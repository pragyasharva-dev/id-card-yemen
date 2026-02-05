"""
Shared helpers for Yemen ID and Passport document validation services.

Used only by yemen_id_validation_service and passport_validation_service.
Implements: sharpness, moiré, texture, resolution, document boundary detection.
"""
import cv2
import numpy as np
from typing import Optional, Tuple, Dict, List

from utils.config import (
    DOC_MIN_SHARPNESS,
    DOC_MIN_SHARPNESS_PASSPORT,
    DOC_MIN_RESOLUTION_PX,
    DOC_MIN_MARGIN_RATIO,
    DOC_MIN_COVERAGE_RATIO,
    DOC_ASPECT_RATIO_YEMEN_ID,
    DOC_ASPECT_RATIO_PASSPORT,
    DOC_MOIRE_THRESHOLD,
    DOC_MOIRE_THRESHOLD_BACK,
    DOC_MOIRE_THRESHOLD_PASSPORT,
    DOC_SCREEN_GRID_MAX,
    DOC_SCREEN_GRID_MAX_BACK,
    DOC_SCREEN_GRID_MAX_PASSPORT,
    DOC_PASSPORT_MOIRE_BORDERLINE_MIN,
    DOC_PASSPORT_MOIRE_BORDERLINE_MAX,
    DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MIN,
    DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MAX,
    DOC_TEXTURE_THRESHOLD,
    DOC_TEXTURE_MAX,
    DOC_HALFTONE_MAX,
    DOC_HALFTONE_MAX_PASSPORT,
    DOC_HIGH_TEXTURE_THRESHOLD,
    DOC_MIN_SATURATION_FOR_HIGH_TEXTURE,
)


def _to_gray(image: np.ndarray) -> np.ndarray:
    """Convert BGR to grayscale if needed."""
    if image is None or image.size == 0:
        return None
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.copy()


def check_document_sharpness(image: np.ndarray, normalize: bool = True) -> Tuple[float, bool]:
    """
    Document sharpness (Laplacian variance). Reject blurry / out-of-focus captures.
    Returns (score, passed).
    """
    gray = _to_gray(image)
    if gray is None or gray.size == 0:
        return 0.0, False
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = float(laplacian.var())
    if normalize:
        h, w = gray.shape
        pixel_count = h * w
        base_pixels = 640 * 480
        variance = variance * (base_pixels / max(1, pixel_count))
    score = min(1.0, variance / 100.0) if variance > 0 else 0.0
    passed = variance >= (DOC_MIN_SHARPNESS * 100.0) or score >= DOC_MIN_SHARPNESS
    return score, passed


def check_document_moire(image: np.ndarray) -> Tuple[float, bool]:
    """
    Moiré / screen-capture detection via FFT. Higher score = less moiré (more natural).
    Returns (score 0-1, passed).
    """
    gray = _to_gray(image)
    if gray is None or gray.size == 0:
        return 0.0, False
    size = 256
    resized = cv2.resize(gray, (size, size)).astype(float)
    hann = np.hanning(size)
    window = np.outer(hann, hann)
    windowed = resized * window
    f_transform = np.fft.fft2(windowed)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    magnitude_log = np.log1p(magnitude)
    h, w = magnitude_log.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    valid_mask = (distance > 5) & (distance < 120)
    mid_freq_mask = (distance > 20) & (distance < 80)
    valid_energy = np.sum(magnitude_log[valid_mask])
    mid_freq_energy = np.sum(magnitude_log[mid_freq_mask])
    if valid_energy > 0:
        ratio = mid_freq_energy / valid_energy
        score = max(0.0, min(1.0, 1.0 - (ratio * 1.5)))
    else:
        score = 0.5
    passed = score > DOC_MOIRE_THRESHOLD
    return score, passed


