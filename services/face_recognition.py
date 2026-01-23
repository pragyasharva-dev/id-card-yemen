"""
Face Recognition Service for comparing faces.

Uses InsightFace embeddings with cosine similarity for face matching.
"""
import cv2
import numpy as np
from typing import Optional, Dict, Tuple

from .face_extractor import (
    get_face_extractor, 
    get_embedding, 
    is_available as insightface_available
)


def cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First face embedding
        embedding2: Second face embedding
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    # Normalize embeddings
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    # Compute cosine similarity
    similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
    
    # Clamp to [0, 1] range (similarity can be negative for very different faces)
    return float(max(0.0, min(1.0, (similarity + 1) / 2)))


def compare_embeddings(
    embedding1: np.ndarray, 
    embedding2: np.ndarray
) -> float:
    """
    Compare two face embeddings.
    
    This uses a normalized cosine similarity that maps the result to [0, 1].
    
    Args:
        embedding1: First face embedding
        embedding2: Second face embedding
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    return cosine_similarity(embedding1, embedding2)


def compare_faces(
    image1: np.ndarray, 
    image2: np.ndarray
) -> Dict:
    """
    Compare faces in two images.
    
    Args:
        image1: First image (e.g., ID card)
        image2: Second image (e.g., selfie)
        
    Returns:
        Dictionary containing:
        - similarity_score: Float between 0.0 and 1.0
        - image1_face_detected: Boolean
        - image2_face_detected: Boolean
        - error: String if any error occurred
    """
    result = {
        "similarity_score": 0.0,
        "image1_face_detected": False,
        "image2_face_detected": False,
        "error": None
    }
    
    if not insightface_available():
        result["error"] = "InsightFace not installed"
        return result
    
    # Get embeddings from both images
    embedding1 = get_embedding(image1)
    embedding2 = get_embedding(image2)
    
    result["image1_face_detected"] = embedding1 is not None
    result["image2_face_detected"] = embedding2 is not None
    
    if embedding1 is None:
        result["error"] = "No face detected in first image (ID card)"
        return result
    
    if embedding2 is None:
        result["error"] = "No face detected in second image (selfie)"
        return result
    
    # Compute similarity
    result["similarity_score"] = compare_embeddings(embedding1, embedding2)
    
    return result


def verify_identity(
    id_card_image: np.ndarray, 
    selfie_image: np.ndarray,
    check_liveness: bool = True
) -> Dict:
    """
    Verify identity by comparing ID card face with selfie.
    
    This is the main verification function that:
    1. Performs liveness check on selfie (if enabled) - NON-BLOCKING
    2. Extracts face from ID card
    3. Extracts face from selfie
    4. Computes similarity score
    
    Note: Liveness check is non-blocking - verification continues even
    if liveness fails. The result is returned as a warning.
    
    Args:
        id_card_image: ID card image (BGR format)
        selfie_image: Selfie image (BGR format)
        check_liveness: Whether to perform liveness check (default: True)
        
    Returns:
        Dictionary containing:
        - similarity_score: Float between 0.0 and 1.0
        - id_card_face_detected: Boolean
        - selfie_face_detected: Boolean
        - liveness: Liveness detection result (if enabled)
        - error: String if any error occurred
    """
    # Perform liveness check on selfie (non-blocking)
    liveness_result = None
    if check_liveness:
        try:
            from .liveness_service import detect_spoof, is_liveness_enabled
            if is_liveness_enabled():
                liveness_result = detect_spoof(selfie_image)
        except ImportError:
            # Liveness service not available, continue without it
            pass
        except Exception as e:
            # Liveness check failed, continue with verification
            liveness_result = {
                "is_live": False,
                "confidence": 0.0,
                "spoof_probability": 1.0,
                "checks": {},
                "error": f"Liveness check error: {str(e)}"
            }
    
    # Perform face comparison
    result = compare_faces(id_card_image, selfie_image)
    
    # Same-source detection: If similarity is TOO high (>95%), 
    # it's likely the selfie is cropped from the ID card itself
    SAME_SOURCE_THRESHOLD = 0.95
    similarity = result["similarity_score"]
    
    if liveness_result is not None and similarity > SAME_SOURCE_THRESHOLD:
        # Update liveness result to reflect same-source detection
        liveness_result["checks"]["same_source"] = {
            "passed": False,
            "score": float(round(similarity, 3)),
            "threshold": float(SAME_SOURCE_THRESHOLD)
        }
        # Recalculate confidence with the additional failed check
        passed_count = sum(1 for c in liveness_result["checks"].values() if c.get("passed", False))
        total_checks = len(liveness_result["checks"])
        new_confidence = passed_count / total_checks if total_checks > 0 else 0.0
        
        liveness_result["confidence"] = float(round(new_confidence, 3))
        liveness_result["spoof_probability"] = float(round(1.0 - new_confidence, 3))
        liveness_result["is_live"] = bool(new_confidence >= 0.7)  # Use 70% threshold
        
        if not liveness_result.get("error"):
            liveness_result["error"] = "Possible ID card photo crop detected (similarity too high)"
    
    # Return combined result
    return {
        "similarity_score": result["similarity_score"],
        "id_card_face_detected": result["image1_face_detected"],
        "selfie_face_detected": result["image2_face_detected"],
        "liveness": liveness_result,
        "error": result["error"]
    }


def verify_from_paths(
    id_card_path: str, 
    selfie_path: str
) -> Dict:
    """
    Verify identity from image file paths.
    
    Args:
        id_card_path: Path to ID card image
        selfie_path: Path to selfie image
        
    Returns:
        Verification result dictionary
    """
    id_card_image = cv2.imread(id_card_path)
    if id_card_image is None:
        return {
            "similarity_score": 0.0,
            "id_card_face_detected": False,
            "selfie_face_detected": False,
            "error": f"Could not read ID card image: {id_card_path}"
        }
    
    selfie_image = cv2.imread(selfie_path)
    if selfie_image is None:
        return {
            "similarity_score": 0.0,
            "id_card_face_detected": False,
            "selfie_face_detected": False,
            "error": f"Could not read selfie image: {selfie_path}"
        }
    
    return verify_identity(id_card_image, selfie_image)


def is_ready() -> bool:
    """
    Check if the face recognition service is ready.
    
    This initializes the model if needed.
    """
    if not insightface_available():
        return False
    
    try:
        get_face_extractor()
        return True
    except Exception:
        return False
