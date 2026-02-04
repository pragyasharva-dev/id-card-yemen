"""
FastAPI Production Routes for e-KYC System.

These endpoints return scores and raw data for SDK/app integration.
For decision-making endpoints (approved/rejected/manual_review),
use the test routes in test_routes.py.

Endpoints:
- /health: Health check
- /extract-id: Extract ID number from ID card
- /parse-id: Parse full ID card data
- /compare-faces: Compare faces and return similarity score
- /translate: Translate Arabic texts to English
"""
import cv2
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool

from models.schemas import (
    ExtractIDRequest, ExtractIDResponse,
    CompareFacesRequest, CompareFacesResponse,
    HealthResponse, OCRResult, FaceMatchResult,
    TranslateRequest, TranslateResponse, TranslatedText,
)
from services.ocr_service import extract_id_from_image, get_ocr_service
from services.face_recognition import verify_identity, compare_faces, is_ready as face_ready
from services.face_extractor import is_available as insightface_available
from utils.image_manager import load_image, rename_by_id, save_image
from utils.config import ID_CARDS_DIR, PROCESSED_DIR


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check if the service is healthy and all models are loaded.
    """
    ocr_ready = False
    face_recognition_ready = False
    
    try:
        get_ocr_service()
        ocr_ready = True
    except Exception:
        pass
    
    try:
        face_recognition_ready = face_ready()
    except Exception:
        pass
    
    return HealthResponse(
        status="ok",
        ocr_ready=ocr_ready,
        face_recognition_ready=face_recognition_ready
    )


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

@router.post("/compare-faces", response_model=CompareFacesResponse)
async def compare_faces_endpoint(
    image1: UploadFile = File(..., description="First image (e.g., ID card)"),
    image2: UploadFile = File(..., description="Second image (e.g., selfie)")
):
    """
    Compare faces in two images.
    
    Returns a similarity score between 0.0 and 1.0.
    """
    try:
        image1_bytes = await image1.read()
        image2_bytes = await image2.read()
        
        img1 = load_image(image1_bytes)
        img2 = load_image(image2_bytes)
        
        result = await run_in_threadpool(compare_faces, img1, img2)
        
        if result.get("error"):
            return CompareFacesResponse(
                success=False,
                similarity_score=None,
                error=result["error"]
            )
        
        return CompareFacesResponse(
            success=True,
            similarity_score=result["similarity_score"],
            error=None
        )
        
    except Exception as e:
        return CompareFacesResponse(
            success=False,
            similarity_score=None,
            error=str(e)
        )


@router.post("/translate", response_model=TranslateResponse)
async def translate_texts_endpoint(request: TranslateRequest):
    """
    Translate Arabic texts to English.
    
    Called on-demand when user clicks Translate button in the UI.
    Uses Google Translate via deep-translator library.
    """
    try:
        from services.translation_service import translate_arabic_to_english
        
        if not request.texts:
            return TranslateResponse(
                success=True,
                translations=[],
                error=None
            )
        
        # Translate all texts
        results = await run_in_threadpool(translate_arabic_to_english, request.texts)
        
        translations = [
            TranslatedText(
                original=r["original"],
                translated=r["translated"]
            )
            for r in results
        ]
        
        return TranslateResponse(
            success=True,
            translations=translations,
            error=None
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )
