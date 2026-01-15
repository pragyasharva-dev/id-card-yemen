"""
FastAPI Routes for e-KYC System.

Provides endpoints for:
- /verify: Full e-KYC verification (OCR + Face Match)
- /extract-id: Extract ID number from ID card
- /compare-faces: Compare two face images
- /translate: Translate Arabic texts to English
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
    HealthResponse, OCRResult, FaceMatchResult,
    TranslateRequest, TranslateResponse, TranslatedText
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
    id_card_front: UploadFile = File(..., description="ID card front side image"),
    selfie: UploadFile = File(..., description="Selfie image file"),
    id_card_back: UploadFile = File(None, description="ID card back side image (optional)")
):
    """
    e-KYC verification endpoint with optional front and back ID card support.
    
    1. Receives ID card front (required) and optionally back side
    2. Extracts ID number and structured data from front card
    3. Extracts face from front card
    4. Compares with selfie face
    5. Returns extracted data and similarity score
    
    The similarity score is a value between 0.0 and 1.0 - 
    higher values indicate higher likelihood of same person.
    """
    try:
        from services.id_card_parser import parse_yemen_id_card
        
        # Load front ID card and selfie
        id_card_front_bytes = await id_card_front.read()
        selfie_bytes = await selfie.read()
        
        id_card_front_image = load_image(id_card_front_bytes)
        selfie_image = load_image(selfie_bytes)
        
        # Initialize filenames
        id_front_filename = None
        id_back_filename = None
        
        # Optionally load back ID card
        id_card_back_image = None
        if id_card_back:
            id_card_back_bytes = await id_card_back.read()
            id_card_back_image = load_image(id_card_back_bytes)
        
        # Extract ID and all OCR data from front card
        front_ocr_result = extract_id_from_image(id_card_front_image)
        extracted_id = front_ocr_result.get("extracted_id")
        id_type = front_ocr_result.get("id_type")
        
        # Extract OCR from back card if provided
        back_ocr_result = None
        if id_card_back_image is not None:
            back_ocr_result = extract_id_from_image(id_card_back_image)
        
        # Parse structured data from FRONT and BACK OCR results separately
        parsed_data = parse_yemen_id_card(front_ocr_result, back_ocr_result)
        
        # Save images with proper naming if ID was extracted
        if extracted_id:
            import time
            timestamp = int(time.time())
            
            # Save front image to processed directory
            id_front_filename = f"{extracted_id}_front_{timestamp}.jpg"
            save_image(id_card_front_image, id_front_filename, PROCESSED_DIR)
            
            # Save back image if provided
            if id_card_back_image is not None:
                id_back_filename = f"{extracted_id}_back_{timestamp}.jpg"
                save_image(id_card_back_image, id_back_filename, PROCESSED_DIR)
        
        # Face verification using front card
        face_result = verify_identity(id_card_front_image, selfie_image)
        
        if face_result.get("error"):
            return VerifyResponse(
                success=False,
                extracted_id=extracted_id,
                id_type=id_type,
                similarity_score=None,
                id_front=id_front_filename,
                id_back=id_back_filename,
                name_arabic=parsed_data.get("name_arabic"),
                name_english=parsed_data.get("name_english"),
                date_of_birth=parsed_data.get("date_of_birth"),
                gender=parsed_data.get("gender"),
                address=parsed_data.get("address"),
                nationality=parsed_data.get("nationality"),
                issuance_date=parsed_data.get("issuance_date"),
                expiry_date=parsed_data.get("expiry_date"),
                error=face_result["error"]
            )
        
        return VerifyResponse(
            success=True,
            extracted_id=extracted_id,
            id_type=id_type,
            similarity_score=face_result["similarity_score"],
            id_front=id_front_filename,
            id_back=id_back_filename,
            name_arabic=parsed_data.get("name_arabic"),
            name_english=parsed_data.get("name_english"),
            date_of_birth=parsed_data.get("date_of_birth"),
            gender=parsed_data.get("gender"),
            address=parsed_data.get("address"),
            nationality=parsed_data.get("nationality"),
            issuance_date=parsed_data.get("issuance_date"),
            expiry_date=parsed_data.get("expiry_date"),
            error=None
        )
        
    except Exception as e:
        return VerifyResponse(
            success=False,
            extracted_id=None,
            id_type=None,
            similarity_score=None,
            id_front=None,
            id_back=None,
            name_arabic=None,
            name_english=None,
            date_of_birth=None,
            gender=None,
            address=None,
            nationality=None,
            issuance_date=None,
            expiry_date=None,
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
                id_front=None,
                id_back=None,
                name_arabic=None,
                name_english=None,
                date_of_birth=None,
                gender=None,
                address=None,
                nationality=None,
                issuance_date=None,
                expiry_date=None,
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
                id_front=None,
                id_back=None,
                name_arabic=None,
                name_english=None,
                date_of_birth=None,
                gender=None,
                address=None,
                nationality=None,
                issuance_date=None,
                expiry_date=None,
                error=face_result["error"]
            )
        
        return VerifyResponse(
            success=True,
            extracted_id=extracted_id,
            id_type=id_type,
            similarity_score=face_result["similarity_score"],
            id_front=None,
            id_back=None,
            name_arabic=None,
            name_english=None,
            date_of_birth=None,
            gender=None,
            address=None,
            nationality=None,
            issuance_date=None,
            expiry_date=None,
            error=None
        )
        
    except Exception as e:
        return VerifyResponse(
            success=False,
            extracted_id=None,
            id_type=None,
            similarity_score=None,
            id_front=None,
            id_back=None,
            name_arabic=None,
            name_english=None,
            date_of_birth=None,
            gender=None,
            address=None,
            nationality=None,
            issuance_date=None,
            expiry_date=None,
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
        results = translate_arabic_to_english(request.texts)
        
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
        return TranslateResponse(
            success=False,
            translations=[],
            error=str(e)
        )