def check_screen_grid(image: np.ndarray) -> Tuple[float, bool]:
    """
    Detect regular pixel/screen grid (photo of monitor/phone). FFT peak concentration in
    mid-high frequencies suggests LCD-style grid. Returns (grid_score 0-1, passed).
    passed = score <= DOC_SCREEN_GRID_MAX.
    """
    gray = _to_gray(image)
    if gray is None or gray.size == 0:
        return 0.0, True
    size = 256
    resized = cv2.resize(gray, (size, size)).astype(float)
    hann = np.hanning(size)
    window = np.outer(hann, hann)
    windowed = resized * window
    f_transform = np.fft.fft2(windowed)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    # Mid-high frequency ring (screen grids often here)
    ring_mask = (distance >= 25) & (distance <= 90)
    mag_ring = magnitude[ring_mask].ravel()
    mag_ring = mag_ring[mag_ring > 0]
    if mag_ring.size < 10:
        return 0.0, True
    peak = float(np.max(mag_ring))
    mean_val = float(np.mean(mag_ring))
    if mean_val <= 0:
        return 0.0, True
    ratio = peak / mean_val
    # Use gentler scale so originals (security patterns, edges) don't max out; only strong LCD grids fail
    score = min(1.0, (ratio - 1.0) / 20.0)
    score = max(0.0, score)
    passed = score <= DOC_SCREEN_GRID_MAX
    return round(score, 3), passed


def check_halftone(image: np.ndarray) -> Tuple[float, bool]:
    """
    Detect halftone / printed-dot pattern via FFT. Printed copies show strong periodic peaks.
    Returns (halftone_score 0-1, passed). High score = suspected halftone; passed = score <= DOC_HALFTONE_MAX.
    """
    gray = _to_gray(image)
    if gray is None or gray.size == 0:
        return 0.0, True
    size = 256
    resized = cv2.resize(gray, (size, size)).astype(float)
    hann = np.hanning(size)
    window = np.outer(hann, hann)
    windowed = resized * window
    f_transform = np.fft.fft2(windowed)
    f_shift = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shift)
    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    # Exclude DC and very low frequencies (halftone is typically mid-freq)
    mask = (distance >= 8) & (distance <= 100)
    mag_valid = magnitude.copy()
    mag_valid[~mask] = 0
    total = float(np.sum(mag_valid))
    if total <= 0:
        return 0.0, True
    # Peakiness: ratio of top few bins to total (halftone has strong narrow peaks)
    flat = mag_valid[mask].ravel()
    flat = flat[flat > 0]
    if flat.size == 0:
        return 0.0, True
    sorted_vals = np.sort(flat)[::-1]
    top_k = min(50, len(sorted_vals))
    peak_energy = float(np.sum(sorted_vals[:top_k]))
    score = min(1.0, peak_energy / max(total * 0.15, 1e-6) * 0.5)
    passed = score <= DOC_HALFTONE_MAX
    return round(score, 3), passed


def check_document_texture(image: np.ndarray) -> Tuple[float, bool]:
    """
    Texture variance (LBP). Photocopies/screens tend to have flatter texture.
    Returns (score, passed). New implementation (no dependency on liveness_service).
    """
    gray = _to_gray(image)
    if gray is None or gray.size == 0:
        return 0.0, False
    gray = gray.astype(np.uint8)
    h, w = gray.shape
    if h < 10 or w < 10:
        return 0.0, False
    padded = np.pad(gray, 1, mode="edge")
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    center = padded[1:-1, 1:-1].astype(np.int16)
    lbp = np.zeros_like(center, dtype=np.uint8)
    for i, (dy, dx) in enumerate(offsets):
        neighbor = padded[1 + dy : h + 1 + dy, 1 + dx : w + 1 + dx].astype(np.int16)
        lbp |= ((neighbor >= center).astype(np.uint8) << i)
    hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256), density=True)
    mean = np.sum(np.arange(256) * hist)
    variance = np.sum(((np.arange(256) - mean) ** 2) * hist)
    # Normalize to ~0-1 scale; 20 as reference for "good" texture
    score = min(1.0, float(variance) / 20.0) if variance > 0 else 0.0
    # Reject too flat (photocopy) and too peaky (halftone dots from printed copy)
    passed = DOC_TEXTURE_THRESHOLD <= score <= DOC_TEXTURE_MAX
    return score, passed


