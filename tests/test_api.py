"""
Test script for e-KYC API verification.

Usage:
    python tests/test_api.py <id_card_path> <selfie_path>

Example:
    python tests/test_api.py data/id_cards/sample.jpg data/selfies/sample.jpg
"""
import sys
import requests

API_URL = "http://localhost:8000"


def test_verify(id_card_path: str, selfie_path: str):
    """Test the /verify endpoint with actual images."""
    print(f"\n=== Testing e-KYC Verification ===")
    print(f"ID Card: {id_card_path}")
    print(f"Selfie: {selfie_path}")
    print("-" * 40)
    
    try:
        with open(id_card_path, "rb") as id_file, open(selfie_path, "rb") as selfie_file:
            files = {
                "id_card": ("id_card.jpg", id_file, "image/jpeg"),
                "selfie": ("selfie.jpg", selfie_file, "image/jpeg")
            }
            
            response = requests.post(f"{API_URL}/verify", files=files)
            result = response.json()
            
            print(f"\nResponse Status: {response.status_code}")
            print(f"Success: {result.get('success')}")
            print(f"Extracted ID: {result.get('extracted_id')}")
            print(f"ID Type: {result.get('id_type')}")
            print(f"Similarity Score: {result.get('similarity_score')}")
            
            if result.get('error'):
                print(f"Error: {result.get('error')}")
            
            return result
            
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        return None
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API. Is the server running?")
        return None


def test_health():
    """Test the health endpoint."""
    print("\n=== Testing Health Endpoint ===")
    try:
        response = requests.get(f"{API_URL}/health")
        result = response.json()
        print(f"Status: {result.get('status')}")
        print(f"OCR Ready: {result.get('ocr_ready')}")
        print(f"Face Recognition Ready: {result.get('face_recognition_ready')}")
        return result
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API. Is the server running?")
        return None


def test_extract_id(id_card_path: str):
    """Test the /extract-id endpoint."""
    print(f"\n=== Testing ID Extraction ===")
    print(f"ID Card: {id_card_path}")
    print("-" * 40)
    
    try:
        with open(id_card_path, "rb") as id_file:
            files = {"image": ("id_card.jpg", id_file, "image/jpeg")}
            response = requests.post(f"{API_URL}/extract-id", files=files)
            result = response.json()
            
            print(f"\nResponse Status: {response.status_code}")
            print(f"Success: {result.get('success')}")
            
            if result.get('ocr_result'):
                ocr = result['ocr_result']
                print(f"Extracted ID: {ocr.get('extracted_id')}")
                print(f"ID Type: {ocr.get('id_type')}")
                print(f"Confidence: {ocr.get('confidence')}")
                print(f"All Texts: {ocr.get('all_texts')}")
            
            if result.get('error'):
                print(f"Error: {result.get('error')}")
            
            return result
            
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        return None


if __name__ == "__main__":
    # First test health
    test_health()
    
    if len(sys.argv) >= 3:
        # Test verification with provided images
        id_card_path = sys.argv[1]
        selfie_path = sys.argv[2]
        test_verify(id_card_path, selfie_path)
    elif len(sys.argv) == 2:
        # Test just ID extraction
        id_card_path = sys.argv[1]
        test_extract_id(id_card_path)
    else:
        print("\nUsage:")
        print("  python tests/test_api.py <id_card_path> <selfie_path>  # Full verification")
        print("  python tests/test_api.py <id_card_path>                 # ID extraction only")
        print("\nExample:")
        print("  python tests/test_api.py data/id_cards/sample.jpg data/selfies/sample.jpg")
