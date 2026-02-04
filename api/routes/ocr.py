"""OCR and ID extraction endpoints."""
from fastapi import APIRouter, UploadFile, File
from fastapi.concurrency import run_in_threadpool

from models.schemas import ExtractIDResponse, OCRResult
from services.ocr_service import extract_id_from_image
from utils.image_manager import load_image

router = APIRouter(tags=["OCR"])


@router.post("/extract-id", response_model=ExtractIDResponse)
async def extract_id_endpoint(
    image: UploadFile = File(..., description="ID card image file")
):
    """
    Extract unique ID number from an ID card image.
    
    Uses OCR and intelligent pattern matching to identify the unique ID.
    """
    try:
        image_bytes = await image.read()
        id_card_image = load_image(image_bytes)
        
        result = await run_in_threadpool(extract_id_from_image, id_card_image)
        
        return ExtractIDResponse(
            success=True,
            ocr_result=OCRResult(
                extracted_id=result.get("extracted_id"),
                id_type=result.get("id_type"),
                confidence=result.get("confidence", 0.0),
                all_texts=result.get("all_texts", []),
                text_results=result.get("text_results", []),
                detected_languages=result.get("detected_languages", []),
                detected_languages_display=result.get("detected_languages_display", [])
            ),
            error=None
        )
        
    except Exception as e:
        return ExtractIDResponse(
            success=False,
            ocr_result=None,
            error=str(e)
        )


@router.post("/parse-id")
async def parse_id_endpoint(
    image: UploadFile = File(..., description="ID card image file")
):
    """
    Parse full ID card data including all fields.
    
    Extracts: ID number, name (Arabic/English), DOB, gender, 
    place of birth, issuance/expiry dates.
    """
    try:
        from services.id_card_parser import parse_yemen_id_card
        
        image_bytes = await image.read()
        id_card_image = load_image(image_bytes)
        
        # Get OCR result
        ocr_result = await run_in_threadpool(extract_id_from_image, id_card_image)
        
        # Parse into structured data
        parsed_data = await run_in_threadpool(parse_yemen_id_card, ocr_result, None)
        
        return {
            "success": True,
            "id_number": parsed_data.get("id_number"),
            "name_arabic": parsed_data.get("name_arabic"),
            "name_english": parsed_data.get("name_english"),
            "date_of_birth": parsed_data.get("date_of_birth"),
            "gender": parsed_data.get("gender"),
            "place_of_birth": parsed_data.get("place_of_birth"),
            "issuance_date": parsed_data.get("issuance_date"),
            "expiry_date": parsed_data.get("expiry_date"),
            "blood_type": parsed_data.get("blood_type"),
            "id_type": ocr_result.get("id_type", "yemen_id"),
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
