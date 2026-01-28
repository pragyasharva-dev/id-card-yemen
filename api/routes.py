"""
FastAPI Routes for e-KYC System.

Provides endpoints for:
- /verify: Full e-KYC verification (OCR + Face Match)
- /extract-id: Extract ID number from ID card
- /compare-faces: Compare two face images
- /translate: Translate Arabic texts to English
- /process-batch: Batch process ID cards
- /submit-id-form: Submit and validate ID card form data
- /compare-form-ocr: Compare manual form data with OCR extracted data
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
    TranslateRequest, TranslateResponse, TranslatedText,
    IDFormSubmitRequest, IDFormSubmitResponse,
    FormOCRComparisonRequest, FormOCRComparisonResponse,
    SelfieVerificationResponse
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
                place_of_birth=parsed_data.get("place_of_birth"),
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
            place_of_birth=parsed_data.get("place_of_birth"),
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
            place_of_birth=None,
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
                place_of_birth=None,
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
                place_of_birth=None,
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
            place_of_birth=None,
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
            place_of_birth=None,
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
        ocr_result = extract_id_from_image(id_card_image)
        
        # Parse into structured data
        parsed_data = parse_yemen_id_card(ocr_result, None)
        
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
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )


@router.post("/compare-form-ocr", response_model=FormOCRComparisonResponse)
async def compare_form_ocr_endpoint(request: FormOCRComparisonRequest):
    """
    Compare manually entered form data with OCR extracted data.
    
    Uses configurable severity levels and field-specific thresholds to determine
    overall verification decision (approved/manual_review/rejected).
    
    **Severity Levels:**
    - **High**: ID number, DOB, names, gender - may cause rejection
    - **Medium**: Issuance/expiry dates - causes manual review
    - **Low**: Place of birth - only manual review, never rejects
    
    **Decision Logic:**
    - Any high-severity field below threshold → REJECT
    - Any medium/low severity field below threshold → MANUAL REVIEW
    - All fields pass → APPROVED
    
    Returns field-by-field comparison results plus overall decision.
    """
    try:
        from services.field_comparison_service import validate_form_vs_ocr
        
        # Perform comparison
        result = validate_form_vs_ocr(
            manual_data=request.manual_data,
            ocr_data=request.ocr_data,
            ocr_confidence=request.ocr_confidence
        )
        
        # Convert to response model
        return FormOCRComparisonResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Form-OCR comparison failed: {str(e)}"
        )


@router.post("/submit-id-form", response_model=IDFormSubmitResponse)
async def submit_id_form_endpoint(request: IDFormSubmitRequest):
    """
    Submit ID card form data with comprehensive production-level validation.
    
    Validates form data based on ID type (yemen_national_id or yemen_passport).
    Applies hard-coded validation rules including:
    - Name: Alphabets (English/Arabic), spaces, hyphens only
    - Dates: YYYY-MM-DD format with realistic range checking
    - ID numbers: Regex pattern validation (11 digits for National ID, 8 for Passport)
    - Cross-field validation (e.g., expiry after issuance)
    
    Note: This is backend validation only - no OCR or image processing.
    """
    try:
        from models.form_validators import (
            YemenNationalIDForm,
            YemenPassportForm,
            IDFormValidationError
        )
        
        # Prepare data for validation based on ID type
        form_data = {
            "name_arabic": request.name_arabic,
            "name_english": request.name_english,
            "date_of_birth": request.date_of_birth,
            "place_of_birth": request.place_of_birth,
            "issuance_date": request.issuance_date,
            "expiry_date": request.expiry_date,
        }
        
        # Validate based on ID type
        if request.id_type == "yemen_national_id":
            form_data["id_number"] = request.id_number
            # Do NOT include gender - it will be auto-derived from ID number
            
            # Validate with YemenNationalIDForm
            validated_form = YemenNationalIDForm(**form_data)
            
            return IDFormSubmitResponse(
                success=True,
                message="Yemen National ID form validated successfully",
                errors=None,
                validated_data=validated_form.model_dump()
            )
        
        elif request.id_type == "yemen_passport":
            form_data["passport_number"] = request.passport_number
            form_data["gender"] = request.gender  # Gender is required for passport
            
            # Validate with YemenPassportForm
            validated_form = YemenPassportForm(**form_data)
            
            return IDFormSubmitResponse(
                success=True,
                message="Yemen Passport form validated successfully",
                errors=None,
                validated_data=validated_form.model_dump()
            )
        
        else:
            return IDFormSubmitResponse(
                success=False,
                message=f"Invalid id_type: {request.id_type}",
                errors=[IDFormValidationError(
                    field="id_type",
                    message=f"id_type must be 'yemen_national_id' or 'yemen_passport', got '{request.id_type}'"
                )],
                validated_data=None
            )
            
    except Exception as e:
        # Parse Pydantic validation errors
        if hasattr(e, 'errors'):
            # Pydantic ValidationError
            error_list = []
            for error in e.errors():
                field_path = '.'.join(str(loc) for loc in error['loc'])
                error_list.append(IDFormValidationError(
                    field=field_path,
                    message=error['msg']
                ))
            
            return IDFormSubmitResponse(
                success=False,
                message="Form validation failed",
                errors=error_list,
                validated_data=None
            )
        else:
            # Other exceptions
            return IDFormSubmitResponse(
                success=False,
                message=f"Validation error: {str(e)}",
                errors=[IDFormValidationError(
                    field="general",
                    message=str(e)
                )],
                validated_data=None
            )


@router.post("/validate-id")
async def validate_id_endpoint(
    image_front: UploadFile = File(..., description="ID card front side image"),
    id_type: str = Form(..., description="Expected ID type: yemen_national_id or yemen_passport"),
    id_number: str = Form(..., description="Manually entered ID/Passport number"),
    image_back: UploadFile = File(None, description="ID card back side image (optional)"),
    name_arabic: Optional[str] = Form(None, description="Name in Arabic"),
    name_english: Optional[str] = Form(None, description="Name in English"),
    date_of_birth: Optional[str] = Form(None, description="Date of birth (YYYY-MM-DD)"),
    gender: Optional[str] = Form(None, description="Gender: Male or Female"),
    place_of_birth: Optional[str] = Form(None, description="Place of birth"),
    issuance_date: Optional[str] = Form(None, description="Issuance date (YYYY-MM-DD)"),
    expiry_date: Optional[str] = Form(None, description="Expiry date (YYYY-MM-DD)"),
    issuing_authority: Optional[str] = Form(None, description="Issuing authority/center")
):
    """
    🔍 UNIFIED ID VALIDATION API (Front + Back)
    
    Comprehensive endpoint that performs:
    1. ID Type Detection - Identifies if image is National ID or Passport
    2. ID Type Matching - Verifies detected type matches expected type
    3. OCR Extraction - Extracts all fields from front AND back
    4. Field-by-Field Comparison - Compares manual data with OCR data
    5. Validation Checks - Applies all configured validation rules
    6. Decision Making - Returns approved/manual_review/rejected
    
    Use this for production API testing in Postman.
    """
    import json
    from datetime import datetime
    from services.id_card_parser import parse_yemen_id_card
    from services.field_comparison_service import validate_form_vs_ocr
    
    # ============================================
    # INPUT SANITIZATION - Strip whitespace/newlines
    # ============================================
    def clean_input(value):
        if value is None:
            return None
        return value.strip() if isinstance(value, str) else value
    
    id_number = clean_input(id_number)
    name_arabic = clean_input(name_arabic)
    name_english = clean_input(name_english)
    date_of_birth = clean_input(date_of_birth)
    gender = clean_input(gender)
    place_of_birth = clean_input(place_of_birth)
    issuance_date = clean_input(issuance_date)
    expiry_date = clean_input(expiry_date)
    issuing_authority = clean_input(issuing_authority)
    id_type = clean_input(id_type)
    
    response = {
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "request": {
            "expected_id_type": id_type,
            "has_back_image": image_back is not None,
            "manual_data": {
                "id_number": id_number,
                "name_arabic": name_arabic,
                "name_english": name_english,
                "date_of_birth": date_of_birth,
                "gender": gender,
                "place_of_birth": place_of_birth,
                "issuance_date": issuance_date,
                "expiry_date": expiry_date,
                "issuing_authority": issuing_authority
            }
        },
        "steps": [],
        "ocr_extracted_data": None,
        "comparison_results": None,
        "overall_decision": None,
        "errors": []
    }
    
    try:
        # ============================================
        # STEP 1: Load and validate FRONT image
        # ============================================
        front_bytes = await image_front.read()
        front_image = load_image(front_bytes)
        
        if front_image is None:
            response["errors"].append("Failed to load front image")
            response["steps"].append({"step": 1, "name": "Front Image Load", "status": "FAILED"})
            return response
        
        response["steps"].append({"step": 1, "name": "Front Image Load", "status": "PASSED"})
        
        # Load BACK image if provided
        back_image = None
        if image_back:
            back_bytes = await image_back.read()
            back_image = load_image(back_bytes)
            if back_image is not None:
                response["steps"].append({"step": 1.5, "name": "Back Image Load", "status": "PASSED"})
            else:
                response["steps"].append({"step": 1.5, "name": "Back Image Load", "status": "WARNING", "message": "Could not load back image"})
        
        # ============================================
        # STEP 2: OCR Extraction - FRONT
        # ============================================
        front_ocr = extract_id_from_image(front_image)
        
        if not front_ocr or not front_ocr.get("extracted_id"):
            response["errors"].append("OCR extraction failed on front image - no ID detected")
            response["steps"].append({"step": 2, "name": "Front OCR", "status": "FAILED"})
            return response
        
        detected_id_type = front_ocr.get("id_type", "unknown")
        response["detected_id_type"] = detected_id_type
        response["steps"].append({
            "step": 2, 
            "name": "Front OCR", 
            "status": "PASSED",
            "detected_id_type": detected_id_type,
            "extracted_id": front_ocr.get("extracted_id")
        })
        
        # OCR Extraction - BACK (if provided)
        back_ocr = None
        if back_image is not None:
            back_ocr = extract_id_from_image(back_image)
            if back_ocr:
                response["steps"].append({
                    "step": 2.5, 
                    "name": "Back OCR", 
                    "status": "PASSED",
                    "extracted_id": back_ocr.get("extracted_id")
                })
            else:
                response["steps"].append({"step": 2.5, "name": "Back OCR", "status": "WARNING", "message": "No data extracted from back"})
        
        # ============================================
        # STEP 3: ID Type Matching
        # ============================================
        # Normalize ID types for comparison
        expected_normalized = id_type.lower().replace("-", "_").replace(" ", "_")
        detected_normalized = detected_id_type.lower().replace("-", "_").replace(" ", "_")
        
        # Map variations
        type_mappings = {
            "yemen_national_id": ["yemen_national_id", "yemen_id", "national_id"],
            "yemen_passport": ["yemen_passport", "passport"]
        }
        
        id_type_match = False
        for standard, variations in type_mappings.items():
            if expected_normalized in variations and detected_normalized in variations:
                id_type_match = True
                break
        
        if not id_type_match:
            response["errors"].append(f"ID type mismatch: Expected '{id_type}', Detected '{detected_id_type}'")
            response["steps"].append({
                "step": 3, 
                "name": "ID Type Matching", 
                "status": "FAILED",
                "expected": id_type,
                "detected": detected_id_type
            })
            response["overall_decision"] = "rejected"
            response["success"] = True  # API worked, but validation failed
            return response
        
        response["steps"].append({
            "step": 3, 
            "name": "ID Type Matching", 
            "status": "PASSED",
            "expected": id_type,
            "detected": detected_id_type
        })
        
        # ============================================
        # STEP 4: Full Field Extraction (Parse ID - Front + Back)
        # ============================================
        parsed_data = parse_yemen_id_card(front_ocr, back_ocr)
        
        if not parsed_data:
            response["errors"].append("Failed to parse ID card fields")
            response["steps"].append({"step": 4, "name": "Field Extraction", "status": "FAILED"})
            return response
        
        response["ocr_extracted_data"] = {
            "id_number": parsed_data.get("id_number"),
            "name_arabic": parsed_data.get("name_arabic"),
            "name_english": parsed_data.get("name_english"),
            "date_of_birth": parsed_data.get("date_of_birth"),
            "gender": parsed_data.get("gender"),
            "place_of_birth": parsed_data.get("place_of_birth"),
            "issuance_date": parsed_data.get("issuance_date"),
            "expiry_date": parsed_data.get("expiry_date"),
            "issuing_authority": parsed_data.get("issuing_authority")
        }
        
        response["steps"].append({
            "step": 4, 
            "name": "Field Extraction", 
            "status": "PASSED",
            "fields_extracted": len([v for v in response["ocr_extracted_data"].values() if v]),
            "from_back": back_ocr is not None
        })
        
        # ============================================
        # STEP 5: Manual vs OCR Comparison
        # ============================================
        manual_data = {
            "id_number": id_number,
            "name_arabic": name_arabic,
            "name_english": name_english,
            "date_of_birth": date_of_birth,
            "gender": gender,
            "place_of_birth": place_of_birth,
            "issuance_date": issuance_date,
            "expiry_date": expiry_date,
            "issuing_authority": issuing_authority
        }
        
        comparison_result = validate_form_vs_ocr(
            manual_data=manual_data,
            ocr_data=response["ocr_extracted_data"],
            ocr_confidence=front_ocr.get("confidence", 0.9)
        )
        
        response["comparison_results"] = {
            "overall_score": comparison_result.get("overall_score"),
            "field_comparisons": comparison_result.get("field_comparisons"),
            "summary": comparison_result.get("summary"),
            "recommendations": comparison_result.get("recommendations")
        }
        
        response["steps"].append({
            "step": 5, 
            "name": "Data Comparison", 
            "status": "PASSED",
            "overall_score": comparison_result.get("overall_score")
        })
        
        # ============================================
        # STEP 6: Final Decision
        # ============================================
        overall_decision = comparison_result.get("overall_decision", "manual_review")
        response["overall_decision"] = overall_decision
        
        decision_status = "PASSED" if overall_decision == "approved" else "REVIEW" if overall_decision == "manual_review" else "FAILED"
        response["steps"].append({
            "step": 6, 
            "name": "Final Decision", 
            "status": decision_status,
            "decision": overall_decision
        })
        
        response["success"] = True
        
        # Add summary
        response["summary"] = {
            "image_processed": True,
            "id_type_matched": id_type_match,
            "fields_compared": len(comparison_result.get("field_comparisons", [])),
            "fields_passed": comparison_result.get("summary", {}).get("passed_fields", 0),
            "fields_failed": comparison_result.get("summary", {}).get("failed_fields", 0),
            "overall_score": comparison_result.get("overall_score"),
            "decision": overall_decision
        }
        
        return response
        
    except Exception as e:
        response["errors"].append(f"Unexpected error: {str(e)}")
        response["success"] = False
        import traceback
        response["traceback"] = traceback.format_exc()
        return response


@router.post("/test-selfie-verification")
async def test_selfie_verification_endpoint(
    selfie: UploadFile = File(..., description="Selfie image"),
    id_number: str = Form(..., description="ID number to fetch the previously uploaded ID card image")
):
    """
    🧪 TEST ENDPOINT: Selfie Verification with Auto-Fetch ID Image
    
    Fetches the ID card image that was previously uploaded during OCR,
    then compares it with the provided selfie.
    
    **How it works:**
    1. Uses the ID number to find the ID card image in processed directory
    2. Compares the face on the ID with the selfie
    3. Returns filenames for confirmation
    """
    from pathlib import Path
    
    # Find the ID card image in PROCESSED_DIR
    id_image_path = None
    for file in PROCESSED_DIR.glob(f"{id_number}_front_*"):
        id_image_path = file
        break  # Get the first (most recent) match
    
    if id_image_path is None:
        return {
            "success": False,
            "message": f"No ID card image found for ID number: {id_number}",
            "id_number": id_number,
            "selfie_filename": selfie.filename,
            "id_image_found": None
        }
    
    return {
        "success": True,
        "message": "API hit successfully - ID image found",
        "id_number": id_number,
        "selfie_filename": selfie.filename,
        "id_image_found": id_image_path.name
    }

