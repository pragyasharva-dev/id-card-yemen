"""
OCR Service for extracting text and identifying unique ID numbers from ID cards.

Uses PaddleOCR for text extraction and intelligent pattern matching 
to identify ID numbers from various card types (Aadhaar, PAN, Yemen ID, etc.)

Supports multilingual OCR with per-text language detection:
English, Arabic

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

# Try to import Tesseract for digit validation
try:
    import pytesseract
    # Configure Tesseract path for Windows
    import platform
    if platform.system() == 'Windows':
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        for path in tesseract_paths:
            if Path(path).exists():
                pytesseract.pytesseract.tesseract_cmd = path
                break
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

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
    
    # For Arabic: Must have at least SOME native script characters
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
    
    def preprocess_digits(self, image: np.ndarray) -> np.ndarray:
        """
        Special preprocessing for digit fields (dates).
        Uses padding instead of upscaling to preserve pixel geometry.
        """
        h, w = image.shape[:2]
        
        # Add white padding on ALL sides (10% or minimum 10px)
        # This prevents PaddleOCR from clipping leftmost/rightmost chars
        pad_x = max(10, int(w * 0.10))
        pad_y = max(10, int(h * 0.10))
        padded = cv2.copyMakeBorder(
            image,
            pad_y, pad_y, pad_x, pad_x,  # top, bottom, left, right
            cv2.BORDER_CONSTANT,
            value=(255, 255, 255)  # white background
        )
        
        # Convert to grayscale for contrast enhancement
        gray = cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE for better contrast (gentler settings)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Convert back to BGR
        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    
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
        image: np.ndarray,
        side: str = "front"
    ) -> Dict:
        """
        Process an ID card image and extract the unique ID using multilingual OCR.
        
        Uses YOLO layout detection first for targeted OCR on detected fields.
        Falls back to full-image OCR if YOLO detection fails or is unavailable.
        
        Args:
            image: Input image (BGR format)
            side: Card side - "front" or "back"
            
        Returns:
            Dictionary with extracted fields and metadata
        """
        from services.layout_service import get_layout_service, is_layout_available
        
        layout_fields = {}
        extraction_method = "fallback"
        
        # Step 1: Try YOLO layout detection
        model_key = f"yemen_id_{side}"
        if is_layout_available(model_key):
            layout_service = get_layout_service()
            layout_fields = layout_service.detect_layout(image, model_key)
            
            # If we detected key fields, use targeted extraction
            if layout_fields:
                extraction_method = "yolo"
                return self._extract_from_layout(image, layout_fields, side)
        
        # Step 2: Fallback to full-image OCR
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
            "detected_languages_display": detected_langs_display,
            "extraction_method": extraction_method,
            "layout_fields": {}
        }
    
    def _extract_from_layout(
        self,
        image: np.ndarray,
        layout_fields: Dict,
        side: str
    ) -> Dict:
        """
        Extract text from YOLO-detected field regions using targeted OCR.
        
        Uses field-specific OCR languages for better accuracy:
        - Arabic fields: name, POB, issuing_authority
        - English/numeric fields: DOB, unique_id, expiry_data, issue_date
        
        Args:
            image: Original image
            layout_fields: Dict of label -> LayoutField from YOLO detection
            side: Card side ("front" or "back")
            
        Returns:
            Dictionary with extracted fields
        """
        # Field-to-language mapping for optimal OCR performance
        FIELD_LANGUAGES = {
            'name': ['ar'],              # Arabic names only
            'POB': ['ar'],               # Place of birth in Arabic
            'issuing_authority': ['ar'], # Arabic authority name
            'DOB': ['en'],               # Date format (numbers)
            'unique_id': ['en'],         # ID number (digits)
            'expiry_data': ['en'],       # Date format
            'issue_date': ['en'],        # Date format
        }
        
        # Fields to skip (detection only, no OCR needed)
        SKIP_OCR_FIELDS = {'id_card'}
        
        extracted = {}
        text_results = []
        
        # Process each detected field
        for label, field in layout_fields.items():
            # Skip fields that don't need OCR
            if label in SKIP_OCR_FIELDS:
                extracted[label] = {
                    "text": "",
                    "confidence": field.confidence,
                    "box": field.box,
                    "ocr_lang": [],
                    "skipped": True
                }
                continue
            
            crop = field.crop
            
            # Get OCR languages for this field
            ocr_langs = FIELD_LANGUAGES.get(label, ['en'])
            
            # Apply special preprocessing only for date fields (not unique_id - raw works better)
            DATE_FIELDS = {'DOB', 'expiry_data', 'issue_date'}
            if label in DATE_FIELDS:
                crop = self.preprocess_digits(crop)
            elif label == 'unique_id':
                # FIXED OCR PIPELINE for unique_id (critical for eKYC)
                # Key principles:
                # 1. NO upscaling - preserves original pixel geometry
                # 2. PAD ALL SIDES - PaddleOCR clips edge chars without margin
                # 3. PaddleOCR only - CNN-based, robust to blur
                # 4. Length validation - Yemen ID is 11 digits
                
                h, w = crop.shape[:2]
                
                # Add white padding on ALL sides (10% or minimum 10px)
                # This prevents PaddleOCR from clipping leftmost/rightmost chars
                pad_x = max(10, int(w * 0.10))
                pad_y = max(10, int(h * 0.10))
                ocr_crop = cv2.copyMakeBorder(
                    crop,
                    pad_y, pad_y, pad_x, pad_x,  # top, bottom, left, right
                    cv2.BORDER_CONSTANT,
                    value=(255, 255, 255)  # white background
                )
                
                # OCR on padded crop
                paddle_digits = []
                paddle_results = self.extract_text_with_lang(ocr_crop, 'en')
                for r in paddle_results:
                    digits = re.sub(r'[^0-9]', '', r['text'])
                    if len(digits) >= 8:
                        paddle_digits.append(digits)
                
                # Also try grayscale version (sometimes helps with low contrast)
                gray = cv2.cvtColor(ocr_crop, cv2.COLOR_BGR2GRAY)
                gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                paddle_gray = self.extract_text_with_lang(gray_bgr, 'en')
                for r in paddle_gray:
                    digits = re.sub(r'[^0-9]', '', r['text'])
                    if len(digits) >= 8:
                        paddle_digits.append(digits)
                
                # Select best result with validation
                # Priority: exact 11 digits > longest valid sequence
                final_id = ""
                for candidate in sorted(paddle_digits, key=len, reverse=True):
                    if len(candidate) == 11:
                        final_id = candidate
                        break
                    elif len(candidate) > len(final_id):
                        final_id = candidate
                
                # Validation status
                validation = "valid" if len(final_id) == 11 else f"incomplete_{len(final_id)}_digits"
                
                extracted[label] = {
                    "text": final_id,
                    "confidence": field.confidence,
                    "box": field.box,
                    "ocr_lang": ['en'],
                    "validation": validation,
                    "candidates": paddle_digits
                }
                continue  # Skip normal processing for unique_id
            
            # Run OCR with specified language(s)
            crop_results = []
            for lang in ocr_langs:
                results = self.extract_text_with_lang(crop, lang)
                # Filter: for Arabic OCR, only keep texts with actual Arabic chars
                # For English OCR on date/ID fields, only keep texts with digits
                for r in results:
                    text = r['text']
                    if lang == 'ar':
                        # Must have at least some Arabic characters
                        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
                        if arabic_chars >= 2:
                            crop_results.append(r)
                    elif lang == 'en':
                        # For date/ID fields, accept if it has digits or standard chars
                        if label in ('DOB', 'unique_id', 'expiry_data', 'issue_date'):
                            # Accept if mostly digits or date format
                            if re.search(r'\d', text):
                                crop_results.append(r)
                        else:
                            crop_results.append(r)
            
            # Combine all text from this crop (filter empty)
            crop_text = " ".join([r['text'] for r in crop_results if r['text'].strip()])
            
            # Store the extracted text for this field
            extracted[label] = {
                "text": crop_text,
                "confidence": field.confidence,
                "box": field.box,
                "ocr_lang": ocr_langs
            }
            
            # Add to overall text results
            for r in crop_results:
                r['field_label'] = label
                text_results.append(r)
        
        # Extract unique ID from the unique_id field if detected
        extracted_id = None
        id_confidence = 0.0
        
        if "unique_id" in extracted:
            id_text = extracted["unique_id"]["text"]
            # Clean and extract ID number
            cleaned = re.sub(r'[^0-9]', '', id_text)
            if len(cleaned) >= 8:
                extracted_id = cleaned
                id_confidence = extracted["unique_id"]["confidence"]
        
        # Fallback: try to identify from all extracted texts
        if not extracted_id:
            extracted_id, id_type, id_confidence = self.identify_id_number(text_results)
        else:
            id_type = "yemen_id"
        
        return {
            "extracted_id": extracted_id,
            "id_type": id_type,
            "confidence": id_confidence,
            "text_results": text_results,
            "detected_languages": ["en", "ar"],
            "detected_languages_display": ["English 🇬🇧", "Arabic 🇾🇪"],
            "extraction_method": "yolo",
            "layout_fields": {
                label: {
                    **{k: v for k, v in data.items() if k not in ('ocr_results',)}
                }
                for label, data in extracted.items()
            }
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

