"""
Name Matching Service for e-KYC OCR-to-User Data Comparison

High-severity field validation with:
- Arabic text normalization
- English text normalization
- Fuzzy string matching
- Multiple comparison strategies
- Configurable thresholds for high-severity decisions

Key Principles:
- High severity: Mismatches may cause rejection
- Scoring-based approach
- Handles common spelling variations
- Supports both Arabic and English names
"""

from typing import Optional, Literal
import re
import unicodedata
from difflib import SequenceMatcher


def normalize_arabic_name(text: str) -> str:
    """
    Normalize Arabic name text for consistent matching.
    
    Normalization rules:
    - ا / أ / إ / آ → ا (alef variations)
    - ة ↔ ه (taa marbouta / haa)
    - ي ↔ ى (yaa variations)
    - Remove diacritics (harakat)
    - Remove extra whitespace
    - Convert to lowercase equivalent
    
    Args:
        text: Raw Arabic name
        
    Returns:
        Normalized name
    """
    if not text:
        return ""
    
    # Normalize alef variations
    text = text.replace('أ', 'ا')
    text = text.replace('إ', 'ا')
    text = text.replace('آ', 'ا')
    
    # Normalize taa marbouta and haa
    text = text.replace('ة', 'ه')
    
    # Normalize yaa variations
    text = text.replace('ى', 'ي')
    
    # Remove Arabic diacritics (harakat)
    # Range: U+064B to U+065F
    text = re.sub(r'[\u064B-\u065F]', '', text)
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    text = text.strip()
    
    # Remove non-alphabetic characters except spaces and hyphens
    text = re.sub(r'[^a-zA-Z\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0640\s\-]', '', text)
    
    return text


def normalize_english_name(text: str) -> str:
    """
    Normalize English name text for consistent matching.
    
    Normalization rules:
    - Convert to lowercase
    - Remove extra whitespace
    - Remove special characters except spaces and hyphens
    - Handle common abbreviations
    
    Args:
        text: Raw English name
        
    Returns:
        Normalized name
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    text = text.strip()
    
    # Remove non-alphabetic characters except spaces and hyphens
    text = re.sub(r'[^a-z\s\-]', '', text)
    
    return text


def calculate_string_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings using SequenceMatcher.
    
    Args:
        str1: First string (normalized)
        str2: Second string (normalized)
        
    Returns:
        Similarity score (0.0 - 1.0)
    """
    if not str1 or not str2:
        return 0.0
    
    return SequenceMatcher(None, str1, str2).ratio()


def calculate_token_overlap(str1: str, str2: str) -> float:
    """
    Calculate token overlap between two strings (useful for multi-word names).
    
    Args:
        str1: First string (normalized)
        str2: Second string (normalized)
        
    Returns:
        Token overlap score (0.0 - 1.0)
    """
    if not str1 or not str2:
        return 0.0
    
    tokens1 = set(str1.split())
    tokens2 = set(str2.split())
    
    if not tokens1 or not tokens2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    
    return len(intersection) / len(union) if union else 0.0


def compare_names(
    ocr_name: str,
    user_name: str,
    language: Literal["arabic", "english"]
) -> dict:
    """
    Compare two names with multiple strategies.
    
    Args:
        ocr_name: Name extracted from OCR
        user_name: Name entered by user
        language: Language of the names ("arabic" or "english")
        
    Returns:
        {
            "ocr_normalized": str,
            "user_normalized": str,
            "exact_match": bool,
            "similarity_score": float,
            "token_overlap": float,
            "final_score": float
        }
    """
    # Normalize based on language
    if language == "arabic":
        ocr_normalized = normalize_arabic_name(ocr_name)
        user_normalized = normalize_arabic_name(user_name)
    else:
        ocr_normalized = normalize_english_name(ocr_name)
        user_normalized = normalize_english_name(user_name)
    
    # Check exact match on normalized text
    exact_match = ocr_normalized == user_normalized
    
    # Calculate similarity scores
    similarity_score = calculate_string_similarity(ocr_normalized, user_normalized)
    token_overlap = calculate_token_overlap(ocr_normalized, user_normalized)
    
    # Final score is weighted average:
    # - 70% string similarity (character-level)
    # - 30% token overlap (word-level)
    final_score = (0.7 * similarity_score) + (0.3 * token_overlap)
    
    return {
        "ocr_normalized": ocr_normalized,
        "user_normalized": user_normalized,
        "exact_match": exact_match,
        "similarity_score": similarity_score,
        "token_overlap": token_overlap,
        "final_score": final_score
    }


