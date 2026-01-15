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
