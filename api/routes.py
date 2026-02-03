"""
FastAPI Routes for e-KYC System.

Provides endpoints for:
- /verify: Full e-KYC verification (OCR + Face Match)
- /extract-id: Extract ID number from ID card
- /compare-faces: Compare two face images
- /translate: Translate Arabic texts to English
- /process-batch: Batch process ID cards
- /health: Health check
- /save-id-card: Save extracted ID card data to database
- /save-passport: Save extracted passport data to database
- /id-cards: List all ID card records
- /passports: List all passport records
- /export/id-cards: Export ID cards to CSV/Excel
- /export/passports: Export passports to CSV/Excel
"""
import cv2
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse

from models.schemas import (
    VerifyRequest, VerifyResponse,
    ExtractIDRequest, ExtractIDResponse,
    CompareFacesRequest, CompareFacesResponse,
    BatchProcessRequest, BatchProcessResponse,
    HealthResponse, OCRResult, FaceMatchResult, LivenessResult,
    TranslateRequest, TranslateResponse, TranslatedText,
    ImageQualityResponse,
    # Database schemas
    SaveIDCardRequest, SavePassportRequest,
    IDCardRecord, PassportRecord,
    IDCardListResponse, PassportListResponse,
    SaveRecordResponse, ExportResponse
)
from services.ocr_service import extract_id_from_image, get_ocr_service
from services.face_recognition import verify_identity, compare_faces, is_ready as face_ready
from services.face_extractor import is_available as insightface_available
from services.database import get_id_card_db, get_passport_db
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
    liveness_enabled = False
    face_quality_enabled = False
    
    try:
        get_ocr_service()
        ocr_ready = True
    except Exception:
        pass
    
    try:
        face_recognition_ready = face_ready()
    except Exception:
        pass
    
    try:
        from services.liveness_service import is_liveness_enabled
        liveness_enabled = is_liveness_enabled()
    except Exception:
        pass
    
    try:
        from services.image_quality_service import is_quality_check_enabled
        face_quality_enabled = is_quality_check_enabled()
    except Exception:
        pass
    
    return HealthResponse(
        status="ok",
        ocr_ready=ocr_ready,
        face_recognition_ready=face_recognition_ready,
        liveness_enabled=liveness_enabled,
        face_quality_enabled=face_quality_enabled
    )


@router.post("/check-id-quality", response_model=ImageQualityResponse)
async def check_id_quality_endpoint(
    id_card: UploadFile = File(..., description="ID card/passport image")
):
    """
    Validate ID card/passport image quality before verification.
    
    Checks that the face on the ID is clearly visible and not obscured.
    Returns pass/fail with actionable error message for re-upload flow.
    """
    try:
        from services.image_quality_service import check_id_quality
        
        image_bytes = await id_card.read()
        image = load_image(image_bytes)
        
        result = check_id_quality(image)
        
        return ImageQualityResponse(
            passed=result["passed"],
            face_detected=result["face_detected"],
            quality_score=result["quality_score"],
            error=result.get("error"),
            details=result.get("details")
        )
        
    except Exception as e:
        return ImageQualityResponse(
            passed=False,
            face_detected=False,
            quality_score=0.0,
            error=f"Quality check failed: {str(e)}"
        )


@router.post("/check-selfie-quality", response_model=ImageQualityResponse)
async def check_selfie_quality_endpoint(
    selfie: UploadFile = File(..., description="Selfie image")
):
    """
    Validate selfie image quality before verification.
    
    Checks that the selfie shows a clearly visible face that is not obscured.
    Returns pass/fail with actionable error message for re-upload flow.
    """
    try:
        from services.image_quality_service import check_selfie_quality
        
        image_bytes = await selfie.read()
        image = load_image(image_bytes)
        
        result = check_selfie_quality(image)
        
        return ImageQualityResponse(
            passed=result["passed"],
            face_detected=result["face_detected"],
            quality_score=result["quality_score"],
            error=result.get("error"),
            details=result.get("details")
        )
        
    except Exception as e:
        return ImageQualityResponse(
            passed=False,
            face_detected=False,
            quality_score=0.0,
            error=f"Quality check failed: {str(e)}"
        )