def validate_name_match(
    ocr_name_arabic: Optional[str],
    user_name_arabic: Optional[str],
    ocr_name_english: Optional[str],
    user_name_english: Optional[str],
    ocr_confidence: float = 1.0,
    pass_threshold: float = 0.90,
    manual_threshold: float = 0.70
) -> dict:
    """
    Validate name matching with configurable thresholds for high-severity field.
    
    High severity field: Mismatches below manual_threshold may cause rejection.
    
    Args:
        ocr_name_arabic: OCR extracted Arabic name
        user_name_arabic: User entered Arabic name
        ocr_name_english: OCR extracted English name
        user_name_english: User entered English name
        ocr_confidence: OCR confidence score (0-1)
        pass_threshold: Score >= this → pass (default: 0.90)
        manual_threshold: Score < this → may reject (default: 0.70)
        
    Returns:
        {
            "arabic_comparison": dict,
            "english_comparison": dict,
            "combined_score": float,
            "final_score": float,  # After OCR confidence multiplier
            "decision": "pass" | "manual_review" | "reject",
            "reason": str
        }
    """
    results = {
        "arabic_comparison": None,
        "english_comparison": None,
        "combined_score": 0.0,
        "final_score": 0.0,
        "decision": "manual_review",
        "reason": ""
    }
    
    # Compare Arabic names
    if ocr_name_arabic and user_name_arabic:
        results["arabic_comparison"] = compare_names(
            ocr_name_arabic,
            user_name_arabic,
            language="arabic"
        )
    
    # Compare English names
    if ocr_name_english and user_name_english:
        results["english_comparison"] = compare_names(
            ocr_name_english,
            user_name_english,
            language="english"
        )
    
    # Calculate combined score
    scores = []
    
    if results["arabic_comparison"]:
        scores.append(results["arabic_comparison"]["final_score"])
    
    if results["english_comparison"]:
        scores.append(results["english_comparison"]["final_score"])
    
    if not scores:
        # No names to compare
        results["reason"] = "No names provided for comparison"
        results["decision"] = "manual_review"
        return results
    
    # Combined score is average of available comparisons
    # (Both languages should match well for high confidence)
    results["combined_score"] = sum(scores) / len(scores)
    
    # Apply OCR confidence multiplier
    results["final_score"] = results["combined_score"] * ocr_confidence
    
    # Determine decision based on thresholds
    if results["final_score"] >= pass_threshold:
        results["decision"] = "pass"
        results["reason"] = f"Strong name match (score: {results['final_score']:.2f})"
    elif results["final_score"] >= manual_threshold:
        results["decision"] = "manual_review"
        results["reason"] = f"Moderate name match (score: {results['final_score']:.2f}), needs review"
    else:
        # High severity field: Low scores may cause rejection
        results["decision"] = "reject"
        results["reason"] = f"Name mismatch (score: {results['final_score']:.2f}), likely different person"
    
    return results


def validate_name_match_simple(
    ocr_name: str,
    user_name: str,
    language: Literal["arabic", "english"] = "arabic",
    ocr_confidence: float = 1.0,
    pass_threshold: float = 0.90,
    manual_threshold: float = 0.70
) -> dict:
    """
    Simplified name validation for single language.
    
    Args:
        ocr_name: OCR extracted name
        user_name: User entered name
        language: Language of names ("arabic" or "english")
        ocr_confidence: OCR confidence score (0-1)
        pass_threshold: Score >= this → pass (default: 0.90)
        manual_threshold: Score < this → may reject (default: 0.70)
        
    Returns:
        {
            "comparison": dict,
            "final_score": float,
            "decision": "pass" | "manual_review" | "reject",
            "reason": str
        }
    """
    comparison = compare_names(ocr_name, user_name, language)
    
    # Apply OCR confidence multiplier
    final_score = comparison["final_score"] * ocr_confidence
    
    # Determine decision
    if final_score >= pass_threshold:
        decision = "pass"
        reason = f"Strong name match (score: {final_score:.2f})"
    elif final_score >= manual_threshold:
        decision = "manual_review"
        reason = f"Moderate name match (score: {final_score:.2f}), needs review"
    else:
        decision = "reject"
        reason = f"Name mismatch (score: {final_score:.2f}), likely different person"
    
    return {
        "comparison": comparison,
        "final_score": final_score,
        "decision": decision,
        "reason": reason
    }
