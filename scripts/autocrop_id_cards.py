"""
ID Card Auto-Crop Script

Takes images from a source folder, detects the ID card using largest rectangle
detection, crops to the ID card boundaries, and saves to a destination folder.

Usage:
    python scripts/autocrop_id_cards.py --input INPUT_FOLDER --output OUTPUT_FOLDER

Example:
    python scripts/autocrop_id_cards.py --input ./raw_images --output ./cropped_images
"""

import cv2
import numpy as np
import argparse
from pathlib import Path
import sys


def order_points(pts):
    """
    Order points in: top-left, top-right, bottom-right, bottom-left order.
    """
    rect = np.zeros((4, 2), dtype="float32")
    
    # Top-left has smallest sum, bottom-right has largest
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    # Top-right has smallest diff, bottom-left has largest
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    return rect


def four_point_transform(image, pts, maintain_aspect=True):
    """
    Perform perspective transform to get a top-down view of the card.
    
    Args:
        image: Input image
        pts: 4 corner points
        maintain_aspect: If True, use standard ID card aspect ratio (85.6mm x 53.98mm ≈ 1.586:1)
    """
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    # Compute width
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    # Compute height
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    # Maintain standard ID card aspect ratio (1.586:1) to prevent stretching
    if maintain_aspect:
        ID_CARD_RATIO = 1.586  # Width / Height for standard ID card
        
        # Determine orientation (landscape or portrait)
        if maxWidth > maxHeight:
            # Landscape - width is larger
            expected_height = maxWidth / ID_CARD_RATIO
            if abs(maxHeight - expected_height) > maxHeight * 0.3:
                # Significant difference - use detected dimensions
                pass
            else:
                maxHeight = int(expected_height)
        else:
            # Portrait - height is larger
            expected_width = maxHeight / ID_CARD_RATIO
            if abs(maxWidth - expected_width) > maxWidth * 0.3:
                pass
            else:
                maxWidth = int(expected_width)
    
    # Destination points
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")
    
    # Perspective transform
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    
    return warped


def detect_largest_rectangle(image, use_simple_crop=False, debug=False):
    """
    Detect the largest rectangular contour in the image (likely the ID card).
    Uses multiple detection strategies for challenging images (hand-held, low contrast, etc.)
    
    Args:
        image: Input image
        use_simple_crop: If True, use simple bounding box (no perspective transform)
        debug: If True, show debug info
    
    Returns:
        Cropped image or None if no rectangle found
    """
    original = image.copy()
    height, width = image.shape[:2]
    
    # Resize for faster processing (keep aspect ratio)
    scale = 1.0
    if max(height, width) > 1000:
        scale = 1000 / max(height, width)
        image = cv2.resize(image, None, fx=scale, fy=scale)
    
    card_contour = None
    
    # Try multiple detection strategies
    strategies = [
        _detect_with_canny,
        _detect_with_adaptive_threshold,
        _detect_with_color_mask,
        _detect_with_morphology,
    ]
    
    for strategy in strategies:
        card_contour = strategy(image)
        if card_contour is not None:
            break
    
    if card_contour is None:
        return None
    
    # Scale contour back to original image size
    card_contour = card_contour.reshape(4, 2).astype("float32")
    card_contour = card_contour / scale
    
    if use_simple_crop:
        # Simple bounding box crop (no perspective transform = no stretching)
        x_coords = card_contour[:, 0]
        y_coords = card_contour[:, 1]
        
        x_min = max(0, int(np.min(x_coords)))
        x_max = min(width, int(np.max(x_coords)))
        y_min = max(0, int(np.min(y_coords)))
        y_max = min(height, int(np.max(y_coords)))
        
        # Add small padding
        padding = 5
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(width, x_max + padding)
        y_max = min(height, y_max + padding)
        
        cropped = original[y_min:y_max, x_min:x_max]
    else:
        # Apply perspective transform
        cropped = four_point_transform(original, card_contour)
    
    return cropped


def _find_card_contour(edges, image, min_area_ratio=0.05):
    """Helper to find card contour from edge image."""
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]
    
    image_area = image.shape[0] * image.shape[1]
    
    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        
        if len(approx) == 4:
            area = cv2.contourArea(approx)
            if area > image_area * min_area_ratio:
                return approx
    
    # Fallback: find any large contour and get its bounding box
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > image_area * (min_area_ratio + 0.05):
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
            return np.int0(box)
    
    return None