def check_document_resolution(image: np.ndarray, min_side_px: Optional[int] = None) -> Tuple[bool, int]:
    """
    Ensure image is not too small. Returns (passed, min_side).
    """
    if image is None or image.size == 0:
        return False, 0
    h, w = image.shape[:2]
    min_side = min(h, w)
    threshold = min_side_px if min_side_px is not None else DOC_MIN_RESOLUTION_PX
    return min_side >= threshold, min_side


def get_document_boundary(
    image: np.ndarray,
    aspect_range: Tuple[float, float],
) -> Optional[Dict]:
    """
    Detect largest rectangular document-like region (contour + aspect ratio).
    aspect_range = (min_ratio, max_ratio) for width/height.
    Returns dict with bbox (x,y,w,h), aspect_ratio, area_ratio, margin_ok, or None.
    """
    if image is None or image.size == 0:
        return None
    gray = _to_gray(image)
    if gray is None:
        return None
    h, w = gray.shape[:2]
    # Edge detection and contours
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    # OpenCV 4 returns (contours, hierarchy); OpenCV 3 returns (image, contours, hierarchy)
    cnt_result = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    contours = cnt_result[1] if len(cnt_result) == 3 else cnt_result[0]
    image_area = int(h) * int(w)
    best = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < image_area * 0.1:  # Ignore tiny contours
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            x, y, bw, bh = cv2.boundingRect(approx)
            if bw < 10 or bh < 10:
                continue
            ar = bw / float(bh)
            box_area = bw * bh
            if aspect_range[0] <= ar <= aspect_range[1] and box_area > best_area:
                best_area = box_area
                best = {
                    "bbox": (int(x), int(y), int(bw), int(bh)),
                    "aspect_ratio": float(ar),
                    "area_ratio": float(box_area) / max(image_area, 1),
                    "area": int(box_area),
                }
    if best is None:
        # Fallback: treat full image as document
        ar = float(w) / max(h, 1)
        if aspect_range[0] <= ar <= aspect_range[1]:
            best = {
                "bbox": (0, 0, int(w), int(h)),
                "aspect_ratio": float(ar),
                "area_ratio": 1.0,
                "area": int(image_area),
            }
    if best is None:
        return None
    # Margin check: document should not be flush with image edges
    x, y, bw, bh = best["bbox"]
    margin_w = float(min(x, w - (x + bw))) / max(w, 1)
    margin_h = float(min(y, h - (y + bh))) / max(h, 1)
    best["margin_ok"] = bool(margin_w >= DOC_MIN_MARGIN_RATIO and margin_h >= DOC_MIN_MARGIN_RATIO)
    best["margin_ratio_w"] = float(margin_w)
    best["margin_ratio_h"] = float(margin_h)
    return best


