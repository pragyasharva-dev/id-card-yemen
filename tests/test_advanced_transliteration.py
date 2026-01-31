"""
Test Script for Advanced Transliteration Pipeline.

Tests the 7-step hybrid transliteration and name matching system:
1. Arabic Normalization
2. Name-Aware Tokenization
3. Arabic ↔ Arabic Similarity
4. Cross-Script Bridge
5. Latin Phonetic Similarity
6. Structural Token Overlap
7. Final Score Aggregation
"""
import sys
import os
import io

# Fix Windows console encoding for Arabic text
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.transliteration_core import (
    calculate_name_similarity,
    tokenize_arabic_name,
    tokenize_latin_name,
    arabic_to_latin,
    jaro_winkler_similarity,
)
from utils.text_normalization import (
    normalize_arabic,
    normalize_latin,
    is_arabic_text,
    is_latin_text,
)


def print_separator(title: str):
    """Print a formatted section separator."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def test_arabic_normalization():
    """Test Step 1: Arabic Normalization."""
    print_separator("Step 1: Arabic Normalization")
    
    test_cases = [
        ("أحمد", "احمد"),
        ("محمّد", "محمد"),  # With shadda
        ("فاطمة", "فاطمه"),  # Teh marbuta
        ("مصطفى", "مصطفي"),  # Alef maksura
        ("عبدالله", "عبدالله"),  # Compound
    ]
    
    for arabic, expected in test_cases:
        result = normalize_arabic(arabic)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} '{arabic}' -> '{result}' (expected: '{expected}')")


def test_tokenization():
    """Test Step 2: Name-Aware Tokenization."""
    print_separator("Step 2: Name-Aware Tokenization")
    
    # Arabic tokenization
    arabic_cases = [
        "عبدالله محمد",
        "أحمد بن سعيد",
        "فاطمة الزهراء",
    ]
    
    print("  Arabic:")
    for name in arabic_cases:
        tokens = tokenize_arabic_name(name)
        print(f"    '{name}' → {tokens}")
    
    # Latin tokenization
    latin_cases = [
        "Abdullah Mohammed",
        "Ahmed bin Saeed",
        "Fatima Alzahra",
    ]
    
    print("\n  Latin:")
    for name in latin_cases:
        tokens = tokenize_latin_name(name)
        print(f"    '{name}' → {tokens}")


def test_arabic_similarity():
    """Test Step 3: Arabic ↔ Arabic Similarity."""
    print_separator("Step 3: Arabic ↔ Arabic Similarity")
    
    test_pairs = [
        ("أحمد محمد", "احمد محمد"),  # Same with normalization
        ("محمد علي", "محمد على"),  # Similar
        ("أحمد", "علي"),  # Different
        ("عبدالله", "عبد الله"),  # Compound vs split
    ]
    
    for ar1, ar2 in test_pairs:
        result = calculate_name_similarity(ar1, ar2)
        print(f"  '{ar1}' vs '{ar2}'")
        print(f"    Arabic Similarity: {result['arabic_similarity']:.3f}")
        print(f"    Final Score: {result['final_score']:.3f}")


def test_cross_script_bridge():
    """Test Step 4: Cross-Script Bridge (Arabic → Latin)."""
    print_separator("Step 4: Cross-Script Bridge")
    
    arabic_names = [
        "أحمد",
        "محمد",
        "فاطمة",
        "عبدالله",
        "سعيد",
    ]
    
    for name in arabic_names:
        latin = arabic_to_latin(name)
        print(f"  '{name}' → '{latin}'")


def test_phonetic_similarity():
    """Test Step 5: Latin Phonetic Similarity."""
    print_separator("Step 5: Latin Phonetic Similarity")
    
    test_pairs = [
        ("Mohammed", "Mohamed"),
        ("Ahmed", "Ahmad"),
        ("Fatima", "Fathima"),
        ("Abdullah", "Abdallah"),
        ("Ahmed", "Ali"),  # Different
    ]
    
    for lat1, lat2 in test_pairs:
        result = calculate_name_similarity(lat1, lat2)
        print(f"  '{lat1}' vs '{lat2}'")
        print(f"    Latin Phonetic: {result['latin_phonetic_similarity']:.3f}")


def test_cross_script_comparison():
    """Test cross-script comparison (Arabic vs English)."""
    print_separator("Cross-Script Comparison")
    
    test_pairs = [
        ("أحمد", "Ahmed"),
        ("محمد", "Mohammed"),
        ("فاطمة", "Fatima"),
        ("عبدالله", "Abdullah"),
        ("سعيد", "Saeed"),
    ]
    
    for ar, en in test_pairs:
        result = calculate_name_similarity(ar, en)
        print(f"  '{ar}' vs '{en}'")
        print(f"    Latin Bridge: '{result['latin_bridges']['text1_to_latin']}'")
        print(f"    Final Score: {result['final_score']:.3f}")


def test_full_pipeline():
    """Test complete 7-step pipeline with detailed output."""
    print_separator("Full Pipeline Test")
    
    # Test case: OCR vs User input
    ocr_name = "سماح جابر علي جابر الرحبي"
    user_name = "Samah Jaber Ali Jaber Al-Rahbi"
    
    print(f"  OCR Name:  '{ocr_name}'")
    print(f"  User Name: '{user_name}'")
    print()
    
    result = calculate_name_similarity(ocr_name, user_name)
    
    print("  Pipeline Results:")
    print(f"    1. Normalized (OCR):  '{result['normalized']['text1_arabic']}'")
    print(f"    2. Normalized (User): '{result['normalized']['text2_arabic']}'")
    print(f"    3. Tokens (OCR):  {result['tokens']['text1']}")
    print(f"    4. Tokens (User): {result['tokens']['text2']}")
    print(f"    5. Arabic Similarity:  {result['arabic_similarity']:.3f}")
    print(f"    6. Latin Bridge (OCR): '{result['latin_bridges']['text1_to_latin']}'")
    print(f"    7. Latin Phonetic:     {result['latin_phonetic_similarity']:.3f}")
    print(f"    8. Token Overlap:      {result['token_overlap_score']:.3f}")
    print(f"    9. Final Score:        {result['final_score']:.3f}")


if __name__ == "__main__":
    print("="*60)
    print("  ADVANCED TRANSLITERATION PIPELINE TESTS")
    print("="*60)
    
    test_arabic_normalization()
    test_tokenization()
    test_arabic_similarity()
    test_cross_script_bridge()
    test_phonetic_similarity()
    test_cross_script_comparison()
    test_full_pipeline()
    
    print("\n" + "="*60)
    print("  All tests completed!")
    print("="*60)
