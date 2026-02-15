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
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

from .face_extractor import get_face_extractor, is_available as insightface_available
from utils.config import (
    FACE_QUALITY_ENABLED,
    FACE_QUALITY_MIN_LANDMARKS,
    FACE_QUALITY_MIN_CONFIDENCE,
    FACE_QUALITY_MIN_FACE_RATIO
)
from utils.exceptions import ServiceError, ModelLoadError


def _analyze_landmarks(face, image: np.ndarray = None) -> Dict:
    """
    Analyze facial landmark visibility with occlusion detection.
    
    InsightFace provides 5-point landmarks:
    - Left eye, Right eye, Nose tip, Left mouth corner, Right mouth corner
    
    IMPORTANT: InsightFace always predicts all 5 landmark positions even when
    parts of the face are covered. This function verifies actual visibility
    by analyzing image texture around each landmark point.
    
    Args:
        face: InsightFace face object with landmarks
        image: BGR image for occlusion detection (optional but recommended)
        
    Returns:
        Dictionary with landmark analysis results
    """
    result = {
        "landmarks_detected": 0,
        "eyes_visible": False,
        "nose_visible": False,
        "mouth_visible": False,
        "landmark_confidence": 0.0,
        "occlusion_detected": False
    }
    
    if face is None:
        return result
    
    # Get landmarks (5-point: left_eye, right_eye, nose, left_mouth, right_mouth)
    kps = getattr(face, 'kps', None)
    if kps is None or len(kps) < 5:
        return result
    
    # Get bounding box for relative position checks
    bbox = getattr(face, 'bbox', None)
    
    # Track valid landmarks with actual visibility verification
    valid_landmarks = 0
    left_eye_visible = False
    right_eye_visible = False
    nose_visible = False
    left_mouth_visible = False
    right_mouth_visible = False
    
    for i, (x, y) in enumerate(kps[:5]):
        x, y = int(x), int(y)
        
        if x <= 0 or y <= 0:
            continue
        
        # Check if landmark is actually visible using image analysis
        is_visible = True
        
        if image is not None:
            is_visible = _verify_landmark_visible(image, x, y, i, bbox)
        
        if is_visible:
            valid_landmarks += 1
            if i == 0:
                left_eye_visible = True
            elif i == 1:
                right_eye_visible = True
            elif i == 2:
                nose_visible = True
            elif i == 3:
                left_mouth_visible = True
            elif i == 4:
                right_mouth_visible = True
    
    # Eyes visible requires BOTH eyes to be visible
    result["eyes_visible"] = left_eye_visible and right_eye_visible
    result["nose_visible"] = nose_visible
    # Mouth visible requires at least one mouth corner
    result["mouth_visible"] = left_mouth_visible or right_mouth_visible
    result["landmarks_detected"] = valid_landmarks
    
    # Detect if occlusion is likely (less than 4 landmarks visible)
    result["occlusion_detected"] = valid_landmarks < 4
    
    # ADDITIONAL CHECK: Detect hand/arm crossing face
    # Look for horizontal edges in the face region (between eyes and mouth)
    if image is not None and kps is not None and len(kps) >= 5:
        face_occlusion = _check_face_region_occlusion(image, kps, bbox)
        if face_occlusion:
            result["occlusion_detected"] = True
            logger.info("Face region occlusion detected (possible hand/arm crossing face)")
    
    # Calculate confidence based on detection score
    det_score = getattr(face, 'det_score', 0.0)
    result["landmark_confidence"] = float(det_score)
    
    return result


