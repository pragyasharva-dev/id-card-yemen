"""
Shared OCR Utilities

Universal OCR helper functions used by all document type services
(National ID, Passport, etc.)

Key Features:
- Padding: Adds white border to prevent edge character clipping
- Preprocessing: Optional contrast enhancement for difficult images
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple


def deskew_image(image: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """
    Deskew (straighten) a rotated image.
    
    Uses Hough Line Transform to detect the dominant angle of text lines,
    then rotates to correct. Useful for slightly tilted document photos.
    
    Args:
        image: Input image (BGR or grayscale)
        max_angle: Maximum rotation angle to correct (degrees). 
                   Ignores larger angles to avoid over-correction.
        
    Returns:
        Deskewed image
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Dilate edges to connect broken lines
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    
    # Detect lines using Hough Transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=image.shape[1] // 4,  # At least 1/4 of image width
        maxLineGap=10
    )
    
    if lines is None or len(lines) == 0:
        # No lines detected, return original
        return image
    
    # Calculate angles of all detected lines
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 != 0:  # Avoid division by zero
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # Only consider near-horizontal lines (text lines)
            if abs(angle) < max_angle:
                angles.append(angle)
    
    if not angles:
        return image
    
    # Use median angle (robust to outliers)
    median_angle = np.median(angles)
    
    # Skip if angle is too small (already straight)
    if abs(median_angle) < 0.5:
        return image
    
    # Rotate image to correct the skew
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    
    # Get rotation matrix
    rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    
    # Calculate new image bounds to avoid cropping
    cos = np.abs(rotation_matrix[0, 0])
    sin = np.abs(rotation_matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    
    # Adjust rotation matrix for new bounds
    rotation_matrix[0, 2] += (new_w - w) / 2
    rotation_matrix[1, 2] += (new_h - h) / 2
    
    # Apply rotation with white background
    rotated = cv2.warpAffine(
        image, 
        rotation_matrix, 
        (new_w, new_h),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255) if len(image.shape) == 3 else 255
    )
    
    return rotated


def add_ocr_padding(
    image: np.ndarray,
    padding_percent: float = 0.10,
    min_padding: int = 10,
    background_color: Tuple[int, int, int] = (255, 255, 255),
    min_height: int = 32,
    target_height: int = 64
) -> np.ndarray:
    """
    Add padding around an image to improve OCR accuracy.
    Also upscales small images to improve OCR performance.
    
    PaddleOCR often clips characters at the edge of images.
    Adding white padding prevents this issue.
    
    Small crops (< min_height) are upscaled to target_height to improve
    OCR accuracy on tight bounding boxes.
    
    Args:
        image: Input image (BGR format)
        padding_percent: Padding as percentage of image size (default 10%)
        min_padding: Minimum padding in pixels (default 10px)
        background_color: Padding color, default white (255, 255, 255)
        min_height: If image height is below this, upscale (default 32px)
        target_height: Target height for upscaling (default 64px)
        
    Returns:
        Padded (and possibly upscaled) image
    """
    h, w = image.shape[:2]
    
    # Step 1: Upscale small images to improve OCR accuracy
    if h < min_height and h > 0:
        scale = target_height / h
        new_w = int(w * scale)
        new_h = target_height
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        h, w = image.shape[:2]
    
    # Ensure image is uint8 (PaddleOCR requirement)
    if image.dtype != np.uint8:
        image = image.astype(np.uint8)

    # Step 2: Add padding
    pad_x = max(min_padding, int(w * padding_percent))

    pad_y = max(min_padding, int(h * padding_percent))
    
    padded = cv2.copyMakeBorder(
        image,
        pad_y, pad_y, pad_x, pad_x,  # top, bottom, left, right
        cv2.BORDER_CONSTANT,
        value=background_color
    )
    
    return padded


def preprocess_for_ocr(
    image: np.ndarray,
    apply_padding: bool = True,
    apply_contrast: bool = False,
    apply_grayscale: bool = False
) -> np.ndarray:
    """
    Preprocess an image crop for optimal OCR accuracy.
    
    Args:
        image: Input image (BGR format)
        apply_padding: Add white border padding (recommended)
        apply_contrast: Apply CLAHE contrast enhancement
        apply_grayscale: Convert to grayscale then back to BGR
        
    Returns:
        Preprocessed image ready for OCR
    """
    result = image.copy()
    
    # Step 1: Padding (prevents edge clipping)
    if apply_padding:
        result = add_ocr_padding(result)
    
    # Step 2: Grayscale conversion (optional)
    if apply_grayscale:
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    
    # Step 3: Contrast enhancement (optional)
    if apply_contrast:
        # Convert to grayscale for CLAHE
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        result = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    
    return result


