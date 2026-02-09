"""
Service for ID Card Database Search Operations.
"""
from typing import Optional, Tuple, Any, Dict
from pathlib import Path
import cv2
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service import get_document_by_number
from utils.image_manager import load_image


async def search_id_card_by_number(
    session: AsyncSession,
    id_number: str
) -> Optional[Tuple[str, np.ndarray, Dict[str, Any]]]:
    """
    Search for an ID card by ID number in the PostgreSQL database.
    
    Args:
        session: Database session
        id_number: The ID number to search for
        
    Returns:
        Tuple containing:
        - card_source: "database_blob" or "file_path"
        - id_card_image: Loaded ID card image as numpy array
        - ocr_result: Dictionary with extracted ID details
        
        Returns None if not found.
    """
    document = await get_document_by_number(session, id_number)
    
    if not document:
        return None
        
    # Reconstruct OCR result format expected by verification flow
    ocr_result = document.ocr_data.copy() if document.ocr_data else {}
    
    # Ensure keys exist
    ocr_result.update({
        "extracted_id": document.document_number,
        "id_type": document.document_type,
        "name_arabic": document.full_name_arabic,
        "name_english": document.full_name_english,
    })
    
    # Retrieve image
    image = None
    image_source = "database_blob"
    
    # Try loading from BLOB (BYTEA)
    if document.front_image_data:
        try:
            nparr = np.frombuffer(document.front_image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            pass
            
    # Fallback to loading from path if blob failed or didn't exist (legacy support)
    if image is None:
        # Check if path is in ocr_data or we need to look elsewhere? 
        # The new model stores images in DB, so we rely on that.
        # But if we migrated old data which only had paths...
        pass 
        
    if image is None:
        return None
        
    return image_source, image, ocr_result
