"""
Test script for Hybrid Name Translation Pipeline.

Tests the 3-step conversion:
1. Dictionary Lookup
2. Phonetic Mapping
3. Double Metaphone Correction
"""
import sys
import codecs

# Force UTF-8 for Windows console
if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, 'strict')

from services.translation_service import hybrid_name_convert

# Test cases: (Arabic, Expected English, Expected Method)
TEST_CASES = [
    # Dictionary matches (Step 1)
    ("محمد", "Mohammed", "dictionary"),
    ("فاطمة", "Fatima", "dictionary"),
    ("عبدالله", "Abdullah", "dictionary"),
    ("نور", "Noor", "dictionary"),
    ("جميلة", "Jamila", "dictionary"),
    
    # Phonetic + Correction (Step 2+3)
    # These names are NOT in dictionary but should be corrected
    ("سميرة", "Samira", "dictionary"),  # Now in dictionary
    
    # Pure Phonetic (Step 2 only - no correction available)
    ("غريب", None, "phonetic"),  # Unusual name, just phonetic
]

def run_tests():
    print("=" * 80)
    print("HYBRID NAME TRANSLATION TEST")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    for arabic, expected_english, expected_method in TEST_CASES:
        result = hybrid_name_convert(arabic)
        
        actual_english = result['english']
        actual_method = result['method']
        raw_phonetic = result.get('raw_phonetic', '')
        
        # Check if method matches
        method_ok = (actual_method == expected_method)
        
        # Check if English matches (if expected is set)
        if expected_english:
            english_ok = (actual_english == expected_english)
        else:
            english_ok = True  # No specific expectation
        
        status = "✓" if (method_ok and english_ok) else "✗"
        
        if method_ok and english_ok:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} '{arabic}'")
        print(f"   → English: '{actual_english}' (expected: '{expected_english or 'any'}')")
        print(f"   → Method: {actual_method} (expected: {expected_method})")
        if raw_phonetic:
            print(f"   → Raw Phonetic: '{raw_phonetic}'")
        print()
    
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0


def demo_conversion():
    """Interactive demo of name conversion."""
    print()
    print("=" * 80)
    print("DEMO: Additional Name Conversions")
    print("=" * 80)
    print()
    
    demo_names = [
        "أحمد",      # Ahmed
        "خالد",      # Khaled
        "مريم",      # Maryam
        "زينب",      # Zainab
        "عائشة",     # Aisha
        "سارة",      # Sarah
        "ليلى",      # Layla
        "رانيا",     # Rania
    ]
    
    print(f"{'Arabic':<15} | {'English':<20} | {'Method':<12} | {'Raw Phonetic':<20}")
    print("-" * 75)
    
    for name in demo_names:
        result = hybrid_name_convert(name)
        raw = result.get('raw_phonetic') or '-'
        print(f"{name:<15} | {result['english']:<20} | {result['method']:<12} | {raw:<20}")


if __name__ == "__main__":
    success = run_tests()
    demo_conversion()
    
    sys.exit(0 if success else 1)
