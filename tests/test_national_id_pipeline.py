"""
Test script for National ID YOLO + OCR pipeline.

Usage:
    .venv\Scripts\activate
    python tests/test_national_id_pipeline.py <image_path> [--side front|back]

Example:
    python tests/test_national_id_pipeline.py data/id_cards/sample_front.jpg --side front
    python tests/test_national_id_pipeline.py data/id_cards/sample_back.jpg --side back -v
"""
import sys
import argparse
import cv2
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.layout_service import get_layout_service, is_layout_available
from services.ocr_service import get_ocr_service


def test_layout_detection(image_path: str, side: str = "front"):
    """Test YOLO layout detection on an image."""
    print(f"\n{'='*60}")
    print(f"YOLO Layout Detection Test")
    print(f"{'='*60}")
    print(f"Image: {image_path}")
    print(f"Side:  {side}")
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"ERROR: Could not load image: {image_path}")
        return None
    
    print(f"Size:  {image.shape[1]}x{image.shape[0]}")
    
    # Check if model is available
    model_key = f"yemen_id_{side}"
    if not is_layout_available(model_key):
        print(f"ERROR: Model '{model_key}' not available")
        return None
    
    # Run layout detection
    print(f"\n--- YOLO Detection ---")
    layout_service = get_layout_service()
    layout_fields = layout_service.detect_layout(image, model_key)
    
    if not layout_fields:
        print("No fields detected")
        return {}
    
    print(f"Detected {len(layout_fields)} fields:")
    for label, field in layout_fields.items():
        print(f"  {label:20} conf={field.confidence:.1%}  box={field.box}")
    
    return layout_fields


def test_full_pipeline(image_path: str, side: str = "front"):
    """Test full YOLO + OCR pipeline."""
    print(f"\n{'='*60}")
    print(f"Full YOLO + OCR Pipeline Test")
    print(f"{'='*60}")
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"ERROR: Could not load image: {image_path}")
        return None
    
    # Run OCR service (which now uses YOLO first)
    print(f"Processing...")
    ocr_service = get_ocr_service()
    result = ocr_service.process_id_card(image, side=side)
    
    # Display results
    print(f"\n--- Results ---")
    print(f"Method:     {result.get('extraction_method', 'unknown')}")
    print(f"ID Number:  {result.get('extracted_id')}")
    print(f"ID Type:    {result.get('id_type')}")
    print(f"Confidence: {result.get('confidence', 0):.1%}")
    
    # Show layout fields if YOLO was used
    layout_fields = result.get('layout_fields', {})
    if layout_fields:
        print(f"\n--- Extracted Fields ---")
        for label, data in layout_fields.items():
            text = data.get('text', '')[:60]  # Truncate long text
            conf = data.get('confidence', 0)
            langs = data.get('ocr_lang', ['?'])
            
            # Show validation info for unique_id
            if label == 'unique_id' and 'validation' in data:
                validation = data.get('validation', '?')
                candidates = data.get('candidates', [])
                print(f"  {label:20} '{text}'  (conf={conf:.1%})")
                print(f"    └─ Validation: {validation}")
                if candidates:
                    print(f"       Candidates: {candidates}")
            else:
                print(f"  {label:20} [{','.join(langs):5}] '{text}'  (conf={conf:.1%})")
    
    return result


def save_detection_visualization(image_path: str, layout_fields: dict, output_dir: str = None):
    """Save image with bounding boxes and individual crops."""
    image = cv2.imread(image_path)
    if image is None:
        return
    
    # Create output directory
    if output_dir is None:
        output_dir = Path(image_path).stem + "_detections"
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    colors = {
        'DOB': (0, 255, 0),
        'POB': (255, 0, 0),
        'name': (0, 0, 255),
        'unique_id': (255, 255, 0),
        'expiry_data': (255, 0, 255),
        'issue_date': (0, 255, 255),
        'issuing_authority': (128, 128, 0),
        'id_card': (128, 0, 128),
    }
    
    # Draw boxes and save crops
    for label, field in layout_fields.items():
        x1, y1, x2, y2 = field.box
        color = colors.get(label, (200, 200, 200))
        
        # Draw on main image
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, f"{label} ({field.confidence:.0%})", 
                    (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Save individual crop
        crop_path = output_path / f"{label}.jpg"
        cv2.imwrite(str(crop_path), field.crop)
        print(f"  Saved crop: {crop_path}")
    
    # Save main image with boxes
    main_image_path = output_path / "detected.jpg"
    cv2.imwrite(str(main_image_path), image)
    print(f"\nSaved visualization to: {output_path}/")
    print(f"  - detected.jpg (full image with boxes)")
    print(f"  - Individual crops: {', '.join([f'{l}.jpg' for l in layout_fields.keys()])}")


def main():
    parser = argparse.ArgumentParser(description="Test YOLO + OCR pipeline")
    parser.add_argument("image_path", help="Path to ID card image")
    parser.add_argument("--side", choices=["front", "back"], default="front",
                        help="Card side (front or back)")
    parser.add_argument("--visualize", "-v", action="store_true",
                        help="Save visualization with bounding boxes")
    parser.add_argument("--output", "-o", help="Output path for visualization")
    
    args = parser.parse_args()
    
    # Check image exists
    if not Path(args.image_path).exists():
        print(f"ERROR: Image not found: {args.image_path}")
        sys.exit(1)
    
    # Test layout detection alone
    layout_fields = test_layout_detection(args.image_path, args.side)
    
    # Test full pipeline
    result = test_full_pipeline(args.image_path, args.side)
    
    # Save visualization if requested
    if args.visualize and layout_fields:
        save_detection_visualization(args.image_path, layout_fields, args.output)
    
    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
