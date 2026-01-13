"""
Translation Service for Arabic to English translation.

Uses deep-translator library (Google Translate backend, no API key required).
Provides on-demand translation for OCR results.
"""
from typing import List, Dict, Optional
from functools import lru_cache

from deep_translator import GoogleTranslator


# Simple in-memory cache for translations
_translation_cache: Dict[str, str] = {}


def translate_text(text: str, source: str = "ar", target: str = "en") -> str:
    """
    Translate a single text from source language to target language.
    
    Args:
        text: Text to translate
        source: Source language code (default: Arabic)
        target: Target language code (default: English)
        
    Returns:
        Translated text
    """
    if not text or not text.strip():
        return text
    
    # Check cache first
    cache_key = f"{source}:{target}:{text}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]
    
    try:
        translator = GoogleTranslator(source=source, target=target)
        translated = translator.translate(text)
        
        # Cache the result
        _translation_cache[cache_key] = translated
        
        return translated or text
    except Exception as e:
        print(f"Translation error for '{text}': {e}")
        return text  # Return original on error


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
