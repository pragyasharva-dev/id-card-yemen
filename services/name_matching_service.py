"""
Name Matching Service for e-KYC OCR-to-User Data Comparison

3-tier matching pipeline:
1. Exact Match: 100% if normalized strings are identical
2. Token-Set Match: 100% if same words present in any order
3. Proportional Fuzzy Match: Per-token fuzzy scoring with
   language-specific thresholds (0.65 English, 0.75 Arabic)

Supports:
- Arabic text normalization (alef/taa/yaa variants, diacritics)
- English text normalization (case, whitespace, special chars)
- Order-invariant comparison (handles "First Last" vs "Last First")
- OCR typo tolerance (e.g., "البريهي" vs "البرهي")
- Transliteration tolerance (e.g., "Mohammed" vs "Muhammad")
"""

from typing import Optional, Literal
import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Language-specific fuzzy thresholds for per-token matching
FUZZY_THRESHOLD_ENGLISH = 0.65   # Looser: handles transliteration variants
FUZZY_THRESHOLD_ARABIC = 0.75    # Tighter: handles OCR typos
MIN_TOKEN_MATCH_RATIO = 0.60     # At least 60% of tokens must match


def normalize_arabic_name(text: str) -> str:
    """
    Normalize Arabic name text for consistent matching.
    
    Normalization rules:
    - ا / أ / إ / آ → ا (alef variations)
    - ة ↔ ه (taa marbouta / haa)
    - ي ↔ ى (yaa variations)
    - Remove diacritics (harakat)
    - Remove extra whitespace
    
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


def _token_set_match(tokens1: set, tokens2: set) -> bool:
    """
    Check if two token sets contain the same words (order-invariant).
    
    Args:
        tokens1: First set of name tokens
        tokens2: Second set of name tokens
        
    Returns:
        True if both sets have identical tokens
    """
    return tokens1 == tokens2 and len(tokens1) > 0


def _proportional_fuzzy_score(
    ocr_tokens: list,
    user_tokens: list,
    threshold: float
) -> float:
    """
    Calculate proportional fuzzy match score between token lists.
    
    For each OCR token, find the best-matching user token.
    A token counts as "matched" if its best similarity >= threshold.
    
    Args:
        ocr_tokens: Tokens from OCR-extracted name
        user_tokens: Tokens from user-entered name
        threshold: Minimum similarity for a token to count as matched
        
    Returns:
        Proportional score (matched_tokens / max_tokens), 0.0 - 1.0
    """
    if not ocr_tokens or not user_tokens:
        return 0.0
    
    matched_count = 0
    used_user_indices = set()
    total_similarity = 0.0
    
    for ocr_token in ocr_tokens:
        best_score = 0.0
        best_idx = -1
        
        for j, user_token in enumerate(user_tokens):
            if j in used_user_indices:
                continue
            score = SequenceMatcher(None, ocr_token, user_token).ratio()
            if score > best_score:
                best_score = score
                best_idx = j
        
        if best_score >= threshold and best_idx >= 0:
            matched_count += 1
            used_user_indices.add(best_idx)
            total_similarity += best_score
    
    # Use max of both token counts as denominator
    # This penalizes missing or extra tokens
    max_tokens = max(len(ocr_tokens), len(user_tokens))
    
    if max_tokens == 0:
        return 0.0
    
    # Proportional score: how many tokens matched out of total
    proportion_matched = matched_count / max_tokens
    
    # Average quality of matched tokens
    avg_quality = total_similarity / matched_count if matched_count > 0 else 0.0
    
    # Final score: weighted by both proportion and quality
    # This ensures high scores only when many tokens match well
    return proportion_matched * avg_quality


def compare_names(
    ocr_name: str,
    user_name: str,
    language: Literal["arabic", "english"]
) -> dict:
    """
    Compare two names using a 3-tier matching pipeline.
    
    Pipeline:
    1. Exact Match: normalized strings identical → 1.0
    2. Token-Set Match: same words in any order → 1.0
    3. Proportional Fuzzy Match: per-token fuzzy scoring
    
    Args:
        ocr_name: Name extracted from OCR
        user_name: Name entered by user
        language: Language of the names ("arabic" or "english")
        
    Returns:
        {
            "ocr_normalized": str,
            "user_normalized": str,
            "match_tier": "exact" | "token_set" | "fuzzy" | "none",
            "exact_match": bool,
            "token_set_match": bool,
            "fuzzy_score": float,
            "final_score": float
        }
    """
    # Step 1: Normalize based on language
    if language == "arabic":
        ocr_normalized = normalize_arabic_name(ocr_name)
        user_normalized = normalize_arabic_name(user_name)
        fuzzy_threshold = FUZZY_THRESHOLD_ARABIC
    else:
        ocr_normalized = normalize_english_name(ocr_name)
        user_normalized = normalize_english_name(user_name)
        fuzzy_threshold = FUZZY_THRESHOLD_ENGLISH
    
    result = {
        "ocr_normalized": ocr_normalized,
        "user_normalized": user_normalized,
        "match_tier": "none",
        "exact_match": False,
        "token_set_match": False,
        "fuzzy_score": 0.0,
        "final_score": 0.0
    }
    
    # Handle empty strings
    if not ocr_normalized or not user_normalized:
        return result
    
    # Tier 1: Exact Match
    if ocr_normalized == user_normalized:
        result["exact_match"] = True
        result["token_set_match"] = True
        result["fuzzy_score"] = 1.0
        result["final_score"] = 1.0
        result["match_tier"] = "exact"
        return result
    
    # Tokenize
    ocr_tokens = ocr_normalized.split()
    user_tokens = user_normalized.split()
    ocr_token_set = set(ocr_tokens)
    user_token_set = set(user_tokens)
    
    # Tier 2: Token-Set Match (order-invariant)
    if _token_set_match(ocr_token_set, user_token_set):
        result["token_set_match"] = True
        result["fuzzy_score"] = 1.0
        result["final_score"] = 1.0
        result["match_tier"] = "token_set"
        return result
    
    # Tier 3: Proportional Fuzzy Match
    fuzzy_score = _proportional_fuzzy_score(
        ocr_tokens, user_tokens, fuzzy_threshold
    )
    result["fuzzy_score"] = fuzzy_score
    result["final_score"] = fuzzy_score
    result["match_tier"] = "fuzzy"
    
    return result


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
    
    # Log the result for observability
    logger.info(
        f"Name match: decision={results['decision']}, score={results['final_score']:.2f}, "
        f"reason='{results['reason']}'"
    )
    
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
