"""
OCR Service for extracting text and identifying unique ID numbers from ID cards.

Uses PaddleOCR for text extraction and intelligent pattern matching 
to identify ID numbers from various card types (Aadhaar, PAN, Yemen ID, etc.)

Supports multilingual OCR with per-text language detection:
English, Arabic, Hindi, Bengali

STRICT VALIDATION: Non-English OCR models must produce text containing
at least some characters from their native script, otherwise output is rejected.
"""
import os
import re
import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict, Set
from pathlib import Path

# Suppress PaddlePaddle warnings
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR

from utils.config import ID_PATTERNS, OCR_CONFIDENCE_THRESHOLD


# Supported languages with their Unicode ranges for detection
SUPPORTED_LANGUAGES = {
    'en': {
        'name': 'English',
        'flag': '🇬🇧',
        'ranges': [(0x0041, 0x005A), (0x0061, 0x007A)],  # A-Z, a-z
        'require_native_script': False  # English doesn't require validation
    },
    'ar': {
        'name': 'Arabic', 
        'flag': '🇾🇪',
        'ranges': [(0x0600, 0x06FF), (0x0750, 0x077F)],  # Arabic, Arabic Supplement
        'require_native_script': True  # Must have Arabic characters
    },
    'hi': {
        'name': 'Hindi',
        'flag': '🇮🇳',
        'ranges': [(0x0900, 0x097F)],  # Devanagari
        'require_native_script': True  # Must have Devanagari characters
    },
    'bengali': {
        'name': 'Bengali',
        'flag': '🇮🇳',
        'ranges': [(0x0980, 0x09FF)],  # Bengali script
        'require_native_script': True  # Must have Bengali characters
    }
}


def char_in_language(char: str, lang_code: str) -> bool:
    """Check if a character belongs to a specific language's script."""
    if lang_code not in SUPPORTED_LANGUAGES:
        return False
    
    code_point = ord(char)
    for start, end in SUPPORTED_LANGUAGES[lang_code]['ranges']:
        if start <= code_point <= end:
            return True
    return False


def count_native_chars(text: str, lang_code: str) -> int:
    """Count how many characters in text belong to the language's native script."""
    count = 0
    for char in text:
        if char_in_language(char, lang_code):
            count += 1
    return count


def text_matches_language(text: str, ocr_lang: str) -> bool:
    """
    Validate that OCR output is legitimate for the OCR model that produced it.
    
    For non-English OCR models: The output MUST contain at least ONE character
    from that language's native script. If Arabic OCR outputs "STTUER FERHIST"
    (all Latin), it's garbage and rejected.
    
    Args:
        text: Extracted text
        ocr_lang: The language code of the OCR model that produced this text
        
    Returns:
        True if text is valid output for this OCR model
    """
    if ocr_lang not in SUPPORTED_LANGUAGES:
        return True
    
    lang_info = SUPPORTED_LANGUAGES[ocr_lang]
    
    # English OCR doesn't require validation - it can output any Latin text
    if not lang_info.get('require_native_script', False):
        return True
    
    # For Arabic/Hindi/Bengali: Must have at least SOME native script characters
    native_count = count_native_chars(text, ocr_lang)
    
    # If zero native script characters, this is garbage output
    if native_count == 0:
        return False
    
    return True


def detect_char_language(char: str) -> Optional[str]:
    """
    Detect the language of a single character based on Unicode range.
    """
    code_point = ord(char)
    
    for lang_code, lang_info in SUPPORTED_LANGUAGES.items():
        for start, end in lang_info['ranges']:
            if start <= code_point <= end:
                return lang_code
    
    return None


def detect_text_language(text: str) -> str:
    """
    Detect the primary language of a text string by analyzing each character.
    """
    lang_counts = {lang: 0 for lang in SUPPORTED_LANGUAGES}
    
    for char in text:
        detected = detect_char_language(char)
        if detected and detected in lang_counts:
            lang_counts[detected] += 1
    
    # Find the language with most characters
    max_count = 0
    primary_lang = 'en'  # Default to English
    
    for lang, count in lang_counts.items():
        if count > max_count:
            max_count = count
            primary_lang = lang
    
    return primary_lang


def get_language_display(lang_code: str) -> str:
    """Get display string for a language code."""
    if lang_code in SUPPORTED_LANGUAGES:
        info = SUPPORTED_LANGUAGES[lang_code]
        return f"{info['name']} {info['flag']}"
    return lang_code


