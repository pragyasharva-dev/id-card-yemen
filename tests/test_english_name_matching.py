"""
Testing Script for English to English Name Matching

This script tests the English name matching functionality from the name_matching_service.
Accept user inputs at runtime for testing custom name pairs.
"""

from services.name_matching_service import (
    normalize_english_name,
    compare_names,
    validate_name_match_simple
)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_result(label: str, value):
    """Print a formatted result."""
    print(f"{label:30s}: {value}")


def get_float_input(prompt: str, default: float) -> float:
    """Get float input from user with default value."""
    while True:
        user_input = input(prompt)
        if user_input.strip() == "":
            return default
        try:
            value = float(user_input)
            if 0.0 <= value <= 1.0:
                return value
            else:
                print("Please enter a value between 0.0 and 1.0")
        except ValueError:
            print("Invalid input. Please enter a number between 0.0 and 1.0")


def test_name_pair():
    """Test a single name pair with user input."""
    print_section("English Name Matching Test")
    
    # Get OCR name
    ocr_name = input("\nEnter OCR Name (from ID card): ").strip()
    if not ocr_name:
        print("OCR name cannot be empty!")
        return False
    
    # Get User name
    user_name = input("Enter User Name (from user input): ").strip()
    if not user_name:
        print("User name cannot be empty!")
        return False
    
    # Get OCR confidence (optional)
    ocr_confidence = get_float_input(
        "Enter OCR Confidence [0.0-1.0] (press Enter for 1.0): ",
        default=1.0
    )
    
    # Get thresholds (optional)
    print("\nThreshold Configuration (press Enter to use defaults):")
    pass_threshold = get_float_input(
        "  Pass Threshold (default 0.90): ",
        default=0.90
    )
    manual_threshold = get_float_input(
        "  Manual Review Threshold (default 0.70): ",
        default=0.70
    )
    
    # Perform comparison
    print_section("Comparison Results")
    
    # Show normalization
    print("\n1. NORMALIZATION:")
    ocr_normalized = normalize_english_name(ocr_name)
    user_normalized = normalize_english_name(user_name)
    print_result("OCR Name (original)", f"'{ocr_name}'")
    print_result("OCR Name (normalized)", f"'{ocr_normalized}'")
    print_result("User Name (original)", f"'{user_name}'")
    print_result("User Name (normalized)", f"'{user_normalized}'")
    
    # Show detailed comparison
    print("\n2. COMPARISON METRICS:")
    comparison = compare_names(ocr_name, user_name, language="english")
    print_result("Exact Match", comparison["exact_match"])
    print_result("Similarity Score", f"{comparison['similarity_score']:.4f}")
    print_result("Token Overlap", f"{comparison['token_overlap']:.4f}")
    print_result("Combined Score", f"{comparison['final_score']:.4f}")
    
    # Show validation result
    print("\n3. VALIDATION DECISION:")
    result = validate_name_match_simple(
        ocr_name=ocr_name,
        user_name=user_name,
        language="english",
        ocr_confidence=ocr_confidence,
        pass_threshold=pass_threshold,
        manual_threshold=manual_threshold
    )
    
    print_result("OCR Confidence", f"{ocr_confidence:.2f}")
    print_result("Final Score", f"{result['final_score']:.4f}")
    print_result("Decision", result["decision"].upper())
    print_result("Reason", result["reason"])
    
    # Explanation of thresholds
    print("\n4. THRESHOLD GUIDE:")
    print(f"  - Score >= {pass_threshold:.2f} : PASS (Strong match)")
    print(f"  - Score >= {manual_threshold:.2f} : MANUAL_REVIEW (Moderate match)")
    print(f"  - Score <  {manual_threshold:.2f} : REJECT (Name mismatch)")
    
    return True


def main():
    """Run interactive testing."""
    print("\n")
    print("+" + "=" * 78 + "+")
    print("|" + " " * 78 + "|")
    print("|" + "   ENGLISH TO ENGLISH NAME MATCHING TEST SUITE".center(78) + "|")
    print("|" + " " * 78 + "|")
    print("+" + "=" * 78 + "+")
    
    print("\nThis script tests English name matching between OCR-extracted names")
    print("and user-provided names.")
    
    while True:
        if not test_name_pair():
            continue
        
        print("\n" + "=" * 80)
        continue_test = input("\nTest another name pair? (y/n): ").strip().lower()
        if continue_test not in ['y', 'yes']:
            break
    
    print("\n" + "=" * 80)
    print(" TESTING COMPLETED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
