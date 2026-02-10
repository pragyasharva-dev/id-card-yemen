
import os
import cv2
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

try:
    from services.layout_service import get_layout_service
    from services.ocr_service import get_ocr_service
    import ultralytics
    print(f"Ultralytics version: {ultralytics.__version__}")
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_layout():
    print("Initializing Layout Service...")
    service = get_layout_service()
    
    print(f"Loaded models: {list(service.models.keys())}")
    
    for key, model in service.models.items():
        print(f"\nModel: {key}")
        if hasattr(model, 'names'):
            print(f"Classes: {model.names}")
        else:
            print("Classes: Unknown (no names attribute)")

    if not service.models:
        print("❌ No YOLO models loaded!")
        return

    # Create a dummy image or load one if available
    img_path = r"c:\Users\sujat\Desktop\OneCash\id-card-yemen\data\processed\01011291433_front_1770639577.jpg"
    if os.path.exists(img_path):
        img = cv2.imread(img_path)
        print(f"Running inference on {img_path}...")
        results = service.detect_layout(img, "yemen_id_front")
        print("Layout Results keys:", results.keys())
        for k, v in results.items():
            print(f" - {k}: {v.label} ({v.confidence:.2f})")
    else:
        print("⚠️ No test_id.jpg found. Please place an ID card image named 'test_id.jpg' in this folder to test inference.")

if __name__ == "__main__":
    test_layout()
