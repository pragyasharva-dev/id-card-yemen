"""
OCR Service for extracting text and identifying unique ID numbers from ID cards.

Uses PaddleOCR for text extraction and intelligent pattern matching 
to identify ID numbers from various card types (Aadhaar, PAN, Yemen ID, etc.)
"""
import os
import re
import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict
from pathlib import Path

# Suppress PaddlePaddle warnings
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR

from utils.config import ID_PATTERNS, OCR_LANGUAGE, OCR_CONFIDENCE_THRESHOLD


class OCRService:
    """Service for OCR extraction and ID identification."""
    
    _instance: Optional["OCRService"] = None
    _ocr: Optional[PaddleOCR] = None
    
    def __new__(cls):
        """Singleton pattern to reuse OCR model."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize PaddleOCR if not already done."""
        if OCRService._ocr is None:
            OCRService._ocr = PaddleOCR(lang=OCR_LANGUAGE)
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        
        Args:
            image: Input image in BGR format
            
        Returns:
            Preprocessed image
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
    
    def extract_text(self, image: np.ndarray) -> Tuple[List[str], List[float]]:
        """
        Extract all text from an image using OCR.
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            Tuple of (list of texts, list of confidence scores)
        """
        # Preprocess image
        preprocessed = self.preprocess_image(image)
        
        # Run OCR
        result = self._ocr.predict(preprocessed)
        
        texts = []
        scores = []
        
        # Parse PaddleOCR results
        if isinstance(result, list) and len(result) > 0:
            res = result[0]
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            
            # Clean up texts
            texts = [t.strip() for t in texts if t.strip()]
        
        return texts, scores
    
    def identify_id_number(
        self, 
        texts: List[str]
    ) -> Tuple[Optional[str], Optional[str], float]:
        """
        Intelligently identify the unique ID number from OCR texts.
        
        Uses pattern matching against known ID formats to find the 
        most likely unique identifier.
        
        Args:
            texts: List of text strings extracted by OCR
            
        Returns:
            Tuple of (id_number, id_type, confidence)
        """
        candidates = []
        
        for text in texts:
            # Clean the text - remove spaces and special characters for matching
            cleaned = re.sub(r'[\s\-\.]', '', text.upper())
            
            # Check against each ID pattern
            for id_type, pattern_info in ID_PATTERNS.items():
                pattern = pattern_info["pattern"]
                
                if re.match(pattern, cleaned):
                    # Calculate confidence based on pattern match
                    # Higher confidence for exact length match
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
            for text in texts:
                cleaned = re.sub(r'[^\d]', '', text)
                if 8 <= len(cleaned) <= 15:
                    candidates.append({
                        "id": cleaned,
                        "type": "unknown",
                        "confidence": 0.5,
                        "original": text
                    })
        
        if candidates:
            # Return the highest confidence match
            best = max(candidates, key=lambda x: x["confidence"])
            return best["id"], best["type"], best["confidence"]
        
        return None, None, 0.0
    
    def process_id_card(
        self, 
        image: np.ndarray
    ) -> Dict:
        """
        Process an ID card image and extract the unique ID.
        
        Args:
            image: ID card image (BGR format)
            
        Returns:
            Dictionary containing:
            - extracted_id: The unique ID number
            - id_type: Type of ID detected
            - confidence: Confidence score
            - all_texts: All extracted text
        """
        # Extract all text
        texts, scores = self.extract_text(image)
        
        # Identify the unique ID
        extracted_id, id_type, confidence = self.identify_id_number(texts)
        
        return {
            "extracted_id": extracted_id,
            "id_type": id_type,
            "confidence": confidence,
            "all_texts": texts
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
    
    Convenience function that uses the singleton service.
    
    Args:
        image: ID card image (BGR format)
        
    Returns:
        Dictionary with extraction results
    """
    service = get_ocr_service()
    return service.process_id_card(image)


def extract_id_from_path(image_path: str) -> Dict:
    """
    Extract unique ID from an ID card image file.
    
    Args:
        image_path: Path to the ID card image
        
    Returns:
        Dictionary with extraction results
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    
    return extract_id_from_image(image)
