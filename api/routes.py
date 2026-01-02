"""
FastAPI Routes for e-KYC System.

Provides endpoints for:
- /verify: Full e-KYC verification (OCR + Face Match)
- /extract-id: Extract ID number from ID card
- /compare-faces: Compare two face images
- /process-batch: Batch process ID cards
- /health: Health check
"""
import cv2
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from models.schemas import (
    VerifyRequest, VerifyResponse,
    ExtractIDRequest, ExtractIDResponse,
    CompareFacesRequest, CompareFacesResponse,
    BatchProcessRequest, BatchProcessResponse,
    HealthResponse, OCRResult, FaceMatchResult
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


@router.post("/verify", response_model=VerifyResponse)
async def verify_identity_endpoint(
    id_number: str = Form(..., description="ID number to search for in the database"),
    selfie: UploadFile = File(..., description="Selfie image file")
):
    """
    e-KYC verification endpoint with ID lookup.
    
    1. Searches ID cards database for matching ID number using OCR
    2. Once found, extracts face from ID card
    3. Compares with selfie face
    4. Returns similarity score
    
    The similarity score is a value between 0.0 and 1.0 - 
    higher values indicate higher likelihood of same person.
    """
    try:
        # Import here to avoid circular imports
        from services.id_database import search_id_card_by_number
        
        # Load selfie image
        selfie_bytes = await selfie.read()
        selfie_image = load_image(selfie_bytes)
        
        # Step 1: Search for ID card in database
        search_result = search_id_card_by_number(id_number)
        
        if search_result is None:
            return VerifyResponse(
                success=False,
                extracted_id=id_number,
                id_type=None,
                similarity_score=None,
                error=f"ID card with number '{id_number}' not found in database"
            )
        
        card_path, id_card_image, ocr_result = search_result
        extracted_id = ocr_result.get("extracted_id")
        id_type = ocr_result.get("id_type")
        
        # Step 2: Face verification
        face_result = verify_identity(id_card_image, selfie_image)
        
        if face_result.get("error"):
            return VerifyResponse(
                success=False,
                extracted_id=extracted_id,
                id_type=id_type,
                similarity_score=None,
                error=face_result["error"]
            )
        
        return VerifyResponse(
            success=True,
            extracted_id=extracted_id,
            id_type=id_type,
            similarity_score=face_result["similarity_score"],
            error=None
        )
        
    except Exception as e:
        return VerifyResponse(
            success=False,
            extracted_id=None,
            id_type=None,
            similarity_score=None,
            error=str(e)
        )


@router.post("/verify-json", response_model=VerifyResponse)
async def verify_identity_json(request: VerifyRequest):
    """
    e-KYC verification using JSON body with ID number and selfie path/base64.
    
    Searches ID cards database for matching ID, then compares faces.
    """
    try:
        from services.id_database import search_id_card_by_number
        
        # Load selfie image
        if request.selfie_path:
            selfie_image = load_image(request.selfie_path)
        elif request.selfie_base64:
            selfie_image = load_image(request.selfie_base64)
        else:
            raise ValueError("Either selfie_path or selfie_base64 is required")
        
        # Search for ID card in database
        search_result = search_id_card_by_number(request.id_number)
        
        if search_result is None:
            return VerifyResponse(
                success=False,
                extracted_id=request.id_number,
                id_type=None,
                similarity_score=None,
                error=f"ID card with number '{request.id_number}' not found in database"
            )
        
        card_path, id_card_image, ocr_result = search_result
        extracted_id = ocr_result.get("extracted_id")
        id_type = ocr_result.get("id_type")
        
        # Face verification
        face_result = verify_identity(id_card_image, selfie_image)
        
        if face_result.get("error"):
            return VerifyResponse(
                success=False,
                extracted_id=extracted_id,
                id_type=id_type,
                similarity_score=None,
                error=face_result["error"]
            )
        
        return VerifyResponse(
            success=True,
            extracted_id=extracted_id,
            id_type=id_type,
            similarity_score=face_result["similarity_score"],
            error=None
        )
        
    except Exception as e:
        return VerifyResponse(
            success=False,
            extracted_id=None,
            id_type=None,
            similarity_score=None,
            error=str(e)
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
        
        result = extract_id_from_image(id_card_image)
        
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
        
        result = compare_faces(img1, img2)
        
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


@router.post("/process-batch", response_model=BatchProcessResponse)
async def process_batch_endpoint(request: BatchProcessRequest):
    """
    Batch process ID cards from a directory.
    
    Extracts IDs and renames images for efficient lookup.
    """
    try:
        directory = Path(request.id_cards_directory)
        
        if not directory.exists():
            return BatchProcessResponse(
                success=False,
                processed_count=0,
                failed_count=0,
                results=[],
                errors=[f"Directory not found: {directory}"]
            )
        
        results = []
        errors = []
        processed = 0
        failed = 0
        
        # Find all image files
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
        image_files = [
            f for f in directory.iterdir() 
            if f.suffix.lower() in image_extensions
        ]
        
        for image_file in image_files:
            try:
                image = cv2.imread(str(image_file))
                if image is None:
                    errors.append(f"Could not read: {image_file.name}")
                    failed += 1
                    continue
                
                ocr_result = extract_id_from_image(image)
                extracted_id = ocr_result.get("extracted_id")
                
                if extracted_id:
                    # Rename and save
                    new_path = rename_by_id(image_file, extracted_id)
                    results.append({
                        "original": image_file.name,
                        "extracted_id": extracted_id,
                        "id_type": ocr_result.get("id_type"),
                        "new_path": str(new_path)
                    })
                    processed += 1
                else:
                    errors.append(f"No ID found in: {image_file.name}")
                    failed += 1
                    
            except Exception as e:
                errors.append(f"Error processing {image_file.name}: {str(e)}")
                failed += 1
        
        return BatchProcessResponse(
            success=True,
            processed_count=processed,
            failed_count=failed,
            results=results,
            errors=errors
        )
        
    except Exception as e:
        return BatchProcessResponse(
            success=False,
            processed_count=0,
            failed_count=0,
            results=[],
            errors=[str(e)]
        )
