"""
Test script for Passport YOLO + OCR + MRZ pipeline.

Usage:
    .venv\Scripts\activate
    python tests/test_passport_pipeline.py <image_path>
    python tests/test_passport_pipeline.py <image_path> --visualize

Example:
    python tests/test_passport_pipeline.py data/passports/sample.jpg
    python tests/test_passport_pipeline.py data/passports/sample.jpg -v
"""
import sys
import argparse
import cv2
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.layout_service import get_layout_service, is_layout_available
from services.passport_ocr_service import extract_passport_data


def test_layout_detection(image_path: str):
    """Test YOLO layout detection on a passport image."""
    print(f"\n{'='*60}")
    print(f"YOLO Passport Layout Detection Test")
    print(f"{'='*60}")
    print(f"Image: {image_path}")
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"ERROR: Could not load image: {image_path}")
        return None
    
    print(f"Size:  {image.shape[1]}x{image.shape[0]}")
    
    # Check if model is available
    model_key = "yemen_passport"
    if not is_layout_available(model_key):
        print(f"ERROR: Model '{model_key}' not available")
        print(f"       Make sure 'models/yemen-passport.pt' exists")
        return None
    
    # Run layout detection (return_all=True for multiple MRZ lines)
    print(f"\n--- YOLO Detection ---")
    layout_service = get_layout_service()
    layout_fields = layout_service.detect_layout(image, model_key, return_all=True)
    
    if not layout_fields:
        print("No fields detected")
        return {}
    
    print(f"Detected {len(layout_fields)} field types:")
    for label, fields in layout_fields.items():
        if isinstance(fields, list):
            print(f"  {label:25} x{len(fields)} detections")
            for i, field in enumerate(fields):
                print(f"    [{i}] conf={field.confidence:.1%}  box={field.box}")
        else:
            print(f"  {label:25} conf={fields.confidence:.1%}  box={fields.box}")
    
    return layout_fields


def test_full_pipeline(image_path: str):
    """Test full Passport YOLO + OCR + MRZ pipeline."""
    print(f"\n{'='*60}")
    print(f"Full Passport Extraction Pipeline Test")
    print(f"{'='*60}")
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"ERROR: Could not load image: {image_path}")
        return None
    
    # Run full extraction
    print(f"Processing...")
    result = extract_passport_data(image)
    
    # Display results
    print(f"\n--- Extraction Results ---")
    print(f"Success:     {result.get('success')}")
    print(f"Method:      {result.get('extraction_method', 'unknown')}")
    
    if not result.get("success"):
        print(f"Error:       {result.get('error')}")
        print(f"Suggestion:  {result.get('suggestion')}")
        return result
    
    print(f"\n--- Core Fields (MRZ Priority) ---")
    print(f"Passport No: {result.get('passport_number')}")
    print(f"Given Names: {result.get('given_names')}")
    print(f"Surname:     {result.get('surname')}")
    print(f"Full Name:   {result.get('name_english')}")
    print(f"DOB:         {result.get('date_of_birth')}")
    print(f"Gender:      {result.get('gender')}")
    print(f"Expiry:      {result.get('expiry_date')}")
    print(f"Nationality: {result.get('nationality')}")
    print(f"Country:     {result.get('country_code')}")
    
    print(f"\n--- Supplementary Fields (YOLO OCR) ---")
    print(f"Place Birth: {result.get('place_of_birth')}")
    print(f"Issue Date:  {result.get('issuance_date')}")
    print(f"Authority:   {result.get('issuing_authority')}")
    print(f"Profession:  {result.get('profession')}")
    
    print(f"\n--- Arabic Fields ---")
    print(f"Given (AR):  {result.get('given_name_arabic')}")
    print(f"Surname(AR): {result.get('surname_arabic')}")
    
    print(f"\n--- MRZ Validation ---")
    print(f"MRZ Valid:   {result.get('mrz_valid')}")
    print(f"Confidence:  {result.get('mrz_confidence', 0):.1%}")
    mrz_raw = result.get("mrz_raw", {})
    if mrz_raw.get("line1"):
        print(f"MRZ Line 1:  {mrz_raw.get('line1')}")
        print(f"MRZ Line 2:  {mrz_raw.get('line2')}")
    
    print(f"\n--- Debug Info ---")
    print(f"Detected Labels: {result.get('detected_labels', [])}")
    
    return result


def save_detection_visualization(image_path: str, layout_fields: dict, output_dir: str = None):
    """Save image with bounding boxes and individual crops."""
    image = cv2.imread(image_path)
    if image is None:
        return
    
    # Create output directory
    if output_dir is None:
        output_dir = Path(image_path).stem + "_passport_detections"
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Colors for different field types
    colors = {
        'MRZ': (0, 255, 255),           # Yellow
        'passport_no': (255, 255, 0),   # Cyan
        'DOB': (0, 255, 0),             # Green
        'POB': (255, 0, 0),             # Blue
        'expiry_date': (255, 0, 255),   # Magenta
        'Issue_date': (0, 128, 255),    # Orange
        'GivenName_eng': (0, 200, 0),   # Green
        'GivenName_arabic': (0, 150, 0),
        'surname_eng': (200, 0, 0),     # Red
        'surname_arabic': (150, 0, 0),
        'Profession_eng': (128, 128, 0),
        'Profession_arabic': (100, 100, 0),
        'Issuing_authority_eng': (128, 0, 128),
        'Issuing_authority_arabic': (100, 0, 100),
        'country_code': (0, 128, 128),
        'type': (64, 64, 64),
    }
    
    # Draw boxes and save crops
    for label, fields in layout_fields.items():
        # Handle both single field and list of fields
        field_list = fields if isinstance(fields, list) else [fields]
        color = colors.get(label, (200, 200, 200))
        
        for i, field in enumerate(field_list):
            x1, y1, x2, y2 = field.box
            
            # Draw on main image
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            label_text = f"{label}" if len(field_list) == 1 else f"{label}[{i}]"
            cv2.putText(image, f"{label_text} ({field.confidence:.0%})", 
                        (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            # Save individual crop
            suffix = f"_{i}" if len(field_list) > 1 else ""
            crop_path = output_path / f"{label}{suffix}.jpg"
            cv2.imwrite(str(crop_path), field.crop)
            print(f"  Saved crop: {crop_path}")
    
    # Save main image with boxes
    main_image_path = output_path / "detected.jpg"
    cv2.imwrite(str(main_image_path), image)
    print(f"\nSaved visualization to: {output_path}/")
    print(f"  - detected.jpg (full image with boxes)")


def main():
    parser = argparse.ArgumentParser(description="Test Passport YOLO + OCR + MRZ pipeline")
    parser.add_argument("image_path", help="Path to passport image")
    parser.add_argument("--visualize", "-v", action="store_true",
                        help="Save visualization with bounding boxes")
    parser.add_argument("--output", "-o", help="Output path for visualization")
    parser.add_argument("--layout-only", "-l", action="store_true",
                        help="Only test layout detection (skip OCR)")
    
    args = parser.parse_args()
    
    # Check image exists
    if not Path(args.image_path).exists():
        print(f"ERROR: Image not found: {args.image_path}")
        sys.exit(1)
    
    # Test layout detection
    layout_fields = test_layout_detection(args.image_path)
    
    # Test full pipeline (unless layout-only mode)
    if not args.layout_only:
        result = test_full_pipeline(args.image_path)
    
    # Save visualization if requested
    if args.visualize and layout_fields:
        save_detection_visualization(args.image_path, layout_fields, args.output)
    
    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
