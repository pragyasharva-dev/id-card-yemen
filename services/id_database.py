"""
ID Card Database Service.

Handles searching and retrieving ID cards from the local database (folder).
"""
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, List

from utils.config import ID_CARDS_DIR, SUPPORTED_IMAGE_FORMATS
from services.ocr_service import extract_id_from_image


def get_all_id_card_paths() -> List[Path]:
    """
    Get all ID card image paths from the database folder.
    
    Returns:
        List of paths to ID card images
    """
    paths = []
    for ext in SUPPORTED_IMAGE_FORMATS:
        paths.extend(ID_CARDS_DIR.glob(f"*{ext}"))
    return paths


def search_id_card_by_number(id_number: str) -> Optional[Tuple[Path, np.ndarray, Dict]]:
    """
    Search for an ID card in the database by ID number.
    
    Iterates through all ID cards in the database folder, extracts
    the ID number using OCR, and returns the matching card.
    
    Args:
        id_number: The ID number to search for
        
    Returns:
        Tuple of (file_path, image, ocr_result) if found, None otherwise
    """
    id_card_paths = get_all_id_card_paths()
    
    # Clean the input ID number for comparison
    search_id = id_number.strip().upper().replace(" ", "").replace("-", "")
    
    for card_path in id_card_paths:
        try:
            # Load the image
            image = cv2.imread(str(card_path))
            if image is None:
                continue
            
            # Extract ID from this card
            ocr_result = extract_id_from_image(image)
            extracted_id = ocr_result.get("extracted_id")
            
            if extracted_id:
                # Clean the extracted ID for comparison
                clean_extracted = extracted_id.strip().upper().replace(" ", "").replace("-", "")
                
                # Check if it matches
                if clean_extracted == search_id:
                    return card_path, image, ocr_result
                    
        except Exception:
            continue
    
    return None


def get_id_card_stats() -> Dict:
    """
    Get statistics about the ID card database.
    
    Returns:
        Dictionary with database stats
    """
    paths = get_all_id_card_paths()
    return {
        "total_cards": len(paths),
        "database_path": str(ID_CARDS_DIR),
        "card_files": [p.name for p in paths]
    }
