"""
Test Script for Place of Birth Extraction and Validation

Tests:
1. OCR extraction of Place of Birth from Yemen ID cards
2. Arabic text normalization
3. Token extraction and classification
4. Matching and scoring logic
5. Decision making (pass/manual_review)

Usage:
    python tests/test_place_of_birth.py --image path/to/id_card.jpg
    python tests/test_place_of_birth.py --test-validation  # Test validation logic only
"""

import sys
import argparse
from pathlib import Path
import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ocr_service import extract_id_from_image
from services.id_card_parser import extract_place_of_birth
from services.place_of_birth_service import (
    normalize_arabic_text,
    extract_tokens,
    classify_token,
    validate_place_of_birth
)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_ocr_place_extraction(image_path: str):
    """
    Test Place of Birth extraction from an ID card image.
    
    Args:
        image_path: Path to ID card image
    """
    print_section("TESTING PLACE OF BIRTH OCR EXTRACTION")
    
    # Load image
    print(f"\nLoading image: {image_path}")
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        return None
    
    print(f"Image loaded successfully: {image.shape}")
    
    # Extract all OCR data
    print("\nRunning OCR on image...")
    ocr_result = extract_id_from_image(image)
    
    print(f"\nOCR Results:")
    print(f"   - Extracted ID: {ocr_result.get('extracted_id')}")
    print(f"   - ID Type: {ocr_result.get('id_type')}")
    print(f"   - Confidence: {ocr_result.get('confidence', 0):.2f}")
    print(f"   - Languages: {', '.join(ocr_result.get('detected_languages_display', []))}")
    
    # Extract place of birth specifically
    print("\nExtracting Place of Birth...")
    all_texts = ocr_result.get('all_texts', [])
    
    if not all_texts:
        print("No text extracted from image")
        return None
    
    print(f"\nAll extracted texts ({len(all_texts)} items):")
    for i, text in enumerate(all_texts, 1):
        print(f"   {i}. {text}")
    
    # Extract place of birth using parser
    place_of_birth = extract_place_of_birth(all_texts)
    
    if place_of_birth:
        print(f"\nPlace of Birth extracted: {place_of_birth}")
    else:
        print("\nPlace of Birth not found in OCR results")
    
    return {
        'ocr_raw': place_of_birth,
        'ocr_confidence': ocr_result.get('confidence', 0.0),
        'all_texts': all_texts
    }


def test_normalization():
    """Test Arabic text normalization."""
    print_section("TESTING ARABIC TEXT NORMALIZATION")
    
    test_cases = [
        ("صنعاء", "Original: صنعاء"),
        ("صنعا", "Alef variant: صنعا"),
        ("أمانة العاصمة", "With hamza: أمانة العاصمة"),
        ("الحديدة", "With definite article: الحديدة"),
        ("حديدة", "Without article: حديدة"),
        ("تعز - جبل حبشي", "With separator: تعز - جبل حبشي"),
    ]
    
    for text, description in test_cases:
        normalized = normalize_arabic_text(text)
        print(f"\n{description}")
        print(f"   Original:   '{text}'")
        print(f"   Normalized: '{normalized}'")


def test_token_extraction():
    """Test token extraction from place names."""
    print_section("TESTING TOKEN EXTRACTION")
    
    test_cases = [
        "صنعاء",
        "صنعاء - بني الحارث",
        "تعز/جبل حبشي",
        "عدن، كريتر",
        "الحديدة - زبيد - باجل",
    ]
    
    for text in test_cases:
        normalized = normalize_arabic_text(text)
        tokens = extract_tokens(normalized)
        print(f"\nText: '{text}'")
        print(f"   Normalized: '{normalized}'")
        print(f"   Tokens: {tokens}")


def test_token_classification():
    """Test token classification (governorate/district/unknown)."""
    print_section("TESTING TOKEN CLASSIFICATION")
    
    test_tokens = [
        "صنعاء",        # Governorate
        "بني الحارث",  # District in Sanaa
        "عدن",         # Governorate
        "كريتر",       # District in Aden
        "تعز",         # Governorate
        "جبل حبشي",    # District in Taiz
        "الحديدة",     # Governorate
        "زبيد",        # District in Hodeidah
        "unknown",     # Unknown token
    ]
    
    for token in test_tokens:
        normalized = normalize_arabic_text(token)
        classification = classify_token(normalized)
        
        print(f"\nToken: '{token}'")
        print(f"   Type: {classification['type']}")
        print(f"   Canonical: {classification['canonical_name']}")
        if classification.get('governorate'):
            print(f"   Governorate: {classification['governorate']}")


