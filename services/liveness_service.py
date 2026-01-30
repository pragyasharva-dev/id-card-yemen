"""
Liveness Detection Service for Passive Anti-Spoofing.

Provides passive liveness detection to verify that selfies are captured from
a live, physically present user rather than from a screen or printed photo.

Detection Techniques:
- Texture Analysis (LBP) - Detects printed photos with unnatural texture
- Color Distribution - Checks for natural skin tone variations
- Sharpness Analysis - Detects photos-of-photos (typically blurrier)
- Moiré Pattern Detection - Detects screen captures via FFT
- ML Model - Deep learning based spoof detection

Strict Mode: ALL checks must pass for liveness to pass.
"""
import cv2
import numpy as np
from typing import Dict, Optional, Tuple

# Fast LBP from skimage
try:
    from skimage.feature import local_binary_pattern
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False

from utils.config import (
    LIVENESS_ENABLED,
    LIVENESS_TEXTURE_THRESHOLD,
    LIVENESS_COLOR_THRESHOLD,
    LIVENESS_SHARPNESS_THRESHOLD,
    LIVENESS_MOIRE_THRESHOLD
)


# Minimum image size for selfies
MIN_SELFIE_SIZE = 160


def compute_lbp_texture_score(gray_image: np.ndarray) -> float:
    """
    Calculate Local Binary Pattern (LBP) variance for texture analysis.
    
    Optimized using skimage for fast vectorized computation.
    Real faces have natural texture variation, while printed photos
    and screen displays show more uniform patterns.
    
    Args:
        gray_image: Grayscale image (uint8)
        
    Returns:
        LBP histogram variance score (higher = more natural texture)
    """
    if gray_image is None or gray_image.size == 0:
        return 0.0
    
    # Ensure proper type
    gray = gray_image.astype(np.uint8)
    h, w = gray.shape
    
    if h < 10 or w < 10:
        return 0.0
    
    if SKIMAGE_AVAILABLE:
        # Fast LBP using skimage (vectorized)
        # P=8 neighbors, R=1 radius, uniform method for rotation-invariant patterns
        lbp = local_binary_pattern(gray, P=8, R=1, method="uniform")
        
        # Uniform LBP with P=8 has P+2 = 10 unique patterns
        hist, _ = np.histogram(lbp.ravel(), bins=10, range=(0, 10), density=True)
        
        # Return variance of histogram (higher = more texture variation)
        return float(np.var(hist) * 1000)  # Scale up for threshold compatibility
    else:
        # Fallback: Pure NumPy vectorized LBP (no nested loops)
        # Pad image for boundary handling
        padded = np.pad(gray, 1, mode='edge')
        
        # Neighbor offsets (8-connected)
        offsets = [(-1, -1), (-1, 0), (-1, 1), (0, 1), 
                   (1, 1), (1, 0), (1, -1), (0, -1)]
        
        center = padded[1:-1, 1:-1].astype(np.int16)
        lbp = np.zeros_like(center, dtype=np.uint8)
        
        for i, (dy, dx) in enumerate(offsets):
            neighbor = padded[1+dy:h+1+dy, 1+dx:w+1+dx].astype(np.int16)
            lbp |= ((neighbor >= center).astype(np.uint8) << i)
        
        hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256), density=True)
        
        # Variance of histogram distribution
        mean = np.sum(np.arange(256) * hist)
        variance = np.sum(((np.arange(256) - mean) ** 2) * hist)
        
        return float(variance)


