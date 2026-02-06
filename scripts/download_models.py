"""
Model Download Script for Offline Deployment.

Downloads PaddleOCR and InsightFace models to a local `models/` directory
so the application can run without internet access.

Usage:
    python scripts/download_models.py

This script should be run ONCE during build/deployment to prepare offline artifacts.
"""
import os
import sys
import shutil
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def download_paddleocr_models(target_dir: Path):
    """Download PaddleOCR models to local directory."""
    print("Downloading PaddleOCR models...")
    
    from paddleocr import PaddleOCR
    
    # Create target directories
    paddle_dir = target_dir / "paddleocr"
    paddle_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize models to trigger download (they cache in ~/.paddleocr)
    languages = ['en', 'ar']
    
    for lang in languages:
        print(f"  - Downloading {lang} model...")
        try:
            ocr = PaddleOCR(
                use_angle_cls=False,
                lang=lang
            )
            print(f"  {lang} model ready")
        except Exception as e:
            print(f"  Failed to download {lang}: {e}")
    
    # Copy cached models to our target directory
    home_paddle = Path.home() / ".paddleocr"
    if home_paddle.exists():
        print(f"  Copying from {home_paddle} to {paddle_dir}")
        for item in home_paddle.iterdir():
            dest = paddle_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        print("  PaddleOCR models copied")
    else:
        print("  PaddleOCR cache not found, models will be in default location")


def download_insightface_models(target_dir: Path):
    """Download InsightFace models to local directory."""
    print("Downloading InsightFace models...")
    
    try:
        from insightface.app import FaceAnalysis
    except ImportError:
        print("  InsightFace not installed. Skipping.")
        return
    
    # Create target directory
    insight_dir = target_dir / "insightface"
    insight_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize model to trigger download
    print("  - Downloading buffalo_l model...")
    try:
        app = FaceAnalysis(
            name="buffalo_l",
            providers=['CPUExecutionProvider']
        )
        app.prepare(ctx_id=0, det_size=(640, 640))
        print("  buffalo_l model ready")
    except Exception as e:
        print(f"  Failed to download buffalo_l: {e}")
    
    # Copy cached models to our target directory
    home_insight = Path.home() / ".insightface"
    if home_insight.exists():
        print(f"  Copying from {home_insight} to {insight_dir}")
        for item in home_insight.iterdir():
            dest = insight_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        print("  InsightFace models copied")
    else:
        print("  InsightFace cache not found, models will be in default location")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Model Download Script for Offline Deployment")
    print("=" * 60)
    
    # Target directory
    project_root = Path(__file__).parent.parent
    target_dir = project_root / "models"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Target directory: {target_dir}")
    print()
    
    # Download models
    download_paddleocr_models(target_dir)
    print()
    download_insightface_models(target_dir)
    
    print()
    print("=" * 60)
    print("Model download complete!")
    print(f"Models saved to: {target_dir}")
    print()
    print("Next steps:")
    print("  1. Set environment variable: MODELS_DIR=./models")
    print("  2. Or update utils/config.py with MODELS_DIR path")
    print("=" * 60)


if __name__ == "__main__":
    main()