def check_not_screenshot_or_copy(
    image: np.ndarray,
    for_back: bool = False,
    for_passport: bool = False,
) -> Dict:
    """
    Combined check: not screenshot or photocopy (sharpness, moire, texture, halftone).
    Rejects blurry, screen-captured, photocopied, and printed (halftone) copies.
    - for_back=True: ID card back – relaxed moiré/screen_grid (barcode can add pattern).
    - for_passport=True: passport – stricter moiré/screen_grid to catch copies and screen-captures.
    Returns dict with passed, checks (sharpness, moire, screen_grid, texture, halftone, saturation), error.
    """
    result = {"passed": False, "checks": {}, "error": None}
    if image is None or image.size == 0:
        result["error"] = "Invalid image"
        return result
    if for_back:
        moire_threshold = DOC_MOIRE_THRESHOLD_BACK
        screen_grid_max = DOC_SCREEN_GRID_MAX_BACK
    elif for_passport:
        moire_threshold = DOC_MOIRE_THRESHOLD_PASSPORT
        screen_grid_max = DOC_SCREEN_GRID_MAX_PASSPORT
    else:
        moire_threshold = DOC_MOIRE_THRESHOLD
        screen_grid_max = DOC_SCREEN_GRID_MAX

    sharp_score, sharp_ok_default = check_document_sharpness(image)
    sharp_min = DOC_MIN_SHARPNESS_PASSPORT if for_passport else DOC_MIN_SHARPNESS
    sharp_ok = sharp_ok_default if not for_passport else (sharp_score >= sharp_min)
    moire_score, _ = check_document_moire(image)
    moire_ok = moire_score > moire_threshold
    screen_grid_score, _ = check_screen_grid(image)
    screen_grid_ok = screen_grid_score <= screen_grid_max
    texture_score, texture_ok = check_document_texture(image)
    halftone_score, halftone_ok_default = check_halftone(image)
    halftone_max = DOC_HALFTONE_MAX_PASSPORT if for_passport else DOC_HALFTONE_MAX
    halftone_ok = halftone_ok_default if not for_passport else (halftone_score <= halftone_max)
    # When texture is high, require sufficient saturation (reject muted printed copies)
    saturation_score = _mean_saturation(image)
    if texture_score >= DOC_HIGH_TEXTURE_THRESHOLD:
        saturation_ok = saturation_score >= DOC_MIN_SATURATION_FOR_HIGH_TEXTURE
    else:
        saturation_ok = True
    # Passport: reject borderline moiré + medium screen_grid (screen-capture pattern); originals have higher screen_grid
    suspicious_screen_capture = False
    if for_passport:
        moire_borderline = (
            DOC_PASSPORT_MOIRE_BORDERLINE_MIN <= moire_score <= DOC_PASSPORT_MOIRE_BORDERLINE_MAX
        )
        screen_grid_suspicious = (
            DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MIN <= screen_grid_score <= DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MAX
        )
        suspicious_screen_capture = bool(moire_borderline and screen_grid_suspicious)

    result["checks"] = {
        "sharpness": {"passed": bool(sharp_ok), "score": round(sharp_score, 3), "threshold": sharp_min},
        "moire": {"passed": bool(moire_ok), "score": round(moire_score, 3), "threshold": moire_threshold},
        "screen_grid": {"passed": bool(screen_grid_ok), "score": screen_grid_score, "max": screen_grid_max},
        "texture": {"passed": bool(texture_ok), "score": round(texture_score, 3), "threshold": DOC_TEXTURE_THRESHOLD, "max": DOC_TEXTURE_MAX},
        "halftone": {"passed": bool(halftone_ok), "score": halftone_score, "max": halftone_max},
        "saturation": {"passed": bool(saturation_ok), "score": round(saturation_score, 3), "min_when_high_texture": DOC_MIN_SATURATION_FOR_HIGH_TEXTURE},
    }
    result["passed"] = bool(
        sharp_ok and moire_ok and screen_grid_ok and texture_ok and halftone_ok and saturation_ok
        and not suspicious_screen_capture
    )
    if not result["passed"]:
        if suspicious_screen_capture:
            result["error"] = "Failed: moire + screen_grid (screen capture suspected)"
        else:
            failed = [k for k, v in result["checks"].items() if not v["passed"]]
            result["error"] = f"Failed: {', '.join(failed)} (screenshot/copy/print/screen suspected)"
    return result


def _mean_saturation(image: np.ndarray) -> float:
    """Mean saturation (0-1) in HSV; 0 for grayscale or invalid."""
    if image is None or image.size == 0 or len(image.shape) != 3:
        return 0.0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    s_channel = hsv[:, :, 1]
    return float(np.mean(s_channel)) / 255.0


def check_glare(image: np.ndarray, roi: Optional[Tuple[int, int, int, int]] = None) -> Tuple[bool, float]:
    """
    Detect large overexposed/saturated regions (glare). Returns (no_significant_glare, glare_ratio).
    """
    if image is None or image.size == 0:
        return True, 0.0
    if roi:
        x, y, rw, rh = roi
        img = image[y : y + rh, x : x + rw]
    else:
        img = image
    gray = _to_gray(img)
    if gray is None:
        return True, 0.0
    # Overexposed: very high intensity
    overexposed = np.sum(gray >= 250) / max(gray.size, 1)
    # Saturation in BGR: max channel near 255
    if len(img.shape) == 3:
        max_ch = np.max(img, axis=2)
        saturated = np.sum(max_ch >= 250) / max(max_ch.size, 1)
        glare_ratio = max(overexposed, saturated)
    else:
        glare_ratio = overexposed
    # Fail if more than ~15% of image is glare
    no_glare = glare_ratio <= 0.15
    return no_glare, round(glare_ratio, 3)