@router.post("/check-liveness", response_model=LivenessResult)
async def check_liveness_endpoint(
    selfie: UploadFile = File(..., description="Selfie image to check for liveness")
):
    """
    Test liveness detection on a selfie image.
    
    Performs passive anti-spoofing detection to verify that the image
    is from a live, physically present person rather than a screen or printed photo.
    
    **Detection Techniques:**
    - Texture Analysis (LBP) - Detects printed photos with unnatural texture
    - Color Distribution - Checks for natural skin tone variations
    - Sharpness Analysis - Detects photos-of-photos (typically blurrier)
    - Moiré Pattern Detection - Detects screen captures via FFT
    - ML Model (if available) - Deep learning anti-spoof detection
    
    **Strict Mode:** ALL checks must pass for liveness to pass.
    """
    try:
        from services.liveness_service import detect_spoof, is_liveness_enabled
        
        if not is_liveness_enabled():
            return LivenessResult(
                is_live=True,
                confidence=1.0,
                spoof_probability=0.0,
                checks={},
                error="Liveness detection is disabled in configuration"
            )
        
        image_bytes = await selfie.read()
        image = load_image(image_bytes)
        
        result = detect_spoof(image)
        
        return LivenessResult(
            is_live=result.get("is_live", False),
            confidence=result.get("confidence", 0.0),
            spoof_probability=result.get("spoof_probability", 1.0),
            checks=result.get("checks", {}),
            error=result.get("error")
        )
        
    except Exception as e:
        return LivenessResult(
            is_live=False,
            confidence=0.0,
            spoof_probability=1.0,
            checks={},
            error=f"Liveness check failed: {str(e)}"
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
        
        # Extract ID from front card
        front_ocr_result = extract_id_from_image(id_card_front_image)
        extracted_id = front_ocr_result.get("extracted_id")
        id_type = front_ocr_result.get("id_type")
        
        # Note: Structured data parsing removed - data is now entered manually into database
        parsed_data = {}
        
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
        
        # Convert liveness dict to LivenessResult model if present
        liveness_response = None
        if face_result.get("liveness"):
            liveness_data = face_result["liveness"]
            liveness_response = LivenessResult(
                is_live=liveness_data.get("is_live", False),
                confidence=liveness_data.get("confidence", 0.0),
                spoof_probability=liveness_data.get("spoof_probability", 1.0),
                checks=liveness_data.get("checks", {}),
                error=liveness_data.get("error")
            )
        
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
                place_of_birth=parsed_data.get("place_of_birth"),
                issuance_date=parsed_data.get("issuance_date"),
                expiry_date=parsed_data.get("expiry_date"),
                liveness=liveness_response,
                error=face_result["error"]
            )
        
        # AUTO-SAVE: Save extracted data to database after successful verification
        if extracted_id:
            try:
                import cv2
                db = get_id_card_db()
                
                # Convert images to JPEG bytes for blob storage
                front_blob = None
                back_blob = None
                selfie_blob = None
                
                if id_card_front_image is not None:
                    _, front_encoded = cv2.imencode('.jpg', id_card_front_image)
                    front_blob = front_encoded.tobytes()
                
                if id_card_back_image is not None:
                    _, back_encoded = cv2.imencode('.jpg', id_card_back_image)
                    back_blob = back_encoded.tobytes()
                
                if selfie_image is not None:
                    _, selfie_encoded = cv2.imencode('.jpg', selfie_image)
                    selfie_blob = selfie_encoded.tobytes()
                
                db_data = {
                    "national_id": extracted_id,
                    "name_arabic": parsed_data.get("name_arabic"),
                    "name_english": parsed_data.get("name_english"),
                    "date_of_birth": parsed_data.get("date_of_birth"),
                    "place_of_birth": parsed_data.get("place_of_birth"),
                    "gender": parsed_data.get("gender"),
                    "issuance_date": parsed_data.get("issuance_date"),
                    "expiry_date": parsed_data.get("expiry_date"),
                    "front_image_blob": front_blob,
                    "back_image_blob": back_blob,
                    "selfie_image_blob": selfie_blob
                }
                
                # Check if record exists, update or insert
                existing = db.get_by_national_id(extracted_id)
                if existing:
                    db.update(extracted_id, db_data)
                else:
                    db.insert(db_data)
            except Exception as db_error:
                # Log error but don't fail the verification
                print(f"Warning: Failed to save to database: {db_error}")
        
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
            place_of_birth=parsed_data.get("place_of_birth"),
            issuance_date=parsed_data.get("issuance_date"),
            expiry_date=parsed_data.get("expiry_date"),
            liveness=liveness_response,
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
            place_of_birth=None,
            issuance_date=None,
            expiry_date=None,
            liveness=None,
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


# =====================================================
# DATABASE ENDPOINTS - ID Card and Passport Storage
# =====================================================

@router.post("/save-id-card", response_model=SaveRecordResponse)
async def save_id_card(request: SaveIDCardRequest):
    """
    Save extracted ID card data to the database.
    
    Names can be provided as:
    - Full names (name_arabic, name_english) which will be auto-split
    - Individual components (first_name_*, middle_name_*, last_name_*)
    """
    try:
        db = get_id_card_db()
        
        # Check if record already exists
        existing = db.get_by_national_id(request.national_id)
        if existing:
            # Update existing record
            data = request.model_dump(exclude_none=True)
            db.update(request.national_id, data)
            return SaveRecordResponse(
                success=True,
                record_id=existing["id"],
                message=f"Updated existing record for ID: {request.national_id}"
            )
        
        # Insert new record
        data = request.model_dump(exclude_none=True)
        record_id = db.insert(data)
        
        return SaveRecordResponse(
            success=True,
            record_id=record_id,
            message=f"Saved new ID card record: {request.national_id}"
        )
        
    except Exception as e:
        return SaveRecordResponse(
            success=False,
            error=str(e)
        )


