
import sys
import requests
import json
import os

API_URL = "http://localhost:8000"

def test_parse_id(image_path):
    """
    Test the /api/v1/parse-id endpoint to see raw OCR output.
    """
    if not os.path.exists(image_path):
        print(f"Error: File not found - {image_path}")
        return

    print(f"\n============================================================")
    print(f"  Testing /api/v1/parse-id (Raw OCR Output)")
    print(f"============================================================")
    print(f"  Image: {image_path}")
    
    try:
        url = f"{API_URL}/api/v1/parse-id"
        print(f"  Sending request to {url}...")
        
        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, "image/jpeg")}
            response = requests.post(url, files=files)
        
        if response.status_code != 200:
            print(f"  [FAIL] Status Code: {response.status_code}")
            print(f"  Response: {response.text}")
            return

        data = response.json()
        
        # DEBUG: Check if YOLO or Fallback was used
        try:
            extract_url = f"{API_URL}/api/v1/extract-id"
            with open(image_path, "rb") as f:
                files = {"image": (os.path.basename(image_path), f, "image/jpeg")}
                raw_resp = requests.post(extract_url, files=files)
                if raw_resp.status_code == 200:
                    ocr_res = raw_resp.json().get("ocr_result", {})
                    print("\n============================================================")
                    print("  Debug Info (from /extract-id)")
                    print("============================================================")
                    print(f"  Extraction Method  : {ocr_res.get('extraction_method')}")
                    print(f"  ID Confidence      : {ocr_res.get('confidence')}")
                    print(f"  Detected Languages : {ocr_res.get('detected_languages')}")
                    
                    # Print layout fields if available
                    layout = ocr_res.get("layout_fields", {})
                    if layout:
                        print(f"  Detected Fields    : {list(layout.keys())}")
                    else:
                        print(f"  Detected Fields    : None (Fallback mode)")
                        
                    print(f"  All Extracted Text : {ocr_res.get('all_texts')[:10]} ...")
        except Exception as e:
            print(f"  [WARN] Failed to get debug info: {e}")

        print("\n============================================================")
        print("  OCR Extracted Data")
        print("============================================================")
        
        # Define field display order
        fields = [
            ("ID Number", "id_number"),
            ("ID Type", "id_type"),
            ("Full Name (English)", "name_english"),
            ("Full Name (Arabic)", "name_arabic"),
            ("Date of Birth", "date_of_birth"),
            ("Gender", "gender"),
            ("Place of Birth", "place_of_birth"),
            ("Issuance Date", "issuance_date"),
            ("Expiry Date", "expiry_date"),
            ("Blood Type", "blood_type"),
        ]
        
        for label, key in fields:
            val = data.get(key)
            if val:
                print(f"  {label:<25} : {val}")
            else:
                print(f"  {label:<25} : -")
                
        print("\n============================================================")
        print("  Full JSON Response")
        print("============================================================")
        print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n  [ERROR] Request failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/test_parse_id.py <path_to_image>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    test_parse_id(image_path)
