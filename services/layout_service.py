"""
Layout Detection Service using YOLOv8.

Detects field regions on Yemen documents using trained YOLO models:
- Yemen National ID (Front/Back)
- Yemen Passport

Returns cropped regions for each detected field to enable targeted OCR.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Try to import ultralytics, fail gracefully if not installed
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    logger.warning("ultralytics not installed. Layout detection disabled.")


# Default labels for National ID (used if model doesn't provide names)
# These are loaded dynamically from each model at runtime
DEFAULT_ID_LABELS = [
    "DOB",               # 0
    "POB",               # 1
    "expiry_data",       # 2
    "id_card",           # 3
    "issue_date",        # 4
    "issuing_authority", # 5
    "name",              # 6
    "unique_id",         # 7
]


@dataclass
class LayoutField:
    """Represents a detected field region on the ID card."""
    label: str
    confidence: float
    box: Tuple[int, int, int, int]  # x1, y1, x2, y2 (pixel coordinates)
    crop: np.ndarray  # Cropped image region


class LayoutService:
    """
    Service for detecting layout fields on Yemen documents using YOLOv8.
    
    Loads trained models for:
    - Yemen ID Front (north-yemen-front.pt)
    - Yemen ID Back (north-yemen-back.pt)
    - Yemen Passport (yemen-passport.pt)
    
    Usage:
        service = get_layout_service()
        
        # For National ID
        front_fields = service.detect_layout(image, "yemen_id_front")
        back_fields = service.detect_layout(image, "yemen_id_back")
        
        # For Passport (use return_all=True for multiple MRZ lines)
        passport_fields = service.detect_layout(image, "yemen_passport", return_all=True)
    """
    
    _instance: Optional['LayoutService'] = None
    _initialized: bool = False
    _init_error: Optional[str] = None
    _ultralytics_available: bool = False
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize YOLO models if not already done."""
        if LayoutService._initialized:
            return
            
        self.models: Dict[str, 'YOLO'] = {}
        self.model_classes: Dict[str, List[str]] = {}
        self.base_path = Path(__file__).parent.parent / "models"
        
        LayoutService._ultralytics_available = ULTRALYTICS_AVAILABLE
        
        if not ULTRALYTICS_AVAILABLE:
            msg = "YOLO layout detection disabled - ultralytics not installed"
            print(f"[DEBUG] {msg}")
            LayoutService._init_error = msg
            LayoutService._initialized = True
            return
        
        # Load available models
        # Yemen National ID (North Yemen)
        logger.info(f"LayoutService initializing. Base path: {self.base_path}")
        self._load_model("yemen_id_front", self.base_path / "north-yemen-front.pt")
        self._load_model("yemen_id_back", self.base_path / "north-yemen-back.pt")
        # Yemen Passport
        self._load_model("yemen_passport", self.base_path / "yemen-passport.pt")
        
        logger.info(f"LayoutService initialized. Cached models: {list(self.models.keys())}")
        LayoutService._initialized = True
        
    def _load_model(self, model_key: str, model_path: Path) -> None:
        """Load a YOLO model if the file exists and extract class names."""
        if not model_path.exists():
            logger.info(f"Model not found: {model_path} (skipping)")
            return
            
        try:
            logger.info(f"Loading YOLO model: {model_key} from {model_path}")
            model = YOLO(str(model_path))
            self.models[model_key] = model
            
            # Extract class names from model metadata (dynamic loading)
            if hasattr(model, 'names') and model.names:
                # model.names is a dict {0: 'class_0', 1: 'class_1', ...}
                class_names = [model.names[i] for i in sorted(model.names.keys())]
                self.model_classes[model_key] = class_names
                logger.info(f"  Classes: {class_names}")
            else:
                # Fallback to defaults
                self.model_classes[model_key] = DEFAULT_ID_LABELS.copy()
                logger.info(f"  Using default classes (model has no .names)")
                
            logger.info(f"Successfully loaded {model_key}")
        except Exception as e:
            logger.error(f"Failed to load {model_key}: {e}")
    
    def is_available(self, model_key: str = "yemen_id_front") -> bool:
        """Check if a specific model is available."""
        return model_key in self.models
    
    def get_status(self) -> Dict:
        """Return diagnostic information about the service."""
        return {
            "initialized": LayoutService._initialized,
            "ultralytics_available": LayoutService._ultralytics_available,
            "error": LayoutService._init_error,
            "loaded_models": list(self.models.keys()),
            "base_path": str(self.base_path),
            "base_path_exists": self.base_path.exists()
        }
    
    def detect_layout(
        self, 
        image: np.ndarray, 
        model_key: str = "yemen_id_front",
        conf_threshold: float = 0.5,
        return_all: bool = False
    ) -> Dict[str, LayoutField]:
        """
        Run YOLO detection on an image.
        
        Args:
            image: Input image (BGR format, as from cv2.imread)
            model_key: Which model to use:
                - "yemen_id_front": National ID front side
                - "yemen_id_back": National ID back side
                - "yemen_passport": Passport document
            conf_threshold: Minimum confidence to accept a detection
            return_all: If True, returns Dict[str, List[LayoutField]] with ALL
                        detections per label (useful for multiple MRZ lines).
                        If False (default), returns only the highest confidence
                        detection per label.
            
        Returns:
            Dictionary mapping label_name -> LayoutField (or List[LayoutField] if return_all=True)
            
        Example:
            >>> layout = service.detect_layout(image, "yemen_id_front")
            >>> if "unique_id" in layout:
            ...     id_crop = layout["unique_id"].crop
            
            >>> # For passport MRZ (multiple lines with same label)
            >>> passport_layout = service.detect_layout(image, "yemen_passport", return_all=True)
            >>> mrz_fields = passport_layout.get("mrz", [])
            >>> mrz_fields.sort(key=lambda f: f.box[1])  # Sort by Y coordinate
        """
        if not ULTRALYTICS_AVAILABLE:
            return {}
            
        if model_key not in self.models:
            logger.debug(f"Model {model_key} not loaded, returning empty layout")
            return {}
        
        try:
            # Run inference
            results = self.models[model_key].predict(
                image,
                conf=conf_threshold,
                verbose=False
            )
            
            logger.info(f"YOLO inference ran. Results found: {len(results) if results else 0}")
            
            if not results or len(results) == 0:
                logger.warning("YOLO inference returned no results object")
                return {}
            
            det_result = results[0]
            logger.info(f"YOLO detections: {len(det_result.boxes)}")
            fields = {}  # Type depends on return_all
            
            h, w = image.shape[:2]
            
            for box in det_result.boxes:
                # Get class ID and label
                cls_id = int(box.cls[0])
                label = det_result.names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf[0])
                
                # Get bounding box coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Clamp coordinates to image bounds
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                
                # Skip invalid boxes
                if x2 <= x1 or y2 <= y1:
                    continue
                
                # Add padding to help OCR read edge characters (5% of box size)
                pad_x = int((x2 - x1) * 0.05)
                pad_y = int((y2 - y1) * 0.05)
                
                # Apply padding while staying in bounds
                x1_padded = max(0, x1 - pad_x)
                y1_padded = max(0, y1 - pad_y)
                x2_padded = min(w, x2 + pad_x)
                y2_padded = min(h, y2 + pad_y)
                
                # Crop the region with padding
                crop = image[y1_padded:y2_padded, x1_padded:x2_padded].copy()
                
                field_obj = LayoutField(
                    label=label,
                    confidence=conf,
                    box=(x1, y1, x2, y2),
                    crop=crop
                )
                
                if return_all:
                    # Collect ALL detections per label
                    if label not in fields:
                        fields[label] = []
                    fields[label].append(field_obj)
                else:
                    # Keep highest confidence detection for each label
                    if label not in fields or conf > fields[label].confidence:
                        fields[label] = field_obj
            
            logger.debug(f"Detected {len(fields)} fields: {list(fields.keys())}")
            return fields
            
        except Exception as e:
            logger.error(f"Error during layout detection: {e}")
            return {}
    
    def get_detected_labels(self, model_key: str = "yemen_id_front") -> List[str]:
        """
        Return list of all possible labels the specified model can detect.
        
        Args:
            model_key: Which model to get labels for
            
        Returns:
            List of class names from the model
        """
        if model_key in self.model_classes:
            return self.model_classes[model_key].copy()
        return DEFAULT_ID_LABELS.copy()