@router.post("/save-passport", response_model=SaveRecordResponse)
async def save_passport(request: SavePassportRequest):
    """
    Save extracted passport data to the database.
    
    Names can be provided as:
    - Full names (name_arabic, name_english) which will be auto-split
    - Individual components (first_name_*, middle_name_*, last_name_*)
    """
    try:
        db = get_passport_db()
        
        # Check if record already exists
        existing = db.get_by_passport_number(request.passport_number)
        if existing:
            # Update existing record
            data = request.model_dump(exclude_none=True)
            db.update(request.passport_number, data)
            return SaveRecordResponse(
                success=True,
                record_id=existing["id"],
                message=f"Updated existing record for passport: {request.passport_number}"
            )
        
        # Insert new record
        data = request.model_dump(exclude_none=True)
        record_id = db.insert(data)
        
        return SaveRecordResponse(
            success=True,
            record_id=record_id,
            message=f"Saved new passport record: {request.passport_number}"
        )
        
    except Exception as e:
        return SaveRecordResponse(
            success=False,
            error=str(e)
        )


@router.get("/id-cards", response_model=IDCardListResponse)
async def list_id_cards():
    """
    List all ID card records from the database.
    """
    try:
        db = get_id_card_db()
        records = db.get_all()
        
        return IDCardListResponse(
            success=True,
            count=len(records),
            records=[IDCardRecord(**r) for r in records]
        )
        
    except Exception as e:
        return IDCardListResponse(
            success=False,
            error=str(e)
        )


@router.get("/passports", response_model=PassportListResponse)
async def list_passports():
    """
    List all passport records from the database.
    """
    try:
        db = get_passport_db()
        records = db.get_all()
        
        return PassportListResponse(
            success=True,
            count=len(records),
            records=[PassportRecord(**r) for r in records]
        )
        
    except Exception as e:
        return PassportListResponse(
            success=False,
            error=str(e)
        )


@router.get("/export/id-cards")
async def export_id_cards(
    format: str = Query("csv", description="Export format: csv or excel")
):
    """
    Export all ID card records to CSV or Excel file.
    
    Returns the file for download.
    """
    try:
        db = get_id_card_db()
        
        if format.lower() == "excel":
            export_path = db.export_excel()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            export_path = db.export_csv()
            media_type = "text/csv"
        
        return FileResponse(
            path=str(export_path),
            filename=export_path.name,
            media_type=media_type
        )
        
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Excel export requires openpyxl. Install with: pip install openpyxl"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/passports")
async def export_passports(
    format: str = Query("csv", description="Export format: csv or excel")
):
    """
    Export all passport records to CSV or Excel file.
    
    Returns the file for download.
    """
    try:
        db = get_passport_db()
        
        if format.lower() == "excel":
            export_path = db.export_excel()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            export_path = db.export_csv()
            media_type = "text/csv"
        
        return FileResponse(
            path=str(export_path),
            filename=export_path.name,
            media_type=media_type
        )
        
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Excel export requires openpyxl. Install with: pip install openpyxl"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/id-cards/{national_id}")
async def get_id_card(national_id: str):
    """
    Get a specific ID card record by national ID number.
    """
    try:
        db = get_id_card_db()
        record = db.get_by_national_id(national_id)
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"ID card with national ID '{national_id}' not found"
            )
        
        return IDCardRecord(**record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/passports/{passport_number}")
async def get_passport(passport_number: str):
    """
    Get a specific passport record by passport number.
    """
    try:
        db = get_passport_db()
        record = db.get_by_passport_number(passport_number)
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Passport with number '{passport_number}' not found"
            )
        
        return PassportRecord(**record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/id-cards/{record_id}")
async def delete_id_card(record_id: int):
    """
    Delete an ID card record by its database ID.
    """
    try:
        db = get_id_card_db()
        deleted = db.delete(record_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"ID card record with ID {record_id} not found"
            )
        
        return {"success": True, "message": f"Deleted record {record_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/passports/{record_id}")
async def delete_passport(record_id: int):
    """
    Delete a passport record by its database ID.
    """
    try:
        db = get_passport_db()
        deleted = db.delete(record_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Passport record with ID {record_id} not found"
            )
        
        return {"success": True, "message": f"Deleted record {record_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