class OCRService:
    """Service for OCR extraction and ID identification with per-text language detection."""
    
    _instance: Optional["OCRService"] = None
    _ocr_models: Dict[str, PaddleOCR] = {}
    
    def __new__(cls):
        """Singleton pattern to reuse OCR model."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize PaddleOCR models for all supported languages if not already done."""
        if not OCRService._ocr_models:
            print("Loading OCR models for all languages...")
            for lang_code in SUPPORTED_LANGUAGES.keys():
                try:
                    print(f"  Loading {lang_code}...")
                    OCRService._ocr_models[lang_code] = PaddleOCR(lang=lang_code)
                except Exception as e:
                    print(f"  Warning: Could not load OCR model for {lang_code}: {e}")
            print("All OCR models loaded.")
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Sharpen the image
        kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # Convert back to BGR for OCR
        return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
    
    def extract_text_with_lang(
        self, 
        image: np.ndarray, 
        lang: str
    ) -> List[Dict]:
        """
        Extract text from an image using OCR with a specific language.
        STRICTLY validates that non-English models produce native script output.
        """
        if lang not in self._ocr_models:
            return []
            
        ocr = self._ocr_models[lang]
        result = ocr.predict(image)
        
        extracted = []
        
        # Parse PaddleOCR results
        if isinstance(result, list) and len(result) > 0:
            res = result[0]
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            
            for text, score in zip(texts, scores):
                text = text.strip()
                if text:
                    # STRICT VALIDATION: Check if output is valid for this OCR model
                    if text_matches_language(text, lang):
                        extracted.append({
                            'text': text,
                            'score': score,
                            'ocr_lang': lang
                        })
        
        return extracted
    
    def extract_text_multilingual(
        self, 
        image: np.ndarray
    ) -> Tuple[List[Dict], List[str], List[str]]:
        """
        Extract text from an image using all OCR languages,
        with strict validation to reject garbage output.
        """
        # Preprocess image
        preprocessed = self.preprocess_image(image)
        
        all_results = []
        seen_texts: Set[str] = set()  # Avoid duplicates
        
        # Run OCR with each language model
        for lang in self._ocr_models.keys():
            results = self.extract_text_with_lang(preprocessed, lang)
            
            for item in results:
                # Normalize for deduplication
                normalized = item['text'].lower().strip()
                
                if normalized not in seen_texts:
                    seen_texts.add(normalized)
                    
                    # Detect actual language of this text by analyzing characters
                    detected_lang = detect_text_language(item['text'])
                    
                    all_results.append({
                        'text': item['text'],
                        'score': item['score'],
                        'detected_language': detected_lang,
                        'detected_language_display': get_language_display(detected_lang)
                    })
        
        # Get unique languages found
        unique_langs = list(set(r['detected_language'] for r in all_results))
        unique_langs_display = [get_language_display(lang) for lang in unique_langs]
        
        return all_results, unique_langs, unique_langs_display
    
    def identify_id_number(
        self, 
        text_results: List[Dict]
    ) -> Tuple[Optional[str], Optional[str], float]:
        """
        Intelligently identify the unique ID number from OCR texts.
        """
        candidates = []
        
        for item in text_results:
            text = item['text']
            # Clean the text - remove spaces and special characters for matching
            cleaned = re.sub(r'[\s\-\.]', '', text.upper())
            
            # Check against each ID pattern
            for id_type, pattern_info in ID_PATTERNS.items():
                pattern = pattern_info["pattern"]
                
                if re.match(pattern, cleaned):
                    expected_len = pattern_info["length"]
                    len_match = 1.0 if len(cleaned) == expected_len else 0.8
                    
                    candidates.append({
                        "id": cleaned,
                        "type": id_type,
                        "confidence": len_match,
                        "original": text
                    })
        
        if not candidates:
            # Fallback: look for any numeric sequence of reasonable length
            for item in text_results:
                text = item['text']
                cleaned = re.sub(r'[^\d]', '', text)
                if 8 <= len(cleaned) <= 15:
                    candidates.append({
                        "id": cleaned,
                        "type": "unknown",
                        "confidence": 0.5,
                        "original": text
                    })
        
        if candidates:
            best = max(candidates, key=lambda x: x["confidence"])
            return best["id"], best["type"], best["confidence"]
        
        return None, None, 0.0
    
    def process_id_card(
        self, 
        image: np.ndarray
    ) -> Dict:
        """
        Process an ID card image and extract the unique ID using multilingual OCR.
        """
        # Extract all text with multilingual OCR
        text_results, detected_langs, detected_langs_display = self.extract_text_multilingual(image)
        
        # Simple text list for backward compatibility
        all_texts = [r['text'] for r in text_results]
        
        # Identify the unique ID
        extracted_id, id_type, confidence = self.identify_id_number(text_results)
        
        return {
            "extracted_id": extracted_id,
            "id_type": id_type,
            "confidence": confidence,
            "all_texts": all_texts,
            "text_results": text_results,
            "detected_languages": detected_langs,
            "detected_languages_display": detected_langs_display
        }


# Module-level convenience functions
_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """Get the singleton OCR service instance."""
    global _service
    if _service is None:
        _service = OCRService()
    return _service


def extract_id_from_image(image: np.ndarray) -> Dict:
    """
    Extract unique ID from an ID card image.
    """
    service = get_ocr_service()
    return service.process_id_card(image)


def extract_id_from_path(image_path: str) -> Dict:
    """
    Extract unique ID from an ID card image file.
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    
    return extract_id_from_image(image)
