"""
Text Normalization Utilities for Arabic and English.

Provides functions for:
- Arabic normalization (Step 1 of the pipeline)
- English/Latin normalization
- Common character mappings
"""
import re
import unicodedata

# =============================================================================
# ARABIC NORMALIZATION (STEP 1)
# =============================================================================

# Alef variants → bare Alef
ARABIC_ALEF_VARIANTS = {
    '\u0623': '\u0627',  # أ (Alef with Hamza above) → ا
    '\u0625': '\u0627',  # إ (Alef with Hamza below) → ا
    '\u0622': '\u0627',  # آ (Alef with Madda) → ا
}

# Teh Marbuta → Heh
ARABIC_TEH_MARBUTA = {
    '\u0629': '\u0647',  # ة → ه
}

# Alef Maksura → Yeh
ARABIC_ALEF_MAKSURA = {
    '\u0649': '\u064A',  # ى → ي
}

# Diacritics to remove (Harakat)
ARABIC_DIACRITICS = (
    '\u064B',  # Fathatan
    '\u064C',  # Dammatan
    '\u064D',  # Kasratan
    '\u064E',  # Fatha
    '\u064F',  # Damma
    '\u0650',  # Kasra
    '\u0651',  # Shadda
    '\u0652',  # Sukun
    '\u0670',  # Superscript Alef
)

# Tatweel (elongation)
ARABIC_TATWEEL = '\u0640'  # ـ


def normalize_arabic(text: str) -> str:
    """
    Normalize Arabic text according to strict pipeline rules.
    
    Steps:
    1. أ / إ / آ → ا (Alef normalization)
    2. ة → ه (Teh Marbuta)
    3. ى → ي (Alef Maksura)
    4. Remove diacritics
    5. Remove tatweel
    6. Normalize whitespace
    7. Remove punctuation
    
    Args:
        text: Arabic text to normalize
        
    Returns:
        Normalized Arabic text
    """
    if not text:
        return ""
    
    result = text
    
    # Step 1: Alef normalization
    for variant, replacement in ARABIC_ALEF_VARIANTS.items():
        result = result.replace(variant, replacement)
    
    # Step 2: Teh Marbuta → Heh
    for variant, replacement in ARABIC_TEH_MARBUTA.items():
        result = result.replace(variant, replacement)
    
    # Step 3: Alef Maksura → Yeh
    for variant, replacement in ARABIC_ALEF_MAKSURA.items():
        result = result.replace(variant, replacement)
    
    # Step 4: Remove diacritics
    for diacritic in ARABIC_DIACRITICS:
        result = result.replace(diacritic, '')
    
    # Step 5: Remove tatweel
    result = result.replace(ARABIC_TATWEEL, '')
    
    # Step 6: Normalize whitespace
    result = re.sub(r'\s+', ' ', result).strip()
    
    # Step 7: Remove punctuation (keep Arabic letters, spaces, and digits)
    result = re.sub(r'[^\u0600-\u06FF\s0-9]', '', result)
    
    return result


# =============================================================================
# ENGLISH/LATIN NORMALIZATION
# =============================================================================

def normalize_latin(text: str) -> str:
    """
    Normalize English/Latin text for phonetic comparison.
    
    Steps:
    1. Lowercase
    2. Remove punctuation
    3. Collapse elongated vowels (aa→a, oo→o, ee→i)
    4. Normalize spacing
    
    Args:
        text: English/Latin text to normalize
        
    Returns:
        Normalized Latin text
    """
    if not text:
        return ""
    
    result = text.lower()
    
    # Remove punctuation
    result = re.sub(r'[^\w\s]', '', result)
    
    # Collapse elongated vowels
    result = re.sub(r'aa+', 'a', result)
    result = re.sub(r'oo+', 'o', result)
    result = re.sub(r'ee+', 'i', result)  # ee → i (closer to Arabic 'ي')
    result = re.sub(r'ii+', 'i', result)
    result = re.sub(r'uu+', 'u', result)
    
    # Normalize spacing
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result


# =============================================================================
# NAME-SPECIFIC COMPOUND HANDLING
# =============================================================================

# Known compound name prefixes in Arabic
ARABIC_COMPOUND_PREFIXES = [
    'عبد',    # Abd
    'ابن',    # Ibn (son of)
    'بن',     # Bin (son of)
    'ابو',    # Abu (father of)
    'أبو',    # Abu (with hamza)
    'ام',     # Umm (mother of)
    'أم',     # Umm (with hamza)
]

# Definite article
ARABIC_DEFINITE_ARTICLE = 'ال'


def is_arabic_text(text: str) -> bool:
    """Check if text contains Arabic characters."""
    if not text:
        return False
    return bool(re.search(r'[\u0600-\u06FF]', text))


def is_latin_text(text: str) -> bool:
    """Check if text contains Latin characters."""
    if not text:
        return False
    return bool(re.search(r'[a-zA-Z]', text))
