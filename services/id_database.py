"""
Service for ID Card Database Search Operations.
"""
from typing import Optional, Tuple, Any, Dict
from pathlib import Path
import cv2
import numpy as np

from services.database import get_id_card_db
from utils.image_manager import load_image


def search_id_card_by_number(id_number: str) -> Optional[Tuple[str, np.ndarray, Dict[str, Any]]]:
    """
    Search for an ID card by ID number in the database.
    
    Args:
        id_number: The ID number to search for
        
    Returns:
        Tuple containing:
        - card_path: Path to the ID card image
        - id_card_image: Loaded ID card image as numpy array
        - ocr_result: Dictionary with extracted ID details
        
        Returns None if not found.
    """
    db = get_id_card_db()
    record = db.get_by_national_id(id_number)
    
    if not record:
        return None
        
    # Reconstruct OCR result format expected by verification flow
    # Construct full names from parts if available
    name_arabic_parts = [
        record.get("first_name_arabic"), 
        record.get("middle_name_arabic"), 
        record.get("last_name_arabic")
    ]
    name_arabic = " ".join([p for p in name_arabic_parts if p])
    
    name_english_parts = [
        record.get("first_name_english"), 
        record.get("middle_name_english"), 
        record.get("last_name_english")
    ]
    name_english = " ".join([p for p in name_english_parts if p])

    ocr_result = {
        "extracted_id": record["national_id"],
        "id_type": "yemen_id",
        "confidence": 1.0,  # Assume 100% confidence for database records
        "name_arabic": name_arabic,
        "name_english": name_english,
        "date_of_birth": record.get("date_of_birth"),
        "gender": record.get("gender"),
        "place_of_birth": record.get("place_of_birth"),
        "issuance_date": record.get("issuance_date"),
        "expiry_date": record.get("expiry_date")
    }
    
    # Retrieve image
    # Try to get the image from blob first, then path
    image = None
    image_path = record.get("front_image_path")
    
    # Try loading from BLOB first (most reliable if saved via API)
    if record.get("front_image_blob"):
        try:
            nparr = np.frombuffer(record["front_image_blob"], np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image_path is None:
                image_path = "database_blob"
        except Exception:
            pass
            
    # Fallback to loading from path
    if image is None and image_path and Path(image_path).exists():
        image = load_image(image_path)
        
    if image is None:
        # Record exists but no image available for face verification
        return None
        
    return image_path, image, ocr_result