def _check_face_region_occlusion(image: np.ndarray, kps, bbox) -> bool:
    """
    Check for occlusion in the face region by detecting horizontal discontinuities.
    
    This detects hands/arms crossing the face by looking for:
    1. Strong horizontal edges in the mid-face region
    2. Color/brightness discontinuities that don't match normal face patterns
    
    Args:
        image: BGR image
        kps: Facial landmark keypoints (5-point)
        bbox: Face bounding box
        
    Returns:
        True if face region appears occluded
    """
    import numpy as np
    if bbox is None or len(bbox) < 4:
        return False
    
    try:
        h, w = image.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        
        # Get eye and mouth positions
        left_eye = kps[0]
        right_eye = kps[1]
        nose = kps[2]
        left_mouth = kps[3]
        right_mouth = kps[4]
        
        # Define the mid-face region (between eyes and mouth)
        eye_y = int(min(left_eye[1], right_eye[1]))
        mouth_y = int(max(left_mouth[1], right_mouth[1]))
        
        # Add padding
        region_top = max(0, eye_y + 10)  # Start below eyes
        region_bottom = min(h, mouth_y + 10)  # End below mouth
        region_left = max(0, x1)
        region_right = min(w, x2)
        
        if region_bottom <= region_top or region_right <= region_left:
            return False
        
        # Extract the mid-face region
        face_region = image[region_top:region_bottom, region_left:region_right]
        
        if face_region.size == 0:
            return False
        
        gray_region = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        
        # Detect horizontal edges using Sobel
        # Hand/arm crossing face creates strong horizontal edges
        sobel_x = cv2.Sobel(gray_region, cv2.CV_64F, 1, 0, ksize=3)  # Vertical edges
        sobel_y = cv2.Sobel(gray_region, cv2.CV_64F, 0, 1, ksize=3)  # Horizontal edges
        
        # Calculate edge magnitudes
        horizontal_edge_strength = np.mean(np.abs(sobel_y))
        vertical_edge_strength = np.mean(np.abs(sobel_x))
        
        # Also check for strong horizontal lines using Hough
        edges = cv2.Canny(gray_region, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=20, maxLineGap=10)
        
        horizontal_line_count = 0
        if lines is not None:
            for line in lines:
                x1_l, y1_l, x2_l, y2_l = line[0]
                angle = abs(np.arctan2(y2_l - y1_l, x2_l - x1_l) * 180 / np.pi)
                # Count lines that are mostly horizontal (within 30 degrees)
                if angle < 30 or angle > 150:
                    horizontal_line_count += 1
        
        # Check for brightness discontinuity (rows with sudden brightness change)
        row_means = np.mean(gray_region, axis=1)
        if len(row_means) > 5:
            row_diffs = np.abs(np.diff(row_means))
            max_row_diff = np.max(row_diffs) if len(row_diffs) > 0 else 0
            mean_row_diff = np.mean(row_diffs) if len(row_diffs) > 0 else 0
        else:
            max_row_diff = 0
            mean_row_diff = 0
        
        logger.debug(f"Face region: h_edge={horizontal_edge_strength:.1f}, v_edge={vertical_edge_strength:.1f}, "
                    f"h_lines={horizontal_line_count}, max_row_diff={max_row_diff:.1f}")
        
        # Detection criteria for hand/arm occlusion:
        # Hand covering face has:
        # - Many strong horizontal lines (arm/hand edges)
        # - Higher horizontal/vertical edge ratio (arm is horizontal)
        # - Possibly brightness discontinuity from arm shadow
        #
        # Normal face has:
        # - Fewer horizontal lines (face features are varied)
        # - More balanced edge ratio
        
        h_v_ratio = horizontal_edge_strength / (vertical_edge_strength + 1)
        
        # Revised thresholds based on testing:
        # - Hand-covering: h_lines=23, h_v_ratio=1.10 (more horizontal = arm crossing)
        # - Hijab (valid): h_lines=21, h_v_ratio=0.92 (more vertical = hijab edge)
        # - Normal selfie: h_lines=16, h_v_ratio=1.06
        #
        # Key insight: Hands crossing face have h_v_ratio > 1.0 (horizontal dominant)
        # Hijab around face has h_v_ratio < 1.0 (vertical edges around face frame)
        
        is_occluded = (
            (horizontal_line_count >= 22 and h_v_ratio > 1.0) or  # Many lines + horizontal dominant
            (h_v_ratio > 1.08 and horizontal_line_count >= 18) or  # High ratio + many lines
            (max_row_diff > 40 and horizontal_line_count >= 18 and h_v_ratio > 1.0)  # Brightness jump + lines + ratio
        )
        
        return is_occluded
        
    except Exception as e:
        logger.error(f"Error in face region occlusion check: {e}")
        return False


