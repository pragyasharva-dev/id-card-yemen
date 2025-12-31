"""
Image management utilities for loading, saving, and organizing images.
"""
import base64
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Union

from .config import PROCESSED_DIR, SUPPORTED_IMAGE_FORMATS, MAX_IMAGE_SIZE


def load_image(source: Union[str, Path, bytes]) -> np.ndarray:
    """
    Load an image from various sources.
    
    Args:
        source: Can be a file path (str/Path), base64 string, or raw bytes
        
    Returns:
        numpy array of the image in BGR format
        
    Raises:
        ValueError: If image cannot be loaded
    """
    if isinstance(source, (str, Path)):
        source_path = Path(source)
        
        # Check if it's a file path
        if source_path.exists():
            img = cv2.imread(str(source_path))
            if img is None:
                raise ValueError(f"Could not read image from: {source_path}")
            return img
        
        # Maybe it's a base64 string
        try:
            img_bytes = base64.b64decode(source)
            return _bytes_to_image(img_bytes)
        except Exception:
            raise ValueError(f"Invalid image source: {source}")
    
    elif isinstance(source, bytes):
        return _bytes_to_image(source)
    
    else:
        raise ValueError(f"Unsupported image source type: {type(source)}")


def _bytes_to_image(img_bytes: bytes) -> np.ndarray:
    """Convert bytes to OpenCV image."""
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image from bytes")
    return img


def save_image(
    image: np.ndarray,
    filename: str,
    directory: Optional[Path] = None
) -> Path:
    """
    Save an image to disk.
    
    Args:
        image: numpy array of the image
        filename: name of the file (with extension)
        directory: target directory (defaults to PROCESSED_DIR)
        
    Returns:
        Path to the saved image
    """
    if directory is None:
        directory = PROCESSED_DIR
    
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    
    filepath = directory / filename
    cv2.imwrite(str(filepath), image)
    
    return filepath


def rename_by_id(
    image_path: Union[str, Path],
    id_number: str,
    suffix: str = "_id"
) -> Path:
    """
    Rename an image file using the extracted ID number.
    
    Args:
        image_path: Path to the original image
        id_number: Extracted ID number for naming
        suffix: Suffix to add before extension (e.g., "_id")
        
    Returns:
        Path to the renamed image in PROCESSED_DIR
    """
    image_path = Path(image_path)
    extension = image_path.suffix.lower()
    
    if extension not in SUPPORTED_IMAGE_FORMATS:
        extension = ".png"
    
    # Create new filename
    new_filename = f"{id_number}{suffix}{extension}"
    
    # Load and save to new location
    img = load_image(image_path)
    new_path = save_image(img, new_filename, PROCESSED_DIR)
    
    return new_path


def get_image_path(id_number: str, suffix: str = "_id") -> Optional[Path]:
    """
    Find an image by its ID number (O(1) lookup by filename).
    
    Args:
        id_number: The ID number to search for
        suffix: Suffix used when saving
        
    Returns:
        Path to the image if found, None otherwise
    """
    for ext in SUPPORTED_IMAGE_FORMATS:
        filepath = PROCESSED_DIR / f"{id_number}{suffix}{ext}"
        if filepath.exists():
            return filepath
    
    return None


def resize_image(
    image: np.ndarray,
    max_size: Tuple[int, int] = MAX_IMAGE_SIZE
) -> np.ndarray:
    """
    Resize image if it exceeds maximum dimensions.
    
    Args:
        image: Input image
        max_size: Maximum (width, height)
        
    Returns:
        Resized image (or original if within limits)
    """
    h, w = image.shape[:2]
    max_w, max_h = max_size
    
    if w <= max_w and h <= max_h:
        return image
    
    # Calculate scaling factor
    scale = min(max_w / w, max_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def image_to_base64(image: np.ndarray, format: str = ".png") -> str:
    """
    Convert image to base64 string.
    
    Args:
        image: numpy array of the image
        format: image format extension
        
    Returns:
        Base64 encoded string
    """
    _, buffer = cv2.imencode(format, image)
    return base64.b64encode(buffer).decode("utf-8")
