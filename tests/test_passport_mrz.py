"""
Passport MRZ Extraction and Parsing Test Script

Tests the passport services with a real Yemen passport image.

Usage:
    python -m tests.test_passport_mrz <path_to_passport_image>

Example:
    python -m tests.test_passport_mrz "C:/Users/user/.gemini/antigravity/brain/7c4cc7cc-b570-433b-b007-85fba00243fa/uploaded_image_1768891921715.jpg"
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.passport_ocr_service import extract_passport_data, validate_passport_data
from services.passport_mrz_parser import parse_passport_mrz
import json


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_passport_extraction(image_path: str):
    """
    Test full passport extraction pipeline.
    
    Args:
        image_path: Path to passport image
    """
    print_section("PASSPORT EXTRACTION TEST")
    print(f"Image: {image_path}")
    
    # Extract passport data
    print("\n⏳ Extracting passport data...")
    result = extract_passport_data(image_path)
    
    if not result.get("success"):
        print(f"\n❌ EXTRACTION FAILED")
        print(f"Error: {result.get('error')}")
        print(f"Suggestion: {result.get('suggestion', 'N/A')}")
        return
    
    print("\n✅ EXTRACTION SUCCESSFUL")
    
    # Display extracted data
    print_section("EXTRACTED DATA")
    
    print("\n📝 Core Identity:")
    print(f"  Passport Number: {result.get('passport_number')}")
    print(f"  Full Name: {result.get('name_english')}")
    print(f"  Date of Birth: {result.get('date_of_birth')}")
    print(f"  Gender: {result.get('gender')}")
    print(f"  Nationality: {result.get('nationality')}")
    
    print("\n📅 Dates:")
    print(f"  Expiry Date: {result.get('expiry_date')}")
    
    print("\n🌍 Additional Info:")
    print(f"  Place of Birth: {result.get('place_of_birth', 'N/A')}")
    print(f"  Occupation: {result.get('occupation', 'N/A')}")
    
    print("\n🔍 Quality Metrics:")
    print(f"  MRZ Valid: {result.get('mrz_valid')}")
    print(f"  MRZ Confidence: {result.get('mrz_confidence', 0):.2%}")
    print(f"  Extraction Method: {result.get('extraction_method')}")
    
    # Display MRZ
    if result.get('mrz_raw'):
        print_section("MRZ DATA")
        print(f"\nLine 1: {result['mrz_raw']['line1']}")
        print(f"Line 2: {result['mrz_raw']['line2']}")
    
    # Validate
    print_section("VALIDATION")
    validation = validate_passport_data(result)
    
    if validation['valid']:
        print("\n✅ ALL VALIDATIONS PASSED")
    else:
        print("\n⚠️  VALIDATION ISSUES FOUND:")
        for issue in validation['issues']:
            print(f"  - {issue}")
    
    print(f"\nOverall Confidence: {validation['confidence']:.2%}")
    
    # Save full result to JSON
    output_path = "passport_extraction_result.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Full result saved to: {output_path}")


def test_manual_mrz_parsing():
    """Test MRZ parser with known good MRZ lines."""
    print_section("MANUAL MRZ PARSING TEST")
    
    # Example from sample passport
    mrz_lines = [
        "P<YEMALARABI<<FAWAZ<HADI<MOHAMMED<<<<<<<<<<<<",
        "10381272<6YEM8801018M2708218<<<<<<<<<<<<<<08"
    ]
    
    print("\nMRZ Input:")
    print(f"Line 1: {mrz_lines[0]}")
    print(f"Line 2: {mrz_lines[1]}")
    
    # Parse
    result = parse_passport_mrz(mrz_lines)
    
    if result.get("success"):
        print("\n✅ MRZ PARSED SUCCESSFULLY")
        print(f"\nPassport Number: {result['passport_number']}")
        print(f"Name: {result['full_name_english']}")
        print(f"DOB: {result['date_of_birth']}")
        print(f"Gender: {result['gender']}")
        print(f"Expiry: {result['expiry_date']}")
        print(f"Nationality: {result['nationality']}")
        
        print(f"\nChecksum Valid: {result['mrz_valid']}")
        print(f"Confidence: {result['confidence']:.2%}")
        
        # Show checksum details
        if 'checksum_details' in result:
            print("\nChecksum Details:")
            for field, valid in result['checksum_details'].items():
                status = "✓" if valid else "✗"
                print(f"  {status} {field}: {valid}")
    else:
        print(f"\n❌ MRZ PARSING FAILED: {result.get('error')}")


def main():
    """Main test runner."""
    print("\n" + "🔍" * 30)
    print("   PASSPORT MRZ EXTRACTION TEST SUITE")
    print("🔍" * 30)
    
    # Test 1: Manual MRZ parsing
    test_manual_mrz_parsing()
    
    # Test 2: Full extraction from image
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        if os.path.exists(image_path):
            test_passport_extraction(image_path)
        else:
            print(f"\n❌ Image not found: {image_path}")
    else:
        print("\n" + "=" * 60)
        print("ℹ️  To test image extraction, provide image path:")
        print(f"   python -m tests.test_passport_mrz <path_to_image>")
        print("=" * 60)
    
    print("\n✅ Tests completed!")


if __name__ == "__main__":
    main()
