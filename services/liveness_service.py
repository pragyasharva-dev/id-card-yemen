"""
Liveness Detection Service for Passive Anti-Spoofing.

Provides passive liveness detection to verify that selfies are captured from
a live, physically present user rather than from a screen or printed photo.

Detection Techniques:
- Texture Analysis (LBP) - Detects printed photos with unnatural texture
- Color Distribution - Checks for natural skin tone variations
- Sharpness Analysis - Detects photos-of-photos (typically blurrier)
- Moiré Pattern Detection - Detects screen captures via FFT

Note: This is NON-BLOCKING - verification continues even if liveness fails.
The result is returned as a warning to the caller.
"""
import cv2
import numpy as np
from typing import Dict, Optional, Tuple
from scipy import ndimage

from utils.config import (
    LIVENESS_ENABLED,
    LIVENESS_THRESHOLD,
    LIVENESS_TEXTURE_THRESHOLD,
    LIVENESS_COLOR_THRESHOLD,
    LIVENESS_SHARPNESS_THRESHOLD,
    LIVENESS_MOIRE_THRESHOLD
)


def compute_lbp_texture_score(gray_image: np.ndarray) -> float:
    """
    Calculate Local Binary Pattern (LBP) variance for texture analysis.
    
    Real faces have natural texture variation, while printed photos
    and screen displays show more uniform patterns.
    
    Args:
        gray_image: Grayscale image (uint8)
        
    Returns:
        LBP variance score (higher = more natural texture)
    """
    if gray_image is None or gray_image.size == 0:
        return 0.0
    
    # Ensure proper type
    gray = gray_image.astype(np.uint8)
    h, w = gray.shape
    
    if h < 10 or w < 10:
        return 0.0
    
    # Simple LBP computation
    # Compare each pixel with its 8 neighbors
    lbp_image = np.zeros((h - 2, w - 2), dtype=np.uint8)
    
    for i in range(1, h - 1):
        for j in range(1, w - 1):
            center = gray[i, j]
            binary_string = 0
            
            # 8 neighbors in clockwise order
            neighbors = [
                (i-1, j-1), (i-1, j), (i-1, j+1),
                (i, j+1), (i+1, j+1), (i+1, j),
                (i+1, j-1), (i, j-1)
            ]
            
            for idx, (ni, nj) in enumerate(neighbors):
                if gray[ni, nj] >= center:
                    binary_string |= (1 << idx)
            
            lbp_image[i-1, j-1] = binary_string
    
    # Calculate variance of LBP histogram
    hist, _ = np.histogram(lbp_image.ravel(), bins=256, range=(0, 256))
    hist = hist.astype(float) / (hist.sum() + 1e-7)
    
    # Variance of the distribution
    mean = np.sum(np.arange(256) * hist)
    variance = np.sum(((np.arange(256) - mean) ** 2) * hist)
    
    return float(variance)


def analyze_color_distribution(image: np.ndarray) -> float:
    """
    Check for natural skin color distribution.
    
    Real faces have specific color characteristics in YCrCb/HSV space.
    Screens have limited color depth, printed photos have different gamut.
    
    Args:
        image: BGR image
        
    Returns:
        Score between 0.0-1.0 (higher = more natural skin tones)
    """
    if image is None or image.size == 0:
        return 0.0
    
    # Convert to YCrCb color space (better for skin detection)
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    
    # Skin color range in YCrCb
    # Y: any, Cr: 133-173, Cb: 77-127
    lower_skin = np.array([0, 133, 77], dtype=np.uint8)
    upper_skin = np.array([255, 173, 127], dtype=np.uint8)
    
    # Create skin mask
    skin_mask = cv2.inRange(ycrcb, lower_skin, upper_skin)
    
    # Calculate skin pixel ratio
    total_pixels = image.shape[0] * image.shape[1]
    skin_pixels = cv2.countNonZero(skin_mask)
    skin_ratio = skin_pixels / total_pixels
    
    # Also check color variance within skin regions
    skin_region = cv2.bitwise_and(image, image, mask=skin_mask)
    
    if skin_pixels > 100:
        # Extract actual skin pixels
        skin_values = image[skin_mask > 0]
        color_std = np.std(skin_values)
        
        # Natural skin has some variation but not too much
        # Score based on having reasonable skin area and variation
        area_score = min(1.0, skin_ratio / 0.2)  # Expect ~20% skin area
        variance_score = min(1.0, color_std / 30.0)  # Expect some variance
        
        return (area_score + variance_score) / 2.0
    
    return 0.0


def check_image_sharpness(gray_image: np.ndarray) -> float:
    """
    Compute Laplacian variance to detect photos-of-photos.
    
    Photos taken of screens or printed photos are typically blurrier
    than direct camera captures.
    
    Args:
        gray_image: Grayscale image
        
    Returns:
        Laplacian variance (higher = sharper image)
    """
    if gray_image is None or gray_image.size == 0:
        return 0.0
    
    # Compute Laplacian
    laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
    
    # Return variance
    return float(laplacian.var())


