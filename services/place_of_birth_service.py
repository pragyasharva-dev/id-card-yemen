"""
Place of Birth Validation Service

Low-severity, scoring-based, non-blocking validation for Yemen ID place of birth.

Key Principles:
- NEVER auto-reject based on place of birth
- Score for confidence, not correctness
- Always prefer manual review over rejection
- Maintain full audit trail
"""

from typing import Optional, Literal
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

from data.yemen_locations import (
    find_governorate_by_name,
    find_district_governorate,
    get_all_governorate_names,
    get_all_district_names
)
from utils.config import (
    PLACE_OF_BIRTH_PASS_THRESHOLD,
    PLACE_OF_BIRTH_MANUAL_THRESHOLD
)


def normalize_arabic_text(text: str) -> str:
    """
    Normalize Arabic text for consistent matching.
    
    Normalization rules:
    - ا / أ / إ / آ → ا
    - ة ↔ ه
    - ي ↔ ى  
    - Remove diacritics (harakat)
    - Remove extra whitespace
    
    Args:
        text: Raw Arabic text
        
    Returns:
        Normalized text
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
    
    return text


def extract_tokens(text: str) -> list[str]:
    """
    Extract tokens from place of birth text.
    
    Split on:
    - Hyphen (-)
    - En-dash (–)
    - Em-dash (—)
    - Forward slash (/)
    - Comma (،) Arabic comma
    - Comma (,) Latin comma
    
    Args:
        text: Normalized Arabic text
        
    Returns:
        List of tokens
    """
    if not text:
        return []
    
    # Split on various separators
    separators = r'[-–—/،,]'
    tokens = re.split(separators, text)
    
    # Clean and filter tokens
    tokens = [t.strip() for t in tokens if t.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tokens = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    
    return unique_tokens


def classify_token(token: str) -> dict:
    """
    Classify a token as governorate, district, or unknown.
    
    Args:
        token: Normalized Arabic token
        
    Returns:
        {
            "type": "governorate" | "district" | "unknown",
            "canonical_name": str,
            "governorate": str (if type == "district")
        }
    """
    # Check if it's a governorate
    canonical_name, gov_data = find_governorate_by_name(token)
    if canonical_name:
        return {
            "type": "governorate",
            "canonical_name": canonical_name,
            "governorate": canonical_name
        }
    
    # Check if it's a district
    governorate = find_district_governorate(token)
    if governorate:
        return {
            "type": "district",
            "canonical_name": token,
            "governorate": governorate
        }
    
    # Unknown token
    return {
        "type": "unknown",
        "canonical_name": token,
        "governorate": None
    }


def calculate_token_match_score(
    ocr_tokens: list[dict],
    user_tokens: list[dict]
) -> tuple[float, dict, dict]:
    """
    Calculate matching score based on token overlap.
    
    Weighting:
    - Governorate match: 0.6
    - District match: 0.4
    
    Args:
        ocr_tokens: Classified tokens from OCR
        user_tokens: Classified tokens from user input
        
    Returns:
        (base_score, ocr_normalized, user_normalized)
    """
    ocr_governorates = {t["canonical_name"] for t in ocr_tokens if t["type"] == "governorate"}
    user_governorates = {t["canonical_name"] for t in user_tokens if t["type"] == "governorate"}
    
    ocr_districts = {t["canonical_name"] for t in ocr_tokens if t["type"] == "district"}
    user_districts = {t["canonical_name"] for t in user_tokens if t["type"] == "district"}
    
    # Find matches
    governorate_match = bool(ocr_governorates & user_governorates)
    district_match = bool(ocr_districts & user_districts)
    
    # Calculate weighted score
    base_score = 0.0
    if governorate_match:
        base_score += 0.6
    if district_match:
        base_score += 0.4
    
    # Build normalized structures
    ocr_normalized = {
        "governorate": list(ocr_governorates)[0] if ocr_governorates else None,
        "district": list(ocr_districts)[0] if ocr_districts else None
    }
    
    user_normalized = {
        "governorate": list(user_governorates)[0] if user_governorates else None,
        "district": list(user_districts)[0] if user_districts else None
    }
    
    return base_score, ocr_normalized, user_normalized


def validate_place_of_birth(
    ocr_raw: Optional[str],
    user_input: Optional[str],
    ocr_confidence: float
) -> dict:
    """
    Validate place of birth with scoring-based, non-blocking logic.
    
    NEVER auto-rejects. At most, marks for manual review.
    
    Args:
        ocr_raw: Raw place of birth from OCR
        user_input: User-provided place of birth (optional)
        ocr_confidence: OCR confidence score (0-1)
        
    Returns:
        {
            "ocr_raw": str,
            "user_input": str | None,
            "normalized": {
                "district": str | None,
                "governorate": str | None
            },
            "ocr_confidence": float,
            "matching_score": float,
            "decision": "pass" | "manual_review",
            "reason": str
        }
    """
    
    # Special case 1: Empty user input
    if not user_input:
        # TODO: Auto-fill logic (use pass for now as per user request)
        pass
        
        # For now, accept OCR as-is
        if ocr_raw:
            ocr_normalized = normalize_arabic_text(ocr_raw)
            ocr_tokens = extract_tokens(ocr_normalized)
            classified_tokens = [classify_token(token) for token in ocr_tokens]
            
            governorates = [t["canonical_name"] for t in classified_tokens if t["type"] == "governorate"]
            districts = [t["canonical_name"] for t in classified_tokens if t["type"] == "district"]
            
            return {
                "ocr_raw": ocr_raw,
                "user_input": None,
                "normalized": {
                    "governorate": governorates[0] if governorates else None,
                    "district": districts[0] if districts else None
                },
                "ocr_confidence": ocr_confidence,
                "matching_score": 1.0,  # Accept OCR as-is
                "decision": "pass",
                "reason": "No user input provided, accepted OCR data"
            }
        else:
            return {
                "ocr_raw": None,
                "user_input": None,
                "normalized": {
                    "governorate": None,
                    "district": None
                },
                "ocr_confidence": 0.0,
                "matching_score": 0.0,
                "decision": "manual_review",
                "reason": "No place of birth data available"
            }
    
    # Normalize both texts
    ocr_normalized = normalize_arabic_text(ocr_raw) if ocr_raw else ""
    user_normalized = normalize_arabic_text(user_input)
    
    # Special case 2: Check for garbage input (mostly numbers)
    def is_garbage(text: str) -> bool:
        if not text:
            return True
        digit_ratio = sum(c.isdigit() for c in text) / len(text)
        return digit_ratio > 0.5  # More than 50% digits
    
    if is_garbage(user_normalized):
        return {
            "ocr_raw": ocr_raw,
            "user_input": user_input,
            "normalized": {
                "governorate": None,
                "district": None
            },
            "ocr_confidence": ocr_confidence,
            "matching_score": 0.0,
            "decision": "manual_review",
            "reason": "User input appears to be invalid (garbage/numeric data)"
        }
    
    # Extract and classify tokens
    ocr_tokens = extract_tokens(ocr_normalized)
    user_tokens = extract_tokens(user_normalized)
    
    ocr_classified = [classify_token(token) for token in ocr_tokens]
    user_classified = [classify_token(token) for token in user_tokens]
    
    # Calculate match score
    base_score, ocr_norm_struct, user_norm_struct = calculate_token_match_score(
        ocr_classified,
        user_classified
    )
    
    # Apply OCR confidence multiplier
    final_score = base_score * ocr_confidence
    
    # Determine decision based on thresholds
    if final_score >= PLACE_OF_BIRTH_PASS_THRESHOLD:
        decision = "pass"
        reason = f"Strong match (score: {final_score:.2f})"
    else:
        # NEVER reject - always manual review if below threshold
        decision = "manual_review"
        if final_score >= PLACE_OF_BIRTH_MANUAL_THRESHOLD:
            reason = f"Moderate match (score: {final_score:.2f}), needs review"
        else:
            reason = f"Weak match (score: {final_score:.2f}), needs review"
    
    # Build return result
    result = {
        "ocr_raw": ocr_raw,
        "user_input": user_input,
        "normalized": user_norm_struct,
        "ocr_confidence": ocr_confidence,
        "matching_score": final_score,
        "decision": decision,
        "reason": reason
    }
    
    # Log the result for observability
    logger.info(
        f"Place of birth: decision={decision}, score={final_score:.2f}, "
        f"reason='{reason}'"
    )
    
    return result
