"""
Anti-Spoofing Model Service using ONNX Runtime.

Provides ML-based face anti-spoofing detection using a pre-trained model.
This can be used alongside or instead of the basic passive liveness checks.

Model: Uses a MobileNet-based binary classifier trained on face anti-spoofing datasets.
The model outputs a spoof probability (0.0 = real, 1.0 = spoof).

If no pre-trained model is available, falls back to basic checks.
"""
import cv2
import logging
import numpy as np
from typing import Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import ONNX Runtime
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ort = None


class AntiSpoofModel:
    """Anti-spoofing model using ONNX Runtime."""
    
    _instance: Optional["AntiSpoofModel"] = None
    _session: Optional["ort.InferenceSession"] = None
    _model_path: Optional[Path] = None
    
    # Model input size (matches MiniFASNetV2SE model)
    INPUT_SIZE = (128, 128)  # Width, Height
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the anti-spoof model."""
        if not ONNX_AVAILABLE:
            return
        
        if AntiSpoofModel._session is not None:
            return
        
        # Look for model in models/antispoof directory
        model_dir = Path(__file__).parent.parent / "models" / "antispoof"
        model_files = list(model_dir.glob("*.onnx")) if model_dir.exists() else []
        
        if model_files:
            self._model_path = model_files[0]
            try:
                AntiSpoofModel._session = ort.InferenceSession(
                    str(self._model_path),
                    providers=['CPUExecutionProvider']
                )
            except Exception as e:
                logger.warning(f"Failed to load anti-spoof model: {e}")
                AntiSpoofModel._session = None
    
    def is_available(self) -> bool:
        """Check if the model is loaded and available."""
        return ONNX_AVAILABLE and AntiSpoofModel._session is not None
    
    def preprocess(self, image: np.ndarray, bbox: Optional[Tuple] = None) -> np.ndarray:
        """
        Preprocess image for the model.
        
        Args:
            image: BGR image
            bbox: Optional face bounding box (x1, y1, x2, y2)
            
        Returns:
            Preprocessed tensor ready for inference
        """
        # If bbox provided, crop to face region
        if bbox is not None:
            x1, y1, x2, y2 = [int(v) for v in bbox]
            # Add padding
            h, w = image.shape[:2]
            pad_x = int((x2 - x1) * 0.2)
            pad_y = int((y2 - y1) * 0.2)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w, x2 + pad_x)
            y2 = min(h, y2 + pad_y)
            image = image[y1:y2, x1:x2]
        
        # Resize to model input size
        resized = cv2.resize(image, self.INPUT_SIZE)
        
        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1]
        normalized = rgb.astype(np.float32) / 255.0
        
        # Transpose to NCHW format (batch, channels, height, width)
        transposed = np.transpose(normalized, (2, 0, 1))
        
        # Add batch dimension
        batched = np.expand_dims(transposed, axis=0)
        
        return batched
    
    def predict(self, image: np.ndarray, bbox: Optional[Tuple] = None) -> Dict:
        """
        Predict if the face is real or spoofed.
        
        Args:
            image: BGR face image
            bbox: Optional face bounding box
            
        Returns:
            Dictionary with:
            - is_real: Boolean indicating if face is real
            - spoof_probability: Float 0.0-1.0
            - confidence: Float 0.0-1.0
            - model_used: String indicating model name
        """
        result = {
            "is_real": True,
            "spoof_probability": 0.0,
            "confidence": 0.5,
            "model_used": "none"
        }
        
        if not self.is_available():
            result["model_used"] = "fallback"
            # Use basic analysis as fallback
            return self._fallback_prediction(image)
        
        try:
            # Preprocess
            input_tensor = self.preprocess(image, bbox)
            
            # Get input name
            input_name = AntiSpoofModel._session.get_inputs()[0].name
            
            # Run inference
            outputs = AntiSpoofModel._session.run(None, {input_name: input_tensor})
            
            # Parse output - MiniFASNetV2SE outputs raw logits [real, spoof]
            if len(outputs) > 0:
                output = outputs[0]
                
                if output.shape[-1] == 2:
                    # Two-class output: [real_logit, spoof_logit]
                    # Apply softmax to convert to probabilities
                    logits = output[0]
                    exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
                    softmax = exp_logits / np.sum(exp_logits)
                    spoof_prob = float(softmax[1])  # Index 1 = spoof probability
                elif output.shape[-1] == 1:
                    # Single output: apply sigmoid
                    spoof_prob = float(1.0 / (1.0 + np.exp(-output[0][0])))
                else:
                    # Unknown output format
                    spoof_prob = 0.5
                
                # Clamp values to valid range
                spoof_prob = max(0.0, min(1.0, spoof_prob))
                
                result["spoof_probability"] = round(spoof_prob, 4)
                result["is_real"] = spoof_prob < 0.5
                result["confidence"] = round(abs(spoof_prob - 0.5) * 2, 4)
                result["model_used"] = self._model_path.name if self._model_path else "onnx"
                
        except Exception as e:
            result["error"] = str(e)
            result["model_used"] = "error"
        
        return result
    
    def _fallback_prediction(self, image: np.ndarray) -> Dict:
        """
        Enhanced fallback prediction using multiple image analysis techniques.
        Used when no ML model is available. Combines multiple signals:
        - Sharpness (Laplacian variance)
        - Frequency analysis (high-frequency content)
        - Edge density
        - Color variance
        """
        result = {
            "is_real": True,
            "spoof_probability": 0.3,  # Default to likely real
            "confidence": 0.5,
            "model_used": "enhanced_fallback"
        }
        
        if image is None or image.size == 0:
            result["is_real"] = False
            result["spoof_probability"] = 1.0
            return result
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            
            scores = []
            
            # 1. Laplacian variance (sharpness) - more lenient thresholds
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var > 200:
                scores.append(0.1)  # Very sharp = likely real
            elif laplacian_var > 50:
                scores.append(0.25)  # Good sharpness
            elif laplacian_var > 20:
                scores.append(0.4)  # Acceptable (filtered images)
            else:
                scores.append(0.7)  # Too blurry = likely spoof
            
            # 2. High-frequency content analysis (FFT) - more lenient
            f = np.fft.fft2(gray)
            fshift = np.fft.fftshift(f)
            magnitude = np.abs(fshift)
            center_size = min(h, w) // 4
            center_h, center_w = h // 2, w // 2
            high_freq = np.sum(magnitude) - np.sum(
                magnitude[center_h-center_size:center_h+center_size,
                         center_w-center_size:center_w+center_size]
            )
            total_freq = np.sum(magnitude)
            high_freq_ratio = high_freq / (total_freq + 1e-6)
            
            if high_freq_ratio > 0.7:
                scores.append(0.15)  # Rich high-freq = real
            elif high_freq_ratio > 0.4:
                scores.append(0.3)   # Acceptable
            else:
                scores.append(0.6)   # Low high-freq = possible spoof
            
            # 3. Edge density (Canny) - more lenient
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / (h * w)
            
            if edge_density > 0.1:
                scores.append(0.15)
            elif edge_density > 0.05:
                scores.append(0.3)
            else:
                scores.append(0.55)
            
            # 4. Color saturation (HSV) - more lenient
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            saturation = hsv[:, :, 1]
            sat_std = np.std(saturation)
            
            if sat_std > 35:
                scores.append(0.15)  # High variation = real
            elif sat_std > 15:
                scores.append(0.3)   # Acceptable
            else:
                scores.append(0.6)   # Low variation = possible spoof
            
            # Combine scores
            spoof_prob = sum(scores) / len(scores) if scores else 0.5
            
            result["spoof_probability"] = float(round(spoof_prob, 3))
            result["is_real"] = spoof_prob < 0.5
            result["confidence"] = float(round(0.6 + (0.3 * abs(spoof_prob - 0.5)), 3))
            
        except Exception as e:
            result["error"] = str(e)
            result["confidence"] = 0.3
        
        return result


# Singleton instance
_model: Optional[AntiSpoofModel] = None


def get_antispoof_model() -> AntiSpoofModel:
    """Get the singleton anti-spoof model instance."""
    global _model
    if _model is None:
        _model = AntiSpoofModel()
    return _model


def predict_spoof(image: np.ndarray, bbox: Optional[Tuple] = None) -> Dict:
    """
    Predict if an image contains a real face or a spoof.
    
    Args:
        image: BGR image
        bbox: Optional face bounding box (x1, y1, x2, y2)
        
    Returns:
        Dictionary with prediction results
    """
    model = get_antispoof_model()
    return model.predict(image, bbox)


def is_model_available() -> bool:
    """Check if the anti-spoof ML model is available."""
    model = get_antispoof_model()
    return model.is_available()
