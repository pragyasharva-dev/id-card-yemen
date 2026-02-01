"""
Layout Detection Service using YOLOv8.

Detects field regions on Yemen ID cards (front/back) using trained YOLO models.
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


# Label mapping from training (must match classes.txt order)
YOLO_LABELS = [
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
    Service for detecting layout fields on ID cards using YOLOv8.
    
    Loads trained models for:
    - Yemen ID Front (yemen_id_front.pt)
    - Yemen ID Back (yemen_id_back.pt)
    """
    
    _instance: Optional['LayoutService'] = None
    _initialized: bool = False
    
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
        self.base_path = Path(__file__).parent.parent / "models"
        
        if not ULTRALYTICS_AVAILABLE:
            logger.warning("YOLO layout detection disabled - ultralytics not installed")
            LayoutService._initialized = True
            return
        
        # Load available models
        self._load_model("yemen_id_front", self.base_path / "yemen_id_front.pt")
        self._load_model("yemen_id_back", self.base_path / "yemen_id_back.pt")
        
        LayoutService._initialized = True
        
    def _load_model(self, model_key: str, model_path: Path) -> None:
        """Load a YOLO model if the file exists."""
        if not model_path.exists():
            logger.info(f"Model not found: {model_path} (skipping)")
            return
            
        try:
            logger.info(f"Loading YOLO model: {model_key} from {model_path}")
            self.models[model_key] = YOLO(str(model_path))
            logger.info(f"Successfully loaded {model_key}")
        except Exception as e:
            logger.error(f"Failed to load {model_key}: {e}")
    
    def is_available(self, model_key: str = "yemen_id_front") -> bool:
        """Check if a specific model is available."""
        return model_key in self.models
    
    def detect_layout(
        self, 
        image: np.ndarray, 
        model_key: str = "yemen_id_front",
        conf_threshold: float = 0.5
    ) -> Dict[str, LayoutField]:
        """
        Run YOLO detection on an image.
        
        Args:
            image: Input image (BGR format, as from cv2.imread)
            model_key: Which model to use ("yemen_id_front" or "yemen_id_back")
            conf_threshold: Minimum confidence to accept a detection
            
        Returns:
            Dictionary mapping label_name -> LayoutField
            
        Example:
            >>> layout = service.detect_layout(image, "yemen_id_front")
            >>> if "unique_id" in layout:
            ...     id_crop = layout["unique_id"].crop
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
            
            if not results or len(results) == 0:
                return {}
            
            det_result = results[0]
            fields: Dict[str, LayoutField] = {}
            
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
                
                # Keep highest confidence detection for each label
                if label not in fields or conf > fields[label].confidence:
                    fields[label] = LayoutField(
                        label=label,
                        confidence=conf,
                        box=(x1, y1, x2, y2),
                        crop=crop
                    )
            
            logger.debug(f"Detected {len(fields)} fields: {list(fields.keys())}")
            return fields
            
        except Exception as e:
            logger.error(f"Error during layout detection: {e}")
            return {}
    
    def get_detected_labels(self) -> List[str]:
        """Return list of all possible labels the model can detect."""
        return YOLO_LABELS.copy()


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