def detect_moire_patterns(gray_image: np.ndarray) -> float:
    """
    Detect moiré patterns from screens using FFT analysis.
    
    Screen displays produce distinctive frequency patterns when photographed.
    
    Args:
        gray_image: Grayscale image
        
    Returns:
        Score between 0.0-1.0 (higher = less moiré, more natural)
    """
    if gray_image is None or gray_image.size == 0:
        return 0.0
    
    # Resize for consistent FFT analysis
    resized = cv2.resize(gray_image, (256, 256))
    
    # Apply FFT
    f_transform = np.fft.fft2(resized.astype(float))
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    
    # Log transform for visualization
    magnitude_log = np.log1p(magnitude)
    
    # Check for periodic patterns (moiré)
    # High frequency energy in specific bands indicates screen patterns
    h, w = magnitude_log.shape
    center_y, center_x = h // 2, w // 2
    
    # Create annular mask for mid-to-high frequencies
    y, x = np.ogrid[:h, :w]
    distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    
    # Mid-frequency ring (where moiré patterns typically appear)
    mid_freq_mask = (distance > 20) & (distance < 100)
    
    mid_freq_energy = np.sum(magnitude_log[mid_freq_mask])
    total_energy = np.sum(magnitude_log)
    
    if total_energy > 0:
        ratio = mid_freq_energy / total_energy
        # Lower ratio = less periodic patterns = more natural
        # Invert so higher score = better (less moiré)
        return max(0.0, min(1.0, 1.0 - (ratio * 2)))
    
    return 0.5


def detect_spoof(image: np.ndarray) -> Dict:
    """
    Main passive liveness detection function.
    
    Combines multiple detection techniques to determine if the image
    is from a live person or a spoof (screen/photo).
    
    This is NON-BLOCKING - returns result as a warning, verification
    continues regardless of outcome.
    
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
    
    if image is None or image.size == 0:
        result["error"] = "Invalid image provided"
        return result
    
    try:
        # Convert to grayscale for analysis
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        checks = {}
        scores = []
        
        # 0. Image Size Check (prevent tiny cropped images)
        h, w = gray.shape[:2]
        MIN_SIZE = 100  # Minimum dimension in pixels
        size_passed = bool(h >= MIN_SIZE and w >= MIN_SIZE)
        checks["image_size"] = {
            "passed": size_passed,
            "score": float(min(h, w)),
            "threshold": float(MIN_SIZE)
        }
        scores.append(1.0 if size_passed else 0.0)
        
        # 1. Texture Analysis (LBP)
        texture_score = compute_lbp_texture_score(gray)
        texture_passed = bool(texture_score > LIVENESS_TEXTURE_THRESHOLD)
        checks["texture"] = {
            "passed": texture_passed,
            "score": float(round(texture_score, 2)),
            "threshold": float(LIVENESS_TEXTURE_THRESHOLD)
        }
        scores.append(1.0 if texture_passed else 0.0)
        
        # 2. Color Distribution
        color_score = analyze_color_distribution(image)
        color_passed = bool(color_score > LIVENESS_COLOR_THRESHOLD)
        checks["color"] = {
            "passed": color_passed,
            "score": float(round(color_score, 3)),
            "threshold": float(LIVENESS_COLOR_THRESHOLD)
        }
        scores.append(1.0 if color_passed else 0.0)
        
        # 3. Sharpness Analysis
        sharpness_score = check_image_sharpness(gray)
        sharpness_passed = bool(sharpness_score > LIVENESS_SHARPNESS_THRESHOLD)
        checks["sharpness"] = {
            "passed": sharpness_passed,
            "score": float(round(sharpness_score, 2)),
            "threshold": float(LIVENESS_SHARPNESS_THRESHOLD)
        }
        scores.append(1.0 if sharpness_passed else 0.0)
        
        # 4. Moiré Pattern Detection
        moire_score = detect_moire_patterns(gray)
        moire_passed = bool(moire_score > LIVENESS_MOIRE_THRESHOLD)
        checks["reflection"] = {
            "passed": moire_passed,
            "score": float(round(moire_score, 3)),
            "threshold": float(LIVENESS_MOIRE_THRESHOLD)
        }
        scores.append(1.0 if moire_passed else 0.0)
        
        # 5. ML-based Anti-Spoofing Model (if available)
        try:
            from .antispoof_model import predict_spoof, is_model_available
            ml_result = predict_spoof(image)
            
            # Only add to checks if model actually ran (not just fallback)
            if ml_result.get("model_used") not in ["none", "error"]:
                ml_passed = ml_result.get("is_real", False)
                ml_spoof_prob = ml_result.get("spoof_probability", 0.5)
                checks["ml_model"] = {
                    "passed": bool(ml_passed),
                    "score": float(round(1.0 - ml_spoof_prob, 3)),  # Convert to "realness" score
                    "threshold": 0.5,
                    "model": ml_result.get("model_used", "unknown")
                }
                # ML model gets equal weight (1 vote)
                scores.append(1.0 if ml_passed else 0.0)
        except ImportError:
            # ML model not available, continue with basic checks
            pass
        except Exception as e:
            # ML model error, continue without it
            checks["ml_model"] = {
                "passed": True,  # Don't penalize if model fails
                "score": 0.5,
                "threshold": 0.5,
                "error": str(e)
            }
        
        # Calculate overall confidence
        confidence = sum(scores) / len(scores) if scores else 0.0
        
        # Determine if live based on threshold
        is_live = bool(confidence >= LIVENESS_THRESHOLD)
        
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