def _verify_landmark_visible(image: np.ndarray, x: int, y: int, landmark_idx: int, bbox=None) -> bool:
    """
    Verify if a landmark is actually visible using local image analysis.
    
    Checks for:
    1. Valid position within image bounds
    2. Skin-like colors (nose/mouth MUST have skin visible)
    3. Non-black/dark coverage detection (for masks, niqabs)
    4. Local texture variance
    
    Args:
        image: BGR image
        x, y: Landmark coordinates
        landmark_idx: 0=left_eye, 1=right_eye, 2=nose, 3=left_mouth, 4=right_mouth
        bbox: Face bounding box for relative position checks
        
    Returns:
        True if landmark appears to be genuinely visible
    """
    import numpy as np
    import logging
    logger = logging.getLogger(__name__)
    
    h, w = image.shape[:2]
    
    # Check bounds
    if x < 0 or x >= w or y < 0 or y >= h:
        logger.debug(f"Landmark {landmark_idx}: Out of bounds ({x}, {y})")
        return False
    
    # Define ROI size based on landmark type
    roi_sizes = {
        0: 20,  # left eye - larger for better analysis
        1: 20,  # right eye  
        2: 25,  # nose - larger area
        3: 20,  # left mouth
        4: 20   # right mouth
    }
    roi_size = roi_sizes.get(landmark_idx, 20)
    
    # Extract region around landmark
    x1 = max(0, x - roi_size)
    y1 = max(0, y - roi_size)
    x2 = min(w, x + roi_size)
    y2 = min(h, y + roi_size)
    
    roi = image[y1:y2, x1:x2]
    
    if roi.size == 0:
        return False
    
    # For nose and mouth landmarks (indices 2, 3, 4), we MUST see skin
    # These are the landmarks that would be covered by a niqab/mask
    if landmark_idx >= 2:  # Nose and mouth
        if len(roi.shape) == 3:
            # Convert ROI to HSV for skin detection
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Skin color range in HSV - EXPANDED to include all skin tones
            # Range 1: Light to medium skin tones
            lower_skin1 = np.array([0, 15, 60], dtype=np.uint8)
            upper_skin1 = np.array([25, 255, 255], dtype=np.uint8)
            
            # Range 2: Darker skin tones (lower saturation, lower value)
            lower_skin2 = np.array([0, 10, 30], dtype=np.uint8)
            upper_skin2 = np.array([35, 180, 200], dtype=np.uint8)
            
            # Range 3: Very dark skin tones
            lower_skin3 = np.array([0, 5, 20], dtype=np.uint8)
            upper_skin3 = np.array([40, 150, 150], dtype=np.uint8)
            
            # Create combined skin mask
            skin_mask1 = cv2.inRange(hsv_roi, lower_skin1, upper_skin1)
            skin_mask2 = cv2.inRange(hsv_roi, lower_skin2, upper_skin2)
            skin_mask3 = cv2.inRange(hsv_roi, lower_skin3, upper_skin3)
            skin_mask = cv2.bitwise_or(skin_mask1, skin_mask2)
            skin_mask = cv2.bitwise_or(skin_mask, skin_mask3)
            
            skin_ratio = np.sum(skin_mask > 0) / skin_mask.size
            
            # Check brightness
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            mean_brightness = np.mean(gray_roi)
            
            logger.debug(f"Landmark {landmark_idx}: skin_ratio={skin_ratio:.3f}, brightness={mean_brightness:.1f}")
            
            # STRICT SKIN DETECTION: Nose and mouth MUST show skin
            # This catches BOTH dark masks (niqab) AND light masks (surgical masks)
            # 
            # Key insight: Real skin has specific color characteristics that masks don't have
            # - Black niqab: low skin ratio, low brightness
            # - Light surgical mask: low skin ratio, HIGH brightness (blue/white)
            # - Real dark skin: reasonable skin ratio (our expanded ranges cover dark skin)
            
            min_skin_ratios = {
                2: 0.20,  # nose - MUST show skin (was 0.15)
                3: 0.15,  # left mouth corner (was 0.10)
                4: 0.15   # right mouth corner (was 0.10)
            }
            min_skin = min_skin_ratios.get(landmark_idx, 0.15)
            
            # Detect mask/covering: low skin ratio indicates non-skin covering
            # We require minimum skin ratio REGARDLESS of brightness
            # Our expanded skin ranges already cover dark skin tones
            if skin_ratio < min_skin:
                logger.info(f"Landmark {landmark_idx} REJECTED: insufficient skin detected ({skin_ratio:.3f} < {min_skin})")
                return False
            
            # Additional check for black fabric (very dark areas with no skin)
            is_black_fabric = (skin_ratio < 0.10) and (mean_brightness < 50)
            if is_black_fabric:
                logger.info(f"Landmark {landmark_idx} REJECTED: appears to be black fabric (skin_ratio={skin_ratio:.3f}, brightness={mean_brightness:.1f})")
                return False
            
            # HAND/ARM OCCLUSION DETECTION
            # Hands covering face have uniform skin without expected facial features
            
            # For MOUTH landmarks (3, 4): Check for lip color
            # Lips are typically more pink/red than surrounding skin or hands
            if landmark_idx in [3, 4]:
                # Check for lip-like colors (more red/pink than regular skin)
                # In HSV, lips have higher saturation in red range
                b, g, r = cv2.split(roi)
                
                # Lips typically have r > g and higher redness ratio
                redness = np.mean(r.astype(float) - g.astype(float))
                red_ratio = np.mean(r) / (np.mean(g) + 1)  # Avoid division by zero
                
                # Also check color variance - lips have distinct color from surrounding skin
                color_variance = np.var(r) + np.var(g) + np.var(b)
                
                logger.debug(f"Mouth {landmark_idx}: redness={redness:.1f}, red_ratio={red_ratio:.2f}, color_var={color_variance:.1f}")
                
                # Hands covering mouth will have low redness and low color variance
                # Real lips MUST have lip-like characteristics
                # Changed to stricter check - require multiple conditions
                has_redness = redness > 3
                has_red_ratio = red_ratio > 1.02
                has_color_variance = color_variance > 300
                
                # Must have at least 2 of 3 lip features
                lip_score = sum([has_redness, has_red_ratio, has_color_variance])
                
                if lip_score < 2:
                    logger.info(f"Mouth {landmark_idx} REJECTED: insufficient lip features (score={lip_score}/3, redness={redness:.1f}, ratio={red_ratio:.2f}, var={color_variance:.1f})")
                    return False
            
            # For NOSE landmark (2): Check for expected nose features
            # Nose has shadows, contours, and characteristic shape
            if landmark_idx == 2:
                # Edge detection - nose has more edges than flat hand
                edges = cv2.Canny(gray_roi, 50, 150)
                edge_density = np.sum(edges > 0) / edges.size
                
                # Gradient analysis - nose has characteristic gradients
                grad_x = cv2.Sobel(gray_roi, cv2.CV_64F, 1, 0, ksize=3)
                grad_y = cv2.Sobel(gray_roi, cv2.CV_64F, 0, 1, ksize=3)
                gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
                mean_gradient = np.mean(gradient_magnitude)
                
                # Texture variance - nose tip has different texture than hand
                variance = np.var(gray_roi)
                
                logger.debug(f"Nose: edge_density={edge_density:.3f}, gradient={mean_gradient:.1f}, variance={variance:.1f}")
                
                # Hand covering nose will have low edges, low gradient, uniform texture
                # Stricter check - require multiple nose features
                has_edges = edge_density > 0.02
                has_gradient = mean_gradient > 10
                has_texture = variance > 150
                
                # Must have at least 2 of 3 nose features
                nose_score = sum([has_edges, has_gradient, has_texture])
                
                if nose_score < 2:
                    logger.info(f"Nose REJECTED: insufficient nose features (score={nose_score}/3, edges={edge_density:.3f}, grad={mean_gradient:.1f}, var={variance:.1f})")
                    return False
    
    # For eyes (indices 0, 1), check that we can see eye features
    # Eyes should have some variance due to iris/pupil but dark eyes have less contrast
    if landmark_idx < 2:  # Eyes
        if len(roi.shape) == 3:
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray_roi = roi
        
        variance = np.var(gray_roi)
        mean_brightness = np.mean(gray_roi)
        
        logger.debug(f"Eye {landmark_idx}: variance={variance:.1f}, brightness={mean_brightness:.1f}")
        
        # Eyes need some variance (even dark eyes have some texture from eyelashes, etc.)
        # Very low threshold to accommodate dark eyes
        # Also check it's not completely uniform (like a solid mask)
        if variance < 30:
            logger.debug(f"Eye {landmark_idx} REJECTED: too uniform (variance={variance:.1f})")
            return False
        
        # SUNGLASSES DETECTION: Very dark brightness indicates sunglasses/dark glasses
        # Normal eyes: brightness ~40-80+
        # Sunglasses: brightness ~10-20
        # Dark eyes with dark skin: brightness ~25-50
        if mean_brightness < 20:
            logger.info(f"Eye {landmark_idx} REJECTED: too dark (brightness={mean_brightness:.1f}), possible sunglasses")
            return False
    
    logger.debug(f"Landmark {landmark_idx}: PASSED visibility check")
    return True


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
        raise ModelLoadError("InsightFace", reason="Not available")
    
    # Validate image
    if image is None or image.size == 0:
        raise ServiceError("Invalid image provided", code="INVALID_IMAGE")
    
    try:
        # Get face extractor
        extractor = get_face_extractor()
        
        # Detect faces
        faces = extractor.detect_faces(image)
        
        if not faces or len(faces) == 0:
            error_msg = (
                "No face detected on ID card. Please upload a clear photo of your ID."
                if image_type == "id_document"
                else "No face detected in selfie. Please take a clear photo showing your face."
            )
            raise ServiceError(error_msg, code="FACE_NOT_DETECTED")
        
        result["face_detected"] = True
        
        # Get the largest/most prominent face
        face = extractor.get_largest_face(image)
        
        # Analyze landmarks with image-based occlusion detection
        landmark_analysis = _analyze_landmarks(face, image)
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
        
        # Determine if face is visible - REQUIRE eyes, nose, AND mouth for selfies
        # For proper verification, the full face must be visible
        key_features_visible = (
            landmark_analysis["eyes_visible"] and 
            landmark_analysis["nose_visible"] and
            landmark_analysis["mouth_visible"]
        )
        
        # Also fail if occlusion is detected (less than 4 landmarks visible)
        occlusion_detected = landmark_analysis.get("occlusion_detected", False)
        
        result["face_visible"] = key_features_visible and landmarks_ok and confidence_ok and not occlusion_detected
        
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
        elif not ratio_ok and image_type != "id_document":
            # Skip face ratio check for ID cards - only matters for selfies
            result["error"] = "Face is too small in the image. Please come closer to the camera."
        elif occlusion_detected:
            if image_type == "id_document":
                result["error"] = "Face appears to be partially covered on ID card. Please upload a photo with full face visible."
            else:
                result["error"] = "Face appears to be partially covered. Please remove any face coverings, masks, or obstructions."
        elif not key_features_visible:
            if image_type == "id_document":
                result["error"] = "Cannot see eyes, nose, or mouth clearly on ID card. Please ensure face is not covered."
            else:
                result["error"] = "Cannot see your eyes, nose, or mouth clearly. Please remove any obstructions from your face."
        else:
            result["passed"] = True
            result["error"] = None
        
        return result
        
    except ServiceError:
        raise  # Re-raise custom exceptions
    except Exception as e:
        raise ServiceError(f"Quality check failed: {str(e)}", code="QUALITY_CHECK_FAILED")


def is_quality_check_enabled() -> bool:
    """Check if face quality validation is enabled."""
    return FACE_QUALITY_ENABLED