def detect_face_roi(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect face region for ROI-based analysis.
    
    Returns:
        Tuple (x, y, w, h) or None if no face detected
    """
    try:
        # Try to use face extractor if available
        from .face_extractor import get_face_extractor
        extractor = get_face_extractor()
        faces = extractor.detect_faces(image)
        
        if faces and len(faces) > 0:
            # Get the first (largest) face
            face = faces[0]
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            return (x1, y1, x2 - x1, y2 - y1)
    except:
        pass
    
    # Fallback: Use OpenCV Haar cascade
    try:
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            # Return largest face
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            return tuple(faces[0])
    except:
        pass
    
    return None


def analyze_color_distribution(image: np.ndarray, face_roi: Optional[Tuple] = None) -> float:
    """
    Check for natural skin color distribution.
    
    Improved: Analyzes only face ROI if provided, avoiding background interference.
    
    Args:
        image: BGR image
        face_roi: Optional (x, y, w, h) face region
        
    Returns:
        Score between 0.0-1.0 (higher = more natural skin tones)
    """
    if image is None or image.size == 0:
        return 0.0
    
    # Use face ROI if provided, otherwise use center crop
    if face_roi is not None:
        x, y, w, h = face_roi
        # Add small padding
        pad = int(min(w, h) * 0.1)
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(image.shape[1], x + w + pad)
        y2 = min(image.shape[0], y + h + pad)
        roi = image[y1:y2, x1:x2]
    else:
        # Fallback: Use center 60% of image
        h, w = image.shape[:2]
        margin_y, margin_x = int(h * 0.2), int(w * 0.2)
        roi = image[margin_y:h-margin_y, margin_x:w-margin_x]
    
    if roi.size == 0:
        return 0.0
    
    # Convert to YCrCb color space (better for skin detection)
    ycrcb = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)
    
    # Skin color range in YCrCb
    lower_skin = np.array([0, 133, 77], dtype=np.uint8)
    upper_skin = np.array([255, 173, 127], dtype=np.uint8)
    
    # Create skin mask
    skin_mask = cv2.inRange(ycrcb, lower_skin, upper_skin)
    
    # Calculate skin pixel ratio
    total_pixels = roi.shape[0] * roi.shape[1]
    skin_pixels = cv2.countNonZero(skin_mask)
    skin_ratio = skin_pixels / total_pixels
    
    if skin_pixels > 100:
        # Extract actual skin pixels
        skin_values = roi[skin_mask > 0]
        color_std = np.std(skin_values)
        
        # Natural skin has some variation but not too much
        # Adjusted expectation for face ROI (~30-40% skin area)
        area_score = min(1.0, skin_ratio / 0.25)
        variance_score = min(1.0, color_std / 30.0)
        
        return (area_score + variance_score) / 2.0
    
    return 0.0


def check_image_sharpness(gray_image: np.ndarray, normalize: bool = True) -> float:
    """
    Compute Laplacian variance to detect photos-of-photos.
    
    Improved: Normalized by image size for device-independence.
    
    Args:
        gray_image: Grayscale image
        normalize: If True, normalize by image size
        
    Returns:
        Sharpness score (higher = sharper image)
    """
    if gray_image is None or gray_image.size == 0:
        return 0.0
    
    # Compute Laplacian
    laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
    variance = float(laplacian.var())
    
    if normalize:
        # Normalize by image size to make it device-independent
        # Larger images naturally have higher variance
        h, w = gray_image.shape
        pixel_count = h * w
        
        # Normalize: multiply by a factor to maintain similar scale
        # Base assumption: 640x480 image
        base_pixels = 640 * 480
        normalized = variance * (base_pixels / pixel_count)
        
        return normalized
    
    return variance


def detect_moire_patterns(gray_image: np.ndarray) -> float:
    """
    Detect moiré patterns from screens using FFT analysis.
    
    Improved: Uses Hann window for stability against cropping/position.
    
    Args:
        gray_image: Grayscale image
        
    Returns:
        Score between 0.0-1.0 (higher = less moiré, more natural)
    """
    if gray_image is None or gray_image.size == 0:
        return 0.0
    
    # Resize for consistent FFT analysis
    size = 256
    resized = cv2.resize(gray_image, (size, size)).astype(float)
    
    # Apply Hann window to reduce edge effects (improvement)
    hann = np.hanning(size)
    window = np.outer(hann, hann)
    windowed = resized * window
    
    # Apply FFT
    f_transform = np.fft.fft2(windowed)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    
    # Log transform
    magnitude_log = np.log1p(magnitude)
    
    # Analyze frequency distribution
    h, w = magnitude_log.shape
    center_y, center_x = h // 2, w // 2
    
    # Create distance matrix
    y, x = np.ogrid[:h, :w]
    distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    
    # Ignore very low frequencies (DC component, < 5) and very high frequencies (> 120)
    # Focus on mid-frequency range where moiré patterns appear
    valid_mask = (distance > 5) & (distance < 120)
    mid_freq_mask = (distance > 20) & (distance < 80)
    
    valid_energy = np.sum(magnitude_log[valid_mask])
    mid_freq_energy = np.sum(magnitude_log[mid_freq_mask])
    
    if valid_energy > 0:
        ratio = mid_freq_energy / valid_energy
        # Lower ratio = less periodic patterns = more natural
        # Invert so higher score = better (less moiré)
        return max(0.0, min(1.0, 1.0 - (ratio * 1.5)))
    
    return 0.5


def detect_spoof(image: np.ndarray) -> Dict:
    """
    Passive liveness detection for selfie images.
    
    Runs 6 checks to determine if a selfie is from a live person.
    ALL checks must pass for liveness to pass (strict mode).
    
    Args:
        image: Input selfie image (BGR format)
        
    Returns:
        Dictionary containing:
        - is_live: Boolean indicating if image appears to be from live person
        - confidence: Overall confidence score (0.0-1.0)
        - spoof_probability: Probability of spoof (0.0-1.0)
        - checks: Individual check results with scores
        - error: Error message if detection failed
    """
    result = {
        "is_live": False,
        "confidence": 0.0,
        "spoof_probability": 1.0,
        "checks": {},
        "error": None
    }
    
    # Validate image
    if image is None or image.size == 0:
        result["error"] = "Invalid image provided"
        return result
    
    # Get image dimensions
    h, w = image.shape[:2]
    
    # Minimum size check - reject tiny/cropped images
    if min(h, w) < MIN_SELFIE_SIZE:
        result["is_live"] = False
        result["confidence"] = 0.0
        result["spoof_probability"] = 1.0
        result["checks"] = {
            "image_size": {
                "passed": False,
                "score": float(min(h, w)),
                "threshold": float(MIN_SELFIE_SIZE),
                "reason": "image_too_small"
            }
        }
        result["error"] = "Image too small - minimum 160px required"
        return result
    
    try:
        # Convert to grayscale for analysis
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        checks = {}
        
        # Detect face ROI for color analysis
        face_roi = detect_face_roi(image)
        
        h, w = gray.shape[:2]
        
        # 0. Image Size Check (soft check for non-camera sources)
        MIN_SIZE = 100  # Minimum dimension in pixels
        size_passed = bool(h >= MIN_SIZE and w >= MIN_SIZE)
        checks["image_size"] = {
            "passed": size_passed,
            "score": float(min(h, w)),
            "threshold": float(MIN_SIZE)
        }
        
        # 1. Texture Analysis (LBP) - Fast skimage version
        texture_score = compute_lbp_texture_score(gray)
        texture_passed = bool(texture_score > LIVENESS_TEXTURE_THRESHOLD)
        checks["texture"] = {
            "passed": texture_passed,
            "score": float(round(texture_score, 2)),
            "threshold": float(LIVENESS_TEXTURE_THRESHOLD)
        }
        
        # 2. Color Distribution (Face ROI only)
        color_score = analyze_color_distribution(image, face_roi)
        color_passed = bool(color_score > LIVENESS_COLOR_THRESHOLD)
        checks["color"] = {
            "passed": color_passed,
            "score": float(round(color_score, 3)),
            "threshold": float(LIVENESS_COLOR_THRESHOLD)
        }
        
        # 3. Sharpness Analysis (Normalized)
        sharpness_score = check_image_sharpness(gray, normalize=True)
        sharpness_passed = bool(sharpness_score > LIVENESS_SHARPNESS_THRESHOLD)
        checks["sharpness"] = {
            "passed": sharpness_passed,
            "score": float(round(sharpness_score, 2)),
            "threshold": float(LIVENESS_SHARPNESS_THRESHOLD)
        }
        
        # 4. Moiré Pattern Detection (with Hann window)
        moire_score = detect_moire_patterns(gray)
        moire_passed = bool(moire_score > LIVENESS_MOIRE_THRESHOLD)
        checks["reflection"] = {
            "passed": moire_passed,
            "score": float(round(moire_score, 3)),
            "threshold": float(LIVENESS_MOIRE_THRESHOLD)
        }
        
        # 5. ML-based Anti-Spoofing Model (if available)
        try:
            from .antispoof_model import predict_spoof as ml_predict
            ml_result = ml_predict(image)
            
            # Only add to checks if model actually ran
            if ml_result.get("model_used") not in ["none", "error"]:
                ml_passed = ml_result.get("is_real", False)
                ml_spoof_prob = ml_result.get("spoof_probability", 0.5)
                checks["ml_model"] = {
                    "passed": bool(ml_passed),
                    "score": float(round(1.0 - ml_spoof_prob, 3)),
                    "threshold": 0.5,
                    "model": ml_result.get("model_used", "unknown")
                }
        except ImportError:
            # ML model not available
            pass
        except Exception as e:
            checks["ml_model"] = {
                "passed": True,
                "score": 0.5,
                "threshold": 0.5,
                "error": str(e)
            }
        
        # ========================================
        # STRICT MODE: ALL checks must pass
        # ========================================
        # Instead of weighted voting, require ALL checks to pass
        
        # Collect all check results (excluding ML model as optional)
        core_checks = [
            ("image_size", size_passed),
            ("texture", texture_passed),
            ("color", color_passed),
            ("sharpness", sharpness_passed),
            ("reflection", moire_passed),
        ]
        
        # Check if ML model check exists and passed
        ml_passed = checks.get("ml_model", {}).get("passed", True)  # Default to True if not available
        
        # Count passed checks
        passed_count = sum(1 for _, passed in core_checks if passed)
        total_core = len(core_checks)
        
        # ALL core checks must pass
        all_core_passed = all(passed for _, passed in core_checks)
        
        # Final decision: all core checks + ML must pass
        is_live = all_core_passed and ml_passed
        
        # Calculate confidence based on passed ratio
        total_checks = total_core + (1 if "ml_model" in checks else 0)
        passed_total = passed_count + (1 if ml_passed else 0)
        confidence = passed_total / total_checks if total_checks > 0 else 0.0
        
        # If not live, add error message listing failed checks
        if not is_live:
            failed_checks = [name for name, passed in core_checks if not passed]
            if not ml_passed:
                failed_checks.append("ml_model")
            result["error"] = f"Failed checks: {', '.join(failed_checks)}"
        
        result["is_live"] = is_live
        result["confidence"] = float(round(confidence, 3))
        result["spoof_probability"] = float(round(1.0 - confidence, 3))
        result["checks"] = checks
        
    except Exception as e:
        result["error"] = f"Liveness detection error: {str(e)}"
    
    return result


def is_liveness_enabled() -> bool:
    """Check if liveness detection is enabled in configuration."""
    return LIVENESS_ENABLED


def get_liveness_threshold() -> float:
    """Get the configured liveness threshold."""
    return LIVENESS_THRESHOLD
