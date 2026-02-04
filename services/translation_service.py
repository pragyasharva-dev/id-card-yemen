"""
Translation Service for Arabic to English translation.

Uses deep-translator library (Google Translate backend, no API key required).
Provides on-demand translation for OCR results.
"""
from typing import List, Dict, Optional
from functools import lru_cache
import logging

from deep_translator import GoogleTranslator

# Set up logging
logger = logging.getLogger(__name__)


# Simple in-memory cache for translations
_translation_cache: Dict[str, str] = {}


def translate_text(text: str, source: str = "ar", target: str = "en", max_retries: int = 2) -> str:
    """
    Translate a single text from source language to target language with retry logic.
    
    Args:
        text: Text to translate
        source: Source language code (default: Arabic)
        target: Target language code (default: English)
        max_retries: Number of retry attempts for failed translations
        
    Returns:
        Translated text (or original text if translation fails)
    """
    if not text or not text.strip():
        return text
    
    # Check cache first
    cache_key = f"{source}:{target}:{text}"
    if cache_key in _translation_cache:
        cached = _translation_cache[cache_key]
        # Validate cached translation
        if _is_valid_translation(text, cached, source, target):
            return cached
        else:
            # Remove bad cached translation
            del _translation_cache[cache_key]
    
    # Try translation with retries
    for attempt in range(max_retries):
        try:
            translator = GoogleTranslator(source=source, target=target)
            translated = translator.translate(text)
            
            if not translated:
                logger.warning(f"Empty translation for '{text}' (attempt {attempt + 1}/{max_retries})")
                continue
            
            # Validate translation quality
            if _is_valid_translation(text, translated, source, target):
                # Cache the good result
                _translation_cache[cache_key] = translated
                return translated
            else:
                logger.warning(f"Poor translation quality for '{text}' -> '{translated}' (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    # Last attempt failed, return original
                    return text
                # Try again
                continue
                
        except Exception as e:
            logger.warning(f"Translation error for '{text}' (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return text  # Return original on final failure
    
    return text  # Fallback to original


def _is_valid_translation(original: str, translated: str, source: str, target: str) -> bool:
    """
    Validate if a translation looks reasonable.
    
    Args:
        original: Original text
        translated: Translated text
        source: Source language
        target: Target language
        
    Returns:
        True if translation seems valid
    """
    if not translated or not translated.strip():
        return False
    
    # For Arabic to English name translation
    if source == "ar" and target == "en":
        # Translation should not be too short for names (most names are > 5 chars)
        if len(translated) < 5:
            return False
        
        # Should not have excessive punctuation or commas
        punct_count = sum(c in '.,;!?' for c in translated)
        if punct_count > 2:  # Names shouldn't have many punctuation marks
            return False
        
        # Reject if it looks like gibberish (repeating characters, no vowels, etc.)
        if translated.lower() in ['akllal', 'akllal,', 'aklal', 'akla']:
            logger.warning(f"Rejected known bad translation: '{translated}'")
            return False
        
        # Check for reasonable letter distribution (should have vowels)
        vowels = sum(c.lower() in 'aeiou' for c in translated)
        if vowels < len(translated) * 0.2:  # At least 20% vowels
            return False
        
        # Should not be mostly the same as original (untranslated)
        if translated.strip() == original.strip():
            return False
        
        # Basic sanity: should contain some letters
        if not any(c.isalpha() for c in translated):
            return False
        
        # Should have reasonable word structure (spaces for multi-word names)
        if len(original.split()) >= 2 and ' ' not in translated:
            # Original has multiple words but translation is one word - suspicious
            return False
    
    return True


def translate_arabic_to_english(texts: List[str]) -> List[Dict[str, str]]:
    """
    Translate a list of Arabic texts to English.
    
    Args:
        texts: List of Arabic texts to translate
        
    Returns:
        List of dicts with 'original' and 'translated' keys
    """
    results = []
    
    for text in texts:
        translated = translate_text(text, source="ar", target="en")
        results.append({
            "original": text,
            "translated": translated
        })
    
    return results


def translate_ocr_results(text_results: List[Dict]) -> List[Dict]:
    """
    Translate OCR results, only translating Arabic texts.
    
    Args:
        text_results: List of OCR text result dicts with 'text' and 'detected_language' keys
        
    Returns:
        List of dicts with original text and translation (if Arabic)
    """
    results = []
    
    for item in text_results:
        text = item.get("text", "")
        detected_lang = item.get("detected_language", "en")
        
        result = {
            "original": text,
            "detected_language": detected_lang,
            "translated": None
        }
        
        # Only translate Arabic texts
        if detected_lang == "ar" and text.strip():
            result["translated"] = translate_text(text, source="ar", target="en")
        
        results.append(result)
    
    return results


def clear_cache():
    """Clear the translation cache."""
    global _translation_cache
    _translation_cache = {}


# =============================================================================
# HYBRID NAME TRANSLATION PIPELINE
# =============================================================================
# A 3-step approach for Arabic-to-English name conversion:
# 1. Dictionary Lookup (exact match)
# 2. Phonetic Mapping (character-by-character)
# 3. Double Metaphone Correction ("snap-to-grid")

from utils.name_dictionary import (
    get_arabic_to_english,
    VALID_ENGLISH_NAMES,
    is_rejected_word
)

# Phonetic mapping: Arabic characters to English sounds
# Optimized for readability, NOT academic transliteration
PHONETIC_MAP = {
    # Hamza variants
    'ء': "'", 'أ': 'a', 'إ': 'e', 'آ': 'aa', 'ؤ': 'o', 'ئ': 'e',
    # Alef variants
    'ا': 'a', 'ى': 'a',
    # Consonants
    'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h', 'خ': 'kh',
    'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh',
    'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh',
    'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
    'ه': 'h', 'ة': 'a',
    # Semi-vowels
    'و': 'o', 'ي': 'i',
    # Diacritics (usually ignored in names, but map for completeness)
    'ً': '', 'ٌ': '', 'ٍ': '', 'َ': 'a', 'ُ': 'u', 'ِ': 'i', 'ّ': '', 'ْ': '',
}


def _phonetic_map(arabic_text: str) -> str:
    """
    Convert Arabic text to English using phonetic character mapping.
    
    Args:
        arabic_text: Arabic text to convert
        
    Returns:
        Phonetically mapped English text
    """
    result = []
    for char in arabic_text:
        if char in PHONETIC_MAP:
            result.append(PHONETIC_MAP[char])
        elif char == ' ':
            result.append(' ')
        elif char.isascii():
            result.append(char)
        # Skip unknown characters
    
    # Clean up: capitalize first letter of each word
    mapped = ''.join(result)
    return ' '.join(word.capitalize() for word in mapped.split())


def _double_metaphone_simple(text: str) -> str:
    """
    Simple Double Metaphone implementation for phonetic encoding.
    Returns primary encoding only.
    
    This is a simplified version focused on common name patterns.
    """
    text = text.upper()
    result = []
    i = 0
    
    while i < len(text):
        c = text[i]
        
        # Skip non-letters
        if not c.isalpha():
            i += 1
            continue
        
        # Vowels at start
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
                result.append('0')  # TH sound
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


# Pre-compute metaphone codes for valid names
_NAME_METAPHONE_CACHE: Dict[str, List[str]] = {}


def _get_metaphone_cache() -> Dict[str, List[str]]:
    """
    Build/return cache of metaphone codes for valid English names.
    """
    global _NAME_METAPHONE_CACHE
    
    if not _NAME_METAPHONE_CACHE:
        for name in VALID_ENGLISH_NAMES:
            code = _double_metaphone_simple(name)
            if code not in _NAME_METAPHONE_CACHE:
                _NAME_METAPHONE_CACHE[code] = []
            _NAME_METAPHONE_CACHE[code].append(name)
    
    return _NAME_METAPHONE_CACHE


def _phonetic_correct(text: str) -> str:
    """
    Try to correct a phonetically mapped name using Double Metaphone.
    
    Args:
        text: Phonetically mapped text (e.g., "Jmila")
        
    Returns:
        Corrected name if found (e.g., "Jamila"), otherwise original
    """
    cache = _get_metaphone_cache()
    
    # Process each word separately
    words = text.split()
    corrected_words = []
    
    for word in words:
        if len(word) < 2:
            corrected_words.append(word)
            continue
        
        code = _double_metaphone_simple(word)
        
        if code in cache:
            # Found a match! Return the first (most common) spelling
            corrected_words.append(cache[code][0])
        else:
            # No match, keep original
            corrected_words.append(word)
    
    return ' '.join(corrected_words)


def hybrid_name_convert(arabic_text: str) -> Dict[str, any]:
    """
    Convert Arabic name to English using the Hybrid Pipeline.
    
    Pipeline:
    1. Dictionary Lookup - Exact match for common names
    2. Phonetic Mapping - Character-by-character conversion
    3. Metaphone Correction - "Snap" to known valid names
    
    Args:
        arabic_text: Arabic name to convert
        
    Returns:
        Dict with:
        - 'original': Original Arabic text
        - 'english': Final English result
        - 'method': Which step produced the result ('dictionary', 'phonetic', 'corrected')
        - 'raw_phonetic': Raw phonetic mapping (before correction)
    """
    if not arabic_text or not arabic_text.strip():
        return {
            'original': arabic_text,
            'english': arabic_text,
            'method': 'empty',
            'raw_phonetic': None
        }
    
    arabic_text = arabic_text.strip()
    
    # Step 1: Dictionary Lookup
    dict_result = get_arabic_to_english(arabic_text)
    if dict_result:
        logger.info(f"Dictionary match: '{arabic_text}' -> '{dict_result}'")
        return {
            'original': arabic_text,
            'english': dict_result,
            'method': 'dictionary',
            'raw_phonetic': None
        }
    
    # Step 2: Phonetic Mapping
    phonetic_result = _phonetic_map(arabic_text)
    logger.info(f"Phonetic map: '{arabic_text}' -> '{phonetic_result}'")
    
    # Step 3: Metaphone Correction
    corrected_result = _phonetic_correct(phonetic_result)
    
    if corrected_result != phonetic_result:
        logger.info(f"Metaphone correction: '{phonetic_result}' -> '{corrected_result}'")
        return {
            'original': arabic_text,
            'english': corrected_result,
            'method': 'corrected',
            'raw_phonetic': phonetic_result
        }
    
    # No correction found, return phonetic result
    return {
        'original': arabic_text,
        'english': phonetic_result,
        'method': 'phonetic',
        'raw_phonetic': phonetic_result
    }

