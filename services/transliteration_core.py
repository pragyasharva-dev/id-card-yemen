"""
Transliteration Core Service - 7-Step Pipeline.

Implements the strict hybrid transliteration and name matching system:
1. Arabic Normalization (via text_normalization.py)
2. Name-Aware Tokenization
3. Arabic ↔ Arabic Similarity (Primary Signal)
4. Cross-Script Bridge (Arabic → Latin)
5. Latin Phonetic Similarity (Secondary Signal)
6. Structural Token Overlap Score
7. Final Score Aggregation

The final score is computed as:
    final_score = 0.7 * arabic_similarity + 0.3 * latin_phonetic_similarity
"""
import re
from typing import Dict, List, Tuple, Optional
import logging

from utils.text_normalization import (
    normalize_arabic,
    normalize_latin,
    is_arabic_text,
    is_latin_text,
    ARABIC_COMPOUND_PREFIXES,
    ARABIC_DEFINITE_ARTICLE,
)

logger = logging.getLogger(__name__)

# =============================================================================
# STEP 2: NAME-AWARE TOKENIZATION
# =============================================================================

def tokenize_arabic_name(text: str) -> List[str]:
    """
    Tokenize Arabic name with awareness of compound forms.
    
    Handles:
    - Compound forms (عبدالله → عبد + الله)
    - Definite article (ال)
    - Connectors (بن, ابن)
    
    Args:
        text: Normalized Arabic text
        
    Returns:
        List of tokens
    """
    if not text:
        return []
    
    # First, normalize the text
    normalized = normalize_arabic(text)
    
    # Split compound prefixes (e.g., عبدالله → عبد الله)
    for prefix in ARABIC_COMPOUND_PREFIXES:
        # Pattern: prefix followed directly by definite article
        pattern = f'{prefix}({ARABIC_DEFINITE_ARTICLE})'
        normalized = re.sub(pattern, f'{prefix} \\1', normalized)
    
    # Split by whitespace
    tokens = normalized.split()
    
    # Remove empty tokens
    tokens = [t.strip() for t in tokens if t.strip()]
    
    return tokens


def tokenize_latin_name(text: str) -> List[str]:
    """
    Tokenize Latin/English name.
    
    Handles:
    - Compound forms (Abdullah → Abd + Allah)
    - Common prefixes (Al-, El-, Abdul-, etc.)
    
    Args:
        text: Normalized Latin text
        
    Returns:
        List of tokens
    """
    if not text:
        return []
    
    normalized = normalize_latin(text)
    
    # Split common compound prefixes
    latin_compound_patterns = [
        (r'\babdul\s*', 'abd al '),
        (r'\babdel\s*', 'abd el '),
        (r'\babdullah\b', 'abd allah'),
        (r'\babdulrahman\b', 'abd alrahman'),
        (r'\babdulaziz\b', 'abd alaziz'),
        (r'\bibn\s*', 'ibn '),
        (r'\bbin\s*', 'bin '),
        (r'\babu\s*', 'abu '),
    ]
    
    for pattern, replacement in latin_compound_patterns:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    
    # Split by whitespace
    tokens = normalized.split()
    tokens = [t.strip() for t in tokens if t.strip()]
    
    return tokens


# =============================================================================
# STEP 3: ARABIC ↔ ARABIC SIMILARITY (PRIMARY SIGNAL)
# =============================================================================

