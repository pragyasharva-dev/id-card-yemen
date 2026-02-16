"""
Test Script for Image Quality Check Endpoints.

Usage:
    python test_image_quality.py <id_card_path> <selfie_path>

Example:
    python test_image_quality.py data/id_cards/sample.jpg data/selfies/selfie.jpg
"""
import sys
import requests

API_URL = "http://localhost:8000"


def test_id_quality(image_path: str):
    """Test the /check-id-quality endpoint."""
    print(f"\n{'='*50}")
    print("  Testing ID Card Quality Check")
    print(f"{'='*50}")
    print(f"  Image: {image_path}")
    
    try:
        with open(image_path, "rb") as f:
            files = {"id_card": (image_path.split("\\")[-1], f, "image/jpeg")}
            response = requests.post(f"{API_URL}/check-id-quality", files=files, timeout=30)
        
        result = response.json()
        
        passed_color = "\033[92m" if result.get("passed") else "\033[91m"
        print(f"\n  Passed:        {passed_color}{result.get('passed')}\033[0m")
        print(f"  Face Detected: {result.get('face_detected')}")
        print(f"  Quality Score: {result.get('quality_score'):.3f}")
        
        if result.get("error"):
            print(f"  Error:         \033[91m{result.get('error')}\033[0m")
        
        if result.get("details"):
            print(f"\n  Details:")
            for key, value in result.get("details", {}).items():
                print(f"    {key}: {value}")
        
        return result
        
    except FileNotFoundError:
        print(f"\n  \033[91m✗ File not found: {image_path}\033[0m")
        return None
    except requests.exceptions.ConnectionError:
        print(f"\n  \033[91m✗ Could not connect to API. Is the server running?\033[0m")
        print("  Start with: uvicorn main:app --reload")
        return None


def test_selfie_quality(image_path: str):
    """Test the /check-selfie-quality endpoint."""
    print(f"\n{'='*50}")
    print("  Testing Selfie Quality Check")
    print(f"{'='*50}")
    print(f"  Image: {image_path}")
    
    try:
        with open(image_path, "rb") as f:
            files = {"selfie": (image_path.split("\\")[-1], f, "image/jpeg")}
            response = requests.post(f"{API_URL}/check-selfie-quality", files=files, timeout=30)
        
        result = response.json()
        
        passed_color = "\033[92m" if result.get("passed") else "\033[91m"
        print(f"\n  Passed:        {passed_color}{result.get('passed')}\033[0m")
        print(f"  Face Detected: {result.get('face_detected')}")
        print(f"  Quality Score: {result.get('quality_score'):.3f}")
        
        if result.get("error"):
            print(f"  Error:         \033[91m{result.get('error')}\033[0m")
        
        if result.get("details"):
            print(f"\n  Details:")
            for key, value in result.get("details", {}).items():
                print(f"    {key}: {value}")
        
        return result
        
    except FileNotFoundError:
        print(f"\n  \033[91m✗ File not found: {image_path}\033[0m")
        return None
    except requests.exceptions.ConnectionError:
        print(f"\n  \033[91m✗ Could not connect to API. Is the server running?\033[0m")
        print("  Start with: uvicorn main:app --reload")
        return None


def main():
    print("\n" + "="*50)
    print("  Image Quality Check Test")
    print("="*50)
    
    if len(sys.argv) < 2:
        print("\n📖 Usage:")
        print("  python test_image_quality.py <id_card_path> [selfie_path]")
        print("\n  Examples:")
        print("    python test_image_quality.py data/id_cards/sample.jpg")
        print("    python test_image_quality.py data/id_cards/sample.jpg data/selfies/selfie.jpg")
        print("\n  Single image test (auto-detects type):")
        print("    python test_image_quality.py my_image.jpg --id")
        print("    python test_image_quality.py my_image.jpg --selfie")
        return
    
    id_card_path = sys.argv[1]
    selfie_path = sys.argv[2] if len(sys.argv) >= 3 else None
    
    # Check for --id or --selfie flag
    if "--selfie" in sys.argv:
        test_selfie_quality(id_card_path)
    elif "--id" in sys.argv:
        test_id_quality(id_card_path)
    else:
        # Test both if two paths provided
        test_id_quality(id_card_path)
        if selfie_path and selfie_path not in ["--id", "--selfie"]:
            test_selfie_quality(selfie_path)
    
    print("\n" + "="*50 + "\n")


if __name__ == "__main__":
    main()