# Singleton accessor
_service: Optional[LayoutService] = None


def get_layout_service() -> LayoutService:
    """Get the singleton LayoutService instance."""
    global _service
    if _service is None:
        _service = LayoutService()
    return _service


def is_layout_available(model_key: str = "yemen_id_front") -> bool:
    """Check if layout detection is available for a model."""
    return get_layout_service().is_available(model_key)


def detect_passport_layout(image: np.ndarray, conf_threshold: float = 0.5, return_all: bool = True) -> Dict[str, LayoutField]:
    """
    Convenience function to detect layout fields on a Yemen passport.
    
    Args:
        image: Passport image (BGR format)
        conf_threshold: Minimum confidence threshold
        return_all: If True (default), returns all detections per label
                    (needed for multiple MRZ lines)
        
    Returns:
        Dictionary mapping field_name -> LayoutField or List[LayoutField]
    """
    return get_layout_service().detect_layout(image, "yemen_passport", conf_threshold, return_all)


def detect_id_front_layout(image: np.ndarray, conf_threshold: float = 0.5) -> Dict[str, LayoutField]:
    """
    Convenience function to detect layout fields on Yemen ID front side.
    
    Args:
        image: ID card front image (BGR format)
        conf_threshold: Minimum confidence threshold
        
    Returns:
        Dictionary mapping field_name -> LayoutField
    """
    return get_layout_service().detect_layout(image, "yemen_id_front", conf_threshold)


def detect_id_back_layout(image: np.ndarray, conf_threshold: float = 0.5) -> Dict[str, LayoutField]:
    """
    Convenience function to detect layout fields on Yemen ID back side.
    
    Args:
        image: ID card back image (BGR format)
        conf_threshold: Minimum confidence threshold
        
    Returns:
        Dictionary mapping field_name -> LayoutField
    """
    return get_layout_service().detect_layout(image, "yemen_id_back", conf_threshold)