def jaro_winkler_similarity(s1: str, s2: str) -> float:
    """
    Calculate Jaro-Winkler similarity between two strings.
    
    Returns a value between 0.0 (no similarity) and 1.0 (identical).
    """
    if not s1 or not s2:
        return 0.0
    
    if s1 == s2:
        return 1.0
    
    len1, len2 = len(s1), len(s2)
    
    # Calculate match window
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0
    
    s1_matches = [False] * len1
    s2_matches = [False] * len2
    
    matches = 0
    transpositions = 0
    
    # Find matches
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break
    
    if matches == 0:
        return 0.0
    
    # Count transpositions
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1
    
    # Jaro similarity
    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3
    
    # Winkler modification: boost for common prefix
    prefix_len = 0
    for i in range(min(len1, len2, 4)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break
    
    # Standard scaling factor is 0.1
    return jaro + prefix_len * 0.1 * (1 - jaro)


def calculate_arabic_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two Arabic texts.
    
    Uses Jaro-Winkler on normalized tokens with best-match aggregation.
    
    Args:
        text1: First Arabic text (e.g., OCR output)
        text2: Second Arabic text (e.g., user input)
        
    Returns:
        Similarity score in [0.0, 1.0]
    """
    tokens1 = tokenize_arabic_name(text1)
    tokens2 = tokenize_arabic_name(text2)
    
    if not tokens1 or not tokens2:
        return 0.0
    
    # For each token in tokens1, find best match in tokens2
    best_matches = []
    for t1 in tokens1:
        best_score = 0.0
        for t2 in tokens2:
            score = jaro_winkler_similarity(t1, t2)
            if score > best_score:
                best_score = score
        best_matches.append(best_score)
    
    # Average of best matches
    avg_score = sum(best_matches) / len(best_matches)
    
    # Penalize for missing tokens (soft penalty)
    token_ratio = min(len(tokens1), len(tokens2)) / max(len(tokens1), len(tokens2))
    
    # Final score with soft penalty
    final_score = avg_score * (0.8 + 0.2 * token_ratio)
    
    return min(1.0, final_score)


# =============================================================================
# STEP 4: CROSS-SCRIPT BRIDGE (ARABIC → LATIN)
# =============================================================================

# Phonetic mapping: Arabic characters to Latin sounds
# Optimized for name transliteration
ARABIC_TO_LATIN_MAP = {
    # Hamza variants
    'ء': "'", 'أ': 'a', 'إ': 'i', 'آ': 'aa', 'ؤ': 'o', 'ئ': 'e',
    # Alef variants
    'ا': 'a', 'ى': 'a',
    # Consonants
    'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h', 'خ': 'kh',
    'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh',
    'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh',
    'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
    'ه': 'h', 'ة': 'a',
    # Semi-vowels
    'و': 'o', 'ي': 'y',
}


def arabic_to_latin(text: str) -> str:
    """
    Transliterate Arabic text to Latin script.
    
    Uses a phonetic mapping optimized for name recognition.
    One-way only (Arabic → Latin), no reverse.
    
    Args:
        text: Arabic text
        
    Returns:
        Latin transliteration
    """
    if not text:
        return ""
    
    # First normalize
    normalized = normalize_arabic(text)
    
    result = []
    for char in normalized:
        if char in ARABIC_TO_LATIN_MAP:
            result.append(ARABIC_TO_LATIN_MAP[char])
        elif char == ' ':
            result.append(' ')
        elif char.isascii():
            result.append(char)
        # Skip unknown characters
    
    # Clean up and capitalize
    mapped = ''.join(result)
    mapped = re.sub(r'\s+', ' ', mapped).strip()
    
    # Capitalize first letter of each word
    return ' '.join(word.capitalize() for word in mapped.split())


# =============================================================================
# STEP 5: LATIN PHONETIC SIMILARITY (SECONDARY SIGNAL)
# =============================================================================

def simple_metaphone(text: str) -> str:
    """
    Simple metaphone encoding for phonetic matching.
    
    Converts text to a phonetic code for comparison.
    """
    if not text:
        return ""
    
    text = text.upper()
    result = []
    i = 0
    
    while i < len(text):
        c = text[i]
        
        # Skip non-letters
        if not c.isalpha():
            i += 1
            continue
        
        # Vowels at start only
        if c in 'AEIOU':
            if i == 0:
                result.append('A')
            i += 1
            continue
        
        # Consonant mappings
        if c == 'B':
            result.append('P')
        elif c == 'C':
            if i + 1 < len(text) and text[i + 1] in 'EIY':
                result.append('S')
            else:
                result.append('K')
        elif c == 'D':
            result.append('T')
        elif c == 'F':
            result.append('F')
        elif c == 'G':
            if i + 1 < len(text) and text[i + 1] in 'EIY':
                result.append('J')
            else:
                result.append('K')
        elif c == 'H':
            result.append('H')
        elif c == 'J':
            result.append('J')
        elif c == 'K':
            result.append('K')
        elif c == 'L':
            result.append('L')
        elif c == 'M':
            result.append('M')
        elif c == 'N':
            result.append('N')
        elif c == 'P':
            result.append('P')
        elif c == 'Q':
            result.append('K')
        elif c == 'R':
            result.append('R')
        elif c == 'S':
            if i + 1 < len(text) and text[i + 1] == 'H':
                result.append('X')
                i += 1
            else:
                result.append('S')
        elif c == 'T':
            if i + 1 < len(text) and text[i + 1] == 'H':
                result.append('0')
                i += 1
            else:
                result.append('T')
        elif c == 'V':
            result.append('F')
        elif c == 'W':
            result.append('W')
        elif c == 'X':
            result.append('KS')
        elif c == 'Y':
            result.append('Y')
        elif c == 'Z':
            result.append('S')
        
        i += 1
    
    return ''.join(result)


def calculate_phonetic_similarity(lat1: str, lat2: str) -> float:
    """
    Calculate phonetic similarity between two Latin texts.
    
    Uses metaphone encoding + Jaro-Winkler.
    
    Args:
        lat1: First Latin text
        lat2: Second Latin text
        
    Returns:
        Similarity score in [0.0, 1.0]
    """
    if not lat1 or not lat2:
        return 0.0
    
    # Normalize
    norm1 = normalize_latin(lat1)
    norm2 = normalize_latin(lat2)
    
    # Get metaphone codes
    meta1 = simple_metaphone(norm1)
    meta2 = simple_metaphone(norm2)
    
    # Compare using Jaro-Winkler
    return jaro_winkler_similarity(meta1, meta2)


# =============================================================================
# STEP 6: STRUCTURAL TOKEN OVERLAP SCORE
# =============================================================================

def calculate_token_overlap(tokens1: List[str], tokens2: List[str]) -> float:
    """
    Calculate overlap ratio of meaningful name tokens.
    
    Penalizes missing or extra components.
    
    Args:
        tokens1: First set of tokens
        tokens2: Second set of tokens
        
    Returns:
        Overlap score in [0.0, 1.0]
    """
    if not tokens1 or not tokens2:
        return 0.0
    
    # Count matching tokens (using Jaro-Winkler threshold)
    match_threshold = 0.85
    matched = 0
    
    used_j = set()
    for t1 in tokens1:
        best_j = -1
        best_score = 0.0
        for j, t2 in enumerate(tokens2):
            if j in used_j:
                continue
            score = jaro_winkler_similarity(t1.lower(), t2.lower())
            if score >= match_threshold and score > best_score:
                best_score = score
                best_j = j
        if best_j >= 0:
            matched += 1
            used_j.add(best_j)
    
    # Calculate overlap ratio
    total = max(len(tokens1), len(tokens2))
    return matched / total if total > 0 else 0.0


# =============================================================================
# STEP 7: FINAL SCORE AGGREGATION
# =============================================================================

def calculate_name_similarity(
    text1: str,
    text2: str,
    arabic_weight: float = 0.7,
    latin_weight: float = 0.3
) -> Dict:
    """
    Calculate final name similarity using the 7-step pipeline.
    
    Pipeline:
    1. Arabic Normalization
    2. Name-Aware Tokenization
    3. Arabic ↔ Arabic Similarity (Primary Signal)
    4. Cross-Script Bridge (Arabic → Latin)
    5. Latin Phonetic Similarity (Secondary Signal)
    6. Structural Token Overlap
    7. Final Score Aggregation
    
    Final formula:
        final_score = arabic_weight * arabic_similarity + latin_weight * latin_phonetic_similarity
    
    Args:
        text1: First text (OCR or user input)
        text2: Second text (user input or OCR)
        arabic_weight: Weight for Arabic similarity (default 0.7)
        latin_weight: Weight for Latin similarity (default 0.3)
        
    Returns:
        Dict with:
        - final_score: Combined score [0.0, 1.0]
        - arabic_similarity: Arabic-to-Arabic score
        - latin_phonetic_similarity: Latin phonetic score
        - token_overlap_score: Structural overlap score
        - normalized: Dict with normalized texts
        - tokens: Dict with tokenized texts
        - latin_bridges: Dict with Latin transliterations
    """
    # Detect text types
    text1_is_arabic = is_arabic_text(text1)
    text2_is_arabic = is_arabic_text(text2)
    text1_is_latin = is_latin_text(text1)
    text2_is_latin = is_latin_text(text2)
    
    result = {
        "final_score": 0.0,
        "arabic_similarity": 0.0,
        "latin_phonetic_similarity": 0.0,
        "token_overlap_score": 0.0,
        "normalized": {
            "text1_arabic": None,
            "text2_arabic": None,
            "text1_latin": None,
            "text2_latin": None,
        },
        "tokens": {
            "text1": [],
            "text2": [],
        },
        "latin_bridges": {
            "text1_to_latin": None,
            "text2_to_latin": None,
        },
    }
    
    # Step 1 & 2: Normalize and tokenize
    if text1_is_arabic:
        result["normalized"]["text1_arabic"] = normalize_arabic(text1)
        result["tokens"]["text1"] = tokenize_arabic_name(text1)
        result["latin_bridges"]["text1_to_latin"] = arabic_to_latin(text1)
    if text1_is_latin:
        result["normalized"]["text1_latin"] = normalize_latin(text1)
        if not result["tokens"]["text1"]:
            result["tokens"]["text1"] = tokenize_latin_name(text1)
    
    if text2_is_arabic:
        result["normalized"]["text2_arabic"] = normalize_arabic(text2)
        result["tokens"]["text2"] = tokenize_arabic_name(text2)
        result["latin_bridges"]["text2_to_latin"] = arabic_to_latin(text2)
    if text2_is_latin:
        result["normalized"]["text2_latin"] = normalize_latin(text2)
        if not result["tokens"]["text2"]:
            result["tokens"]["text2"] = tokenize_latin_name(text2)
    
    # Step 3: Arabic ↔ Arabic Similarity
    arabic_similarity = 0.0
    if text1_is_arabic and text2_is_arabic:
        arabic_similarity = calculate_arabic_similarity(text1, text2)
    
    result["arabic_similarity"] = arabic_similarity
    
    # Step 4 & 5: Cross-Script Bridge + Latin Phonetic Similarity
    latin_phonetic_similarity = 0.0
    
    # Determine Latin representations
    lat1 = None
    lat2 = None
    
    if text1_is_arabic:
        lat1 = result["latin_bridges"]["text1_to_latin"]
    elif text1_is_latin:
        lat1 = normalize_latin(text1)
    
    if text2_is_arabic:
        lat2 = result["latin_bridges"]["text2_to_latin"]
    elif text2_is_latin:
        lat2 = normalize_latin(text2)
    
    if lat1 and lat2:
        latin_phonetic_similarity = calculate_phonetic_similarity(lat1, lat2)
    
    result["latin_phonetic_similarity"] = latin_phonetic_similarity
    
    # Step 6: Token Overlap
    if result["tokens"]["text1"] and result["tokens"]["text2"]:
        result["token_overlap_score"] = calculate_token_overlap(
            result["tokens"]["text1"],
            result["tokens"]["text2"]
        )
    
    # Step 7: Final Score Aggregation
    # If both texts are Arabic, use the weighted formula
    if text1_is_arabic and text2_is_arabic:
        result["final_score"] = (
            arabic_weight * arabic_similarity +
            latin_weight * latin_phonetic_similarity
        )
    # If one is Arabic and one is Latin (cross-script comparison)
    elif (text1_is_arabic and text2_is_latin) or (text1_is_latin and text2_is_arabic):
        # In cross-script, Latin phonetic is the only signal
        result["final_score"] = latin_phonetic_similarity
    # If both are Latin
    elif text1_is_latin and text2_is_latin:
        result["final_score"] = latin_phonetic_similarity
    else:
        # Fallback: use whatever signal is available
        result["final_score"] = max(arabic_similarity, latin_phonetic_similarity)
    
    # Log the pipeline results
    logger.debug(
        f"Name similarity: {result['final_score']:.3f} "
        f"(ar={arabic_similarity:.3f}, lat={latin_phonetic_similarity:.3f})"
    )
    
    return result