def _detect_with_canny(image):
    """Strategy 1: Standard Canny edge detection."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(gray, 30, 200)
    kernel = np.ones((5, 5), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=2)
    return _find_card_contour(edges, image)


def _detect_with_adaptive_threshold(image):
    """Strategy 2: Adaptive thresholding for low contrast images."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Adaptive threshold
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    # Invert if needed (card should be lighter)
    if np.mean(thresh) > 127:
        thresh = cv2.bitwise_not(thresh)
    
    kernel = np.ones((3, 3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=3)
    thresh = cv2.dilate(thresh, kernel, iterations=2)
    
    return _find_card_contour(thresh, image, min_area_ratio=0.03)


def _detect_with_color_mask(image):
    """Strategy 3: Detect light-colored regions (ID cards are usually white/light)."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Light color mask (low saturation, high value = white/cream colored)
    lower = np.array([0, 0, 150])
    upper = np.array([180, 80, 255])
    mask = cv2.inRange(hsv, lower, upper)
    
    kernel = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    
    return _find_card_contour(mask, image, min_area_ratio=0.03)


def _detect_with_morphology(image):
    """Strategy 4: Heavy morphology for noisy images."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Strong blur then threshold
    blur = cv2.GaussianBlur(gray, (11, 11), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Heavy morphological operations
    kernel = np.ones((9, 9), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=5)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    
    # Edge from the cleaned mask
    edges = cv2.Canny(thresh, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=2)
    
    return _find_card_contour(edges, image, min_area_ratio=0.03)


def process_folder(input_folder: str, output_folder: str, use_simple_crop: bool = False, extensions: list = None):
    """
    Process all images in input folder and save cropped versions to output folder.
    
    Args:
        input_folder: Source folder with images
        output_folder: Destination for cropped images
        use_simple_crop: If True, use simple bounding box (no perspective transform)
        extensions: List of image extensions to process
    """
    if extensions is None:
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
    
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    
    # Create output folder if doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Get all image files
    image_files = []
    for ext in extensions:
        image_files.extend(input_path.glob(f"*{ext}"))
        image_files.extend(input_path.glob(f"*{ext.upper()}"))
    
    if not image_files:
        print(f"❌ No images found in {input_folder}")
        return
    
    mode = "Simple Crop" if use_simple_crop else "Perspective Transform"
    print(f"📁 Found {len(image_files)} images to process")
    print(f"📂 Output folder: {output_folder}")
    print(f"🔧 Mode: {mode}")
    print("-" * 50)
    
    success_count = 0
    fail_count = 0
    
    for img_path in image_files:
        filename = img_path.name
        print(f"Processing: {filename}...", end=" ")
        
        # Read image
        image = cv2.imread(str(img_path))
        
        if image is None:
            print("❌ Failed to read")
            fail_count += 1
            continue
        
        # Detect and crop
        cropped = detect_largest_rectangle(image, use_simple_crop=use_simple_crop)
        
        if cropped is None:
            # Failed to detect - save original
            print("⚠️ No card detected, saving original")
            output_file = output_path / filename
            cv2.imwrite(str(output_file), image)
            fail_count += 1
        else:
            # Save cropped image (keep original filename)
            output_file = output_path / filename
            cv2.imwrite(str(output_file), cropped)
            print("✅ Cropped")
            success_count += 1
    
    print("-" * 50)
    print(f"✅ Successfully cropped: {success_count}")
    print(f"⚠️ Could not detect card: {fail_count}")
    print(f"📁 Output saved to: {output_folder}")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-crop ID cards from images using largest rectangle detection"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input folder containing images"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output folder for cropped images"
    )
    parser.add_argument(
        "--simple", "-s",
        action="store_true",
        help="Use simple bounding box crop (no perspective transform, prevents stretching)"
    )
    
    args = parser.parse_args()
    
    if not Path(args.input).exists():
        print(f"❌ Input folder does not exist: {args.input}")
        sys.exit(1)
    
    process_folder(args.input, args.output, use_simple_crop=args.simple)


if __name__ == "__main__":
    main()
