"""
Enhanced Test Script for e-KYC API with Structured Data Extraction

Tests the new features:
- Name extraction (Arabic & English)
- Address extraction
- Date extraction (DOB, Issuance, Expiry)
- Gender
- Place of Birth
- Image filename storage

Usage:
    python tests/test_verify_enhanced.py <id_card_front> <selfie> [id_card_back]

Example:
    python tests/test_verify_enhanced.py data/id_cards/front.jpg data/selfies/selfie.jpg
    python tests/test_verify_enhanced.py data/id_cards/front.jpg data/selfies/selfie.jpg data/id_cards/back.jpg
"""
import sys
import json
import requests
from pathlib import Path

API_URL = "http://localhost:8000"


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_field(label: str, value, color_code: str = ""):
    """Print a labeled field with optional color."""
    reset = "\033[0m" if color_code else ""
    if value is not None and value != "":
        print(f"  {label:<20} {color_code}{value}{reset}")
    else:
        print(f"  {label:<20} \033[90m(not extracted)\033[0m")


def test_health():
    """Test the health endpoint."""
    print_section("Health Check")
    
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        result = response.json()
        
        status_color = "\033[92m" if result.get('status') == 'ok' else "\033[91m"
        print_field("Status", result.get('status'), status_color)
        
        ocr_color = "\033[92m" if result.get('ocr_ready') else "\033[91m"
        print_field("OCR Ready", "✓" if result.get('ocr_ready') else "✗", ocr_color)
        
        face_color = "\033[92m" if result.get('face_recognition_ready') else "\033[91m"
        print_field("Face Recognition", "✓" if result.get('face_recognition_ready') else "✗", face_color)
        
        return result
        
    except requests.exceptions.ConnectionError:
        print("\033[91m  ✗ Could not connect to API\033[0m")
        print("  Please start the server with: uvicorn main:app --reload")
        return None
    except Exception as e:
        print(f"\033[91m  Error: {e}\033[0m")
        return None


def test_verify(id_card_front_path: str, selfie_path: str, id_card_back_path: str = None):
    """Test the /verify endpoint with structured data extraction."""
    print_section("e-KYC Verification Test")
    
    print(f"\n  Files:")
    print(f"    ID Front : {id_card_front_path}")
    print(f"    Selfie   : {selfie_path}")
    if id_card_back_path:
        print(f"    ID Back  : {id_card_back_path}")
    
    try:
        # Prepare files
        files = {}
        
        with open(id_card_front_path, "rb") as f:
            files['id_card_front'] = ("id_front.jpg", f.read(), "image/jpeg")
        
        with open(selfie_path, "rb") as f:
            files['selfie'] = ("selfie.jpg", f.read(), "image/jpeg")
        
        if id_card_back_path:
            with open(id_card_back_path, "rb") as f:
                files['id_card_back'] = ("id_back.jpg", f.read(), "image/jpeg")
        
        # Make request
        print("\n  Sending request to API...")
        response = requests.post(f"{API_URL}/verify", files=files, timeout=120)  # Increased for model loading
        result = response.json()
        
        # Display results
        print_section("Verification Results")
        
        # Status
        success_color = "\033[92m" if result.get('success') else "\033[91m"
        print_field("Success", "✓" if result.get('success') else "✗", success_color)
        print_field("HTTP Status", response.status_code)
        
        # Error (if any)
        if result.get('error'):
            print_field("Error", result.get('error'), "\033[91m")
        
        # Identity Information
        print_section("Identity Information")
        print_field("ID Number", result.get('extracted_id'), "\033[96m")
        print_field("ID Type", result.get('id_type'))
        
        # Personal Details
        print_section("Personal Details")
        print_field("Name (Arabic)", result.get('name_arabic'), "\033[93m")
        print_field("Name (English)", result.get('name_english'), "\033[92m")
        print_field("Date of Birth", result.get('date_of_birth'))
        print_field("Gender", result.get('gender'))
        
        # Place of Birth
        print_section("Place of Birth")
        print_field("Place of Birth", result.get('place_of_birth'), "\033[94m")
        
        # Dates
        print_section("Card Validity")
        print_field("Issuance Date", result.get('issuance_date'))
        print_field("Expiry Date", result.get('expiry_date'))
        
        # Face Verification
        print_section("Face Verification")
        score = result.get('similarity_score')
        if score is not None:
            score_color = "\033[92m" if score >= 0.7 else "\033[93m" if score >= 0.5 else "\033[91m"
            print_field("Similarity Score", f"{score:.4f}", score_color)
            match_status = "✓ Match" if score >= 0.7 else "⚠ Uncertain" if score >= 0.5 else "✗ No Match"
            print_field("Match Status", match_status, score_color)
        else:
            print_field("Similarity Score", "N/A")
        
        # Saved Images
        print_section("Saved Files")
        print_field("ID Front Image", result.get('id_front'))
        print_field("ID Back Image", result.get('id_back'))
        
        # Full JSON Response
        print_section("Full JSON Response")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return result
        
    except FileNotFoundError as e:
        print(f"\n\033[91m  ✗ File not found: {e}\033[0m")
        return None
    except requests.exceptions.Timeout:
        print("\n\033[91m  ✗ Request timed out (NER models might be loading)\033[0m")
        print("  Try again in a few seconds...")
        return None
    except requests.exceptions.ConnectionError:
        print("\n\033[91m  ✗ Could not connect to API\033[0m")
        print("  Please start the server with: uvicorn main:app --reload")
        return None
    except Exception as e:
        print(f"\n\033[91m  ✗ Error: {e}\033[0m")
        return None


def main():
    """Main test function."""
    print("\n" + "=" * 60)
    print("  e-KYC API Test Suite - Enhanced")
    print("=" * 60)
    
    # Test health first
    health_result = test_health()
    
    if not health_result:
        print("\n\033[91m❌ Server is not running. Please start it first!\033[0m\n")
        return
    
    # Parse arguments
    if len(sys.argv) >= 3:
        id_card_front = sys.argv[1]
        selfie = sys.argv[2]
        id_card_back = sys.argv[3] if len(sys.argv) >= 4 else None
        
        # Test verification
        result = test_verify(id_card_front, selfie, id_card_back)
        
        if result and result.get('success'):
            print("\n\033[92m✓ Test completed successfully!\033[0m\n")
        else:
            print("\n\033[91m✗ Test failed\033[0m\n")
            
    else:
        print("\n📖 Usage Instructions:")
        print("-" * 60)
        print("\n  With front ID only:")
        print("    python tests/test_verify_enhanced.py <id_front> <selfie>")
        print("\n  With front and back ID:")
        print("    python tests/test_verify_enhanced.py <id_front> <selfie> <id_back>")
        print("\n  Examples:")
        print("    python tests/test_verify_enhanced.py data/id_cards/front.jpg data/selfies/me.jpg")
        print("    python tests/test_verify_enhanced.py data/id_cards/front.jpg data/selfies/me.jpg data/id_cards/back.jpg")
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