def test_validation_logic():
    """Test the complete validation logic with various scenarios."""
    print_section("TESTING VALIDATION LOGIC")
    
    test_scenarios = [
        {
            "name": "Exact Match (Governorate only)",
            "ocr_raw": "صنعاء",
            "user_input": "صنعاء",
            "ocr_confidence": 0.95,
        },
        {
            "name": "Normalized Match (Variant spelling)",
            "ocr_raw": "صنعا",
            "user_input": "صنعاء",
            "ocr_confidence": 0.90,
        },
        {
            "name": "District Match",
            "ocr_raw": "صنعاء - بني الحارث",
            "user_input": "بني الحارث",
            "ocr_confidence": 0.85,
        },
        {
            "name": "Partial Match (Different districts, same governorate)",
            "ocr_raw": "صنعاء - معين",
            "user_input": "صنعاء - بني الحارث",
            "ocr_confidence": 0.80,
        },
        {
            "name": "No Match (Different governorates)",
            "ocr_raw": "صنعاء",
            "user_input": "عدن",
            "ocr_confidence": 0.95,
        },
        {
            "name": "Low OCR Confidence",
            "ocr_raw": "صنعاء",
            "user_input": "صنعاء",
            "ocr_confidence": 0.40,
        },
        {
            "name": "Empty User Input",
            "ocr_raw": "صنعاء",
            "user_input": None,
            "ocr_confidence": 0.90,
        },
        {
            "name": "Garbage Input",
            "ocr_raw": "صنعاء",
            "user_input": "123456",
            "ocr_confidence": 0.90,
        },
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'─' * 80}")
        print(f"Scenario {i}: {scenario['name']}")
        print(f"{'─' * 80}")
        
        result = validate_place_of_birth(
            ocr_raw=scenario['ocr_raw'],
            user_input=scenario['user_input'],
            ocr_confidence=scenario['ocr_confidence']
        )
        
        print(f"\nInput:")
        print(f"   OCR Raw:        {scenario['ocr_raw']}")
        print(f"   User Input:     {scenario['user_input']}")
        print(f"   OCR Confidence: {scenario['ocr_confidence']:.2f}")
        
        print(f"\nResults:")
        print(f"   Normalized District:    {result['normalized']['district']}")
        print(f"   Normalized Governorate: {result['normalized']['governorate']}")
        print(f"   Matching Score:         {result['matching_score']:.2f}")
        print(f"   Decision:              {result['decision'].upper()}")
        print(f"   Reason:                {result['reason']}")
        
        # Visual indicator
        if result['decision'] == 'pass':
            print(f"\n   PASS")
        else:
            print(f"\n   MANUAL REVIEW")


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description='Test Place of Birth extraction and validation')
    parser.add_argument('--image', type=str, help='Path to ID card image to test OCR extraction')
    parser.add_argument('--test-normalization', action='store_true', help='Test Arabic normalization')
    parser.add_argument('--test-tokens', action='store_true', help='Test token extraction')
    parser.add_argument('--test-classification', action='store_true', help='Test token classification')
    parser.add_argument('--test-validation', action='store_true', help='Test validation logic')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    
    args = parser.parse_args()
    
    # If image provided, test OCR extraction
    if args.image:
        result = test_ocr_place_extraction(args.image)
        
        if result and result['ocr_raw']:
            # Also test validation with the extracted data
            print_section("TESTING VALIDATION WITH EXTRACTED DATA")
            
            validation_result = validate_place_of_birth(
                ocr_raw=result['ocr_raw'],
                user_input=None,  # No user input
                ocr_confidence=result['ocr_confidence']
            )
            
            print(f"\nValidation Result:")
            print(f"   Decision: {validation_result['decision'].upper()}")
            print(f"   Matching Score: {validation_result['matching_score']:.2f}")
            print(f"   Reason: {validation_result['reason']}")
    
    # Run individual tests
    if args.test_normalization or args.all:
        test_normalization()
    
    if args.test_tokens or args.all:
        test_token_extraction()
    
    if args.test_classification or args.all:
        test_token_classification()
    
    if args.test_validation or args.all:
        test_validation_logic()
    
    # If no arguments, show help
    if not any([args.image, args.test_normalization, args.test_tokens, 
                args.test_classification, args.test_validation, args.all]):
        parser.print_help()
        print("\nExamples:")
        print("   python tests/test_place_of_birth.py --image data/id_cards/sample.jpg")
        print("   python tests/test_place_of_birth.py --test-validation")
        print("   python tests/test_place_of_birth.py --all")


if __name__ == "__main__":
    main()
