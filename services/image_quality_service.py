"""
Image Quality Service for Face Visibility Validation.

Validates that faces in ID cards/passports and selfies are clearly visible
and not covered or obscured. Uses InsightFace for face detection and
landmark analysis.

Features:
- Face detection using InsightFace
- Landmark visibility analysis (eyes, nose, mouth)
- Face area ratio validation
- Quality scoring with detailed breakdown
"""
import cv2
import numpy as np
from typing import Dict, Optional, Tuple

from .face_extractor import get_face_extractor, is_available as insightface_available
from utils.config import (
    FACE_QUALITY_ENABLED,
    FACE_QUALITY_MIN_LANDMARKS,
    FACE_QUALITY_MIN_CONFIDENCE,
    FACE_QUALITY_MIN_FACE_RATIO
)


def _analyze_landmarks(face) -> Dict:
    """
    Analyze facial landmark visibility.
    
    InsightFace provides 5-point landmarks:
    - Left eye, Right eye, Nose tip, Left mouth corner, Right mouth corner
    
    Args:
        face: InsightFace face object with landmarks
        
    Returns:
        Dictionary with landmark analysis results
    """
    result = {
        "landmarks_detected": 0,
        "eyes_visible": False,
        "nose_visible": False,
        "mouth_visible": False,
        "landmark_confidence": 0.0
    }
    
    if face is None:
        return result
    
    # Get landmarks (5-point: left_eye, right_eye, nose, left_mouth, right_mouth)
    kps = getattr(face, 'kps', None)
    if kps is None or len(kps) < 5:
        return result
    
    # Check if landmarks are valid (not at origin or out of bounds)
    valid_landmarks = 0
    landmark_names = ['left_eye', 'right_eye', 'nose', 'left_mouth', 'right_mouth']
    
    for i, (x, y) in enumerate(kps[:5]):
        if x > 0 and y > 0:
            valid_landmarks += 1
            if i < 2:  # Eyes
                result["eyes_visible"] = True
            elif i == 2:  # Nose
                result["nose_visible"] = True
            else:  # Mouth
                result["mouth_visible"] = True
    
    result["landmarks_detected"] = valid_landmarks
    
    # Calculate confidence based on detection score
    det_score = getattr(face, 'det_score', 0.0)
    result["landmark_confidence"] = float(det_score)
    
    return result


def _calculate_face_ratio(face, image_shape: Tuple[int, int]) -> float:
    """
    Calculate the ratio of face area to image area.
    
    Args:
        face: InsightFace face object with bounding box
        image_shape: (height, width) of the image
        
    Returns:
        Face area ratio (0.0 to 1.0)
    """
    if face is None:
        return 0.0
    
    bbox = getattr(face, 'bbox', None)
    if bbox is None or len(bbox) < 4:
        return 0.0
    
    # Calculate face area
    x1, y1, x2, y2 = bbox
    face_width = x2 - x1
    face_height = y2 - y1
    face_area = face_width * face_height
    
    # Calculate image area
    img_height, img_width = image_shape[:2]
    image_area = img_height * img_width
    
    if image_area == 0:
        return 0.0
    
    return float(face_area / image_area)


def check_id_quality(image: np.ndarray) -> Dict:
    """
    Check face quality in ID card/passport image.
    
    Validates that the face on the ID card is clearly visible and not obscured.
    
    Args:
        image: BGR image of ID card/passport
        
    Returns:
        Dictionary with quality check results:
        - passed: Overall quality check passed
        - face_detected: Whether a face was detected
        - face_visible: Whether face is clearly visible
        - quality_score: Quality score (0.0-1.0)
        - error: Error message if check failed
        - details: Detailed breakdown of checks
    """
    return _check_face_quality(image, image_type="id_document")


def check_selfie_quality(image: np.ndarray) -> Dict:
    """
    Check face quality in selfie image.
    
    Validates that the selfie shows a clearly visible face that is not obscured.
    
    Args:
        image: BGR image of selfie
        
    Returns:
        Dictionary with quality check results:
        - passed: Overall quality check passed
        - face_detected: Whether a face was detected
        - face_visible: Whether face is clearly visible
        - quality_score: Quality score (0.0-1.0)
        - error: Error message if check failed
        - details: Detailed breakdown of checks
    """
    return _check_face_quality(image, image_type="selfie")


