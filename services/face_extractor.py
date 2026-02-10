"""
Face Extractor Service using InsightFace.

Handles face detection and extraction from ID card images.
Supports offline model loading via INSIGHTFACE_MODEL_DIR config.
"""
import os
import cv2
import logging
import numpy as np
from typing import Optional, Tuple, List
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False
    FaceAnalysis = None

from utils.config import FACE_DETECTION_MODEL, FACE_DETECTION_CTX, INSIGHTFACE_MODEL_DIR
from utils.logging_config import log_execution_time


class FaceExtractor:
    """Service for detecting and extracting faces from images."""
    
    _instance: Optional["FaceExtractor"] = None
    _app: Optional["FaceAnalysis"] = None
    
    def __new__(cls):
        """Singleton pattern to reuse face analysis model."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize InsightFace model if not already done."""
        if not INSIGHTFACE_AVAILABLE:
            raise ImportError(
                "InsightFace is not installed. "
                "Please install it with: pip install insightface onnxruntime"
            )
        
        if FaceExtractor._app is None:
            # Check for local models directory (offline mode)
            # Check for local models directory (offline mode)
            kwargs = {}
            if INSIGHTFACE_MODEL_DIR.exists():
                root = str(INSIGHTFACE_MODEL_DIR)
                # Set environment variable for InsightFace to find models
                os.environ["INSIGHTFACE_HOME"] = root
                kwargs["root"] = root
            
            FaceExtractor._app = FaceAnalysis(
                name=FACE_DETECTION_MODEL,
                providers=['CPUExecutionProvider'],
                **kwargs
            )
            # Prepare for different image sizes
            FaceExtractor._app.prepare(
                ctx_id=FACE_DETECTION_CTX, 
                det_size=(640, 640)
            )
            logger.info(f"InsightFace model '{FACE_DETECTION_MODEL}' loaded successfully")
    
    def detect_faces(self, image: np.ndarray) -> List:
        """
        Detect all faces in an image.
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            List of detected face objects from InsightFace
        """
        faces = self._app.get(image)
        return faces
    
    def get_largest_face(self, image: np.ndarray) -> Optional[object]:
        """
        Get the largest face in an image.
        
        Useful for ID cards where there's typically one main face.
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            Largest face object, or None if no faces detected
        """
        faces = self.detect_faces(image)
        
        if not faces:
            logger.debug("No faces detected in image")
            return None
        
        # Find the largest face by bounding box area
        def face_area(face):
            bbox = face.bbox
            return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        
        if not faces:
            return None
        
        return max(faces, key=face_area)
    
    def extract_face_region(
        self, 
        image: np.ndarray, 
        face: object,
        padding: float = 0.2
    ) -> np.ndarray:
        """
        Extract the face region from an image with padding.
        
        Args:
            image: Input image (BGR format)
            face: Face object from InsightFace
            padding: Percentage of padding to add around the face
            
        Returns:
            Cropped face image
        """
        h, w = image.shape[:2]
        bbox = face.bbox.astype(int)
        
        # Calculate padding
        face_w = bbox[2] - bbox[0]
        face_h = bbox[3] - bbox[1]
        pad_w = int(face_w * padding)
        pad_h = int(face_h * padding)
        
        # Apply padding with bounds checking
        x1 = max(0, bbox[0] - pad_w)
        y1 = max(0, bbox[1] - pad_h)
        x2 = min(w, bbox[2] + pad_w)
        y2 = min(h, bbox[3] + pad_h)
        
        return image[y1:y2, x1:x2].copy()
    
    def get_face_embedding(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Get the face embedding from an image.
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            Face embedding vector, or None if no face detected
        """
        face = self.get_largest_face(image)
        
        if face is None:
            return None
        
        return face.embedding
    
    def extract_face_from_id_card(
        self, 
        image: np.ndarray
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Extract face image and embedding from an ID card.
        
        Args:
            image: ID card image (BGR format)
            
        Returns:
            Tuple of (cropped face image, face embedding)
            Both are None if no face detected
        """
        face = self.get_largest_face(image)
        
        if face is None:
            logger.warning("No face detected on ID card image")
            return None, None
        
        face_img = self.extract_face_region(image, face)
        embedding = face.embedding
        
        return face_img, embedding


# Module-level convenience functions
_extractor: Optional[FaceExtractor] = None


def get_face_extractor() -> FaceExtractor:
    """Get the singleton face extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = FaceExtractor()
    return _extractor


@log_execution_time
def extract_face(image: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Extract face from an image.
    
    Convenience function using the singleton extractor.
    
    Args:
        image: Input image (BGR format)
        
    Returns:
        Tuple of (cropped face image, face embedding)
    """
    extractor = get_face_extractor()
    return extractor.extract_face_from_id_card(image)


def get_embedding(image: np.ndarray) -> Optional[np.ndarray]:
    """
    Get face embedding from an image.
    
    Args:
        image: Input image (BGR format)
        
    Returns:
        Face embedding vector or None
    """
    extractor = get_face_extractor()
    return extractor.get_face_embedding(image)


def is_available() -> bool:
    """Check if InsightFace is available."""
    return INSIGHTFACE_AVAILABLE