def preprocess_for_mrz(image: np.ndarray) -> np.ndarray:
    """
    Specialized preprocessing for MRZ (Machine Readable Zone) text.
    
    Applies:
    1. Deskewing (corrects slight rotation from camera angle)
    2. Upscaling (critical for small text)
    3. Padding (prevents edge clipping)
    
    Args:
        image: Input MRZ crop (BGR format)
        
    Returns:
        Preprocessed image optimized for MRZ OCR
    """
    # Step 1: Deskew (correct rotation from tilted document)
    result = deskew_image(image)
    
    # Step 2: Upscale and pad (via add_ocr_padding)
    result = add_ocr_padding(result, min_height=40, target_height=80)
    
    return result


def parse_paddleocr_result(result) -> List[Dict]:
    """
    Parse PaddleOCR result into a consistent format.
    
    Handles both old format (v4 and earlier) and new format (v5+).
    
    Old format: [[box, (text, confidence)], ...]
    New format: [{'rec_texts': [...], 'rec_scores': [...], ...}]
    
    Returns:
        List of dicts with 'text' and 'confidence' keys
    """
    extracted = []
    
    if not result or len(result) == 0:
        return extracted
    
    first_item = result[0]
    
    # Check if it's the new v5 dict format
    if isinstance(first_item, dict):
        # New PP-OCRv5 format
        texts = first_item.get('rec_texts', [])
        scores = first_item.get('rec_scores', [])
        
        for text, score in zip(texts, scores):
            text = text.strip() if text else ""
            if text:
                extracted.append({
                    "text": text,
                    "confidence": float(score)
                })
    else:
        # Old format (list of [box, (text, confidence)])
        for line in result[0] if result[0] else []:
            if line and len(line) >= 2 and line[1]:
                text = line[1][0].strip() if line[1][0] else ""
                confidence = line[1][1] if len(line[1]) > 1 else 0.9
                if text:
                    extracted.append({
                        "text": text,
                        "confidence": float(confidence)
                    })
    
    return extracted


def ocr_image_with_padding(
    image: np.ndarray,
    ocr_engine,
    lang: str = 'en'
) -> List[Dict]:
    """
    Run OCR on an image with automatic padding applied.
    
    This is the universal OCR function that should be used
    for all document field extraction.
    
    Args:
        image: Input image crop (BGR format)
        ocr_engine: OCRService instance (from get_ocr_service())
        lang: Language for OCR ('en' for English, 'ar' for Arabic)
        
    Returns:
        List of dicts with 'text' and 'confidence' keys
    """
    # Apply padding
    padded = add_ocr_padding(image)
    
    # Run OCR with specified language
    result = ocr_engine.ocr(padded, lang=lang)
    
    # Parse result (handles both v4 and v5 formats)
    return parse_paddleocr_result(result)


def ocr_to_single_string(
    image: np.ndarray,
    ocr_engine,
    join_char: str = " ",
    lang: str = 'en'
) -> Tuple[str, float]:
    """
    Run OCR and return a single concatenated string.
    
    Convenience wrapper for fields where you just want the text.
    
    Args:
        image: Input image crop
        ocr_engine: OCRService instance
        join_char: Character to join multiple text segments
        lang: Language for OCR ('en' for English, 'ar' for Arabic)
        
    Returns:
        Tuple of (combined_text, average_confidence)
    """
    results = ocr_image_with_padding(image, ocr_engine, lang=lang)
    
    if not results:
        return "", 0.0
    
    texts = [r["text"] for r in results]
    confidences = [r["confidence"] for r in results]
    
    combined = join_char.join(texts)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    return combined, avg_confidence


def ocr_mrz_line(
    image: np.ndarray,
    ocr_engine
) -> Tuple[str, float]:
    """
    Specialized OCR for a single MRZ line.
    
    Applies MRZ-specific preprocessing (deskew + upscale) 
    before running OCR. Removes spaces from result.
    
    Args:
        image: Input MRZ line crop (BGR format)
        ocr_engine: OCRService instance
        
    Returns:
        Tuple of (mrz_text_no_spaces, confidence)
    """
    # Apply MRZ-specific preprocessing
    processed = preprocess_for_mrz(image)
    
    # Run OCR
    result = ocr_engine.ocr(processed)
    
    # Parse result (handles both v4 and v5 formats)
    parsed = parse_paddleocr_result(result)
    
    texts = [r["text"] for r in parsed]
    confidences = [r["confidence"] for r in parsed]
    
    # Combine and remove ALL spaces (MRZ has no spaces)
    combined = "".join(texts).replace(" ", "")
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    return combined, avg_confidence