def _check_face_quality(image: np.ndarray, image_type: str = "unknown") -> Dict:
    """
    Core face quality checking logic.
    
    Args:
        image: BGR image
        image_type: "id_document" or "selfie"
        
    Returns:
        Quality check result dictionary
    """
    result = {
        "passed": False,
        "face_detected": False,
        "face_visible": False,
        "quality_score": 0.0,
        "error": None,
        "details": {
            "eyes_visible": False,
            "nose_visible": False,
            "mouth_visible": False,
            "face_area_ratio": 0.0,
            "landmark_confidence": 0.0,
            "landmarks_detected": 0
        }
    }
    
    # Check if quality checks are enabled
    if not FACE_QUALITY_ENABLED:
        result["passed"] = True
        result["quality_score"] = 1.0
        return result
    
    # Check if InsightFace is available
    if not insightface_available():
        result["error"] = "Face detection service unavailable"
        return result
    
    # Validate image
    if image is None or image.size == 0:
        result["error"] = "Invalid image provided"
        return result
    
    try:
        # Get face extractor
        extractor = get_face_extractor()
        
        # Detect faces
        faces = extractor.detect_faces(image)
        
        if not faces or len(faces) == 0:
            if image_type == "id_document":
                result["error"] = "No face detected on ID card. Please upload a clear photo of your ID."
            else:
                result["error"] = "No face detected in selfie. Please take a clear photo showing your face."
            return result
        
        result["face_detected"] = True
        
        # Get the largest/most prominent face
        face = extractor.get_largest_face(image)
        
        # Analyze landmarks
        landmark_analysis = _analyze_landmarks(face)
        result["details"].update(landmark_analysis)
        
        # Calculate face area ratio
        face_ratio = _calculate_face_ratio(face, image.shape)
        result["details"]["face_area_ratio"] = round(face_ratio, 4)
        
        # Validate face visibility
        landmarks_ok = landmark_analysis["landmarks_detected"] >= FACE_QUALITY_MIN_LANDMARKS
        confidence_ok = landmark_analysis["landmark_confidence"] >= FACE_QUALITY_MIN_CONFIDENCE
        ratio_ok = face_ratio >= FACE_QUALITY_MIN_FACE_RATIO
        
        # Calculate quality score (weighted average)
        score_components = []
        
        # Landmark score (40% weight)
        landmark_score = min(1.0, landmark_analysis["landmarks_detected"] / 5.0)
        score_components.append(landmark_score * 0.4)
        
        # Confidence score (30% weight)
        confidence_score = min(1.0, landmark_analysis["landmark_confidence"])
        score_components.append(confidence_score * 0.3)
        
        # Face ratio score (30% weight)
        ratio_score = min(1.0, face_ratio / 0.15)  # 15% face ratio = max score
        score_components.append(ratio_score * 0.3)
        
        result["quality_score"] = round(sum(score_components), 3)
        
        # Determine if face is visible
        key_features_visible = (
            landmark_analysis["eyes_visible"] and 
            landmark_analysis["nose_visible"]
        )
        
        result["face_visible"] = key_features_visible and landmarks_ok and confidence_ok
        
        # Determine overall pass/fail
        if not landmarks_ok:
            if image_type == "id_document":
                result["error"] = "Face is partially covered or obscured on ID card. Please upload a clear photo with full face visible."
            else:
                result["error"] = "Face is partially covered or obscured. Please ensure your full face is visible without any obstructions."
        elif not confidence_ok:
            if image_type == "id_document":
                result["error"] = "Face on ID card is unclear. Please upload a higher quality photo."
            else:
                result["error"] = "Face is not clearly visible. Please take a clearer photo with good lighting."
        elif not ratio_ok:
            if image_type == "id_document":
                result["error"] = "Face on ID card is too small. Please upload a closer or higher resolution photo."
            else:
                result["error"] = "Face is too small in the image. Please come closer to the camera."
        elif not key_features_visible:
            if image_type == "id_document":
                result["error"] = "Cannot see eyes or nose clearly on ID card. Please ensure face is not covered."
            else:
                result["error"] = "Cannot see your eyes or nose clearly. Please remove any obstructions from your face."
        else:
            result["passed"] = True
            result["error"] = None
        
        return result
        
    except Exception as e:
        result["error"] = f"Quality check failed: {str(e)}"
        return result


def is_quality_check_enabled() -> bool:
    """Check if face quality validation is enabled."""
    return FACE_QUALITY_ENABLED
