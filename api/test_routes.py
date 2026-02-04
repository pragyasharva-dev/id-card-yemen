"""
Test Routes for e-KYC System.

These endpoints are for internal testing and make decisions
(approved/rejected/manual_review). Production SDK should use
the score-returning endpoints in routes.py instead.

Endpoints:
- /verify: Full e-KYC verification (OCR + Face Match)
- /verify-json: JSON-based verification
- /process-batch: Batch process ID cards
- /compare-form-ocr: Compare manual form data with OCR
- /submit-id-form: Submit and validate ID card form data
- /validate-id: Unified ID validation API
- /test-selfie-verification: Simple upload test
"""
import cv2
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool

from models.schemas import (
    VerifyRequest, VerifyResponse,
    BatchProcessRequest, BatchProcessResponse,
    IDFormSubmitRequest, IDFormSubmitResponse,
    FormOCRComparisonRequest, FormOCRComparisonResponse,
    SelfieVerificationResponse
)
from services.ocr_service import extract_id_from_image
from services.face_recognition import verify_identity
from utils.image_manager import load_image, rename_by_id, save_image
from utils.config import PROCESSED_DIR


test_router = APIRouter(prefix="/test", tags=["Testing"])


@test_router.post("/verify", response_model=VerifyResponse)
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
        front_ocr_result = await run_in_threadpool(extract_id_from_image, id_card_front_image)
        extracted_id = front_ocr_result.get("extracted_id")
        id_type = front_ocr_result.get("id_type")
        
        # Extract OCR from back card if provided
        back_ocr_result = None
        if id_card_back_image is not None:
            back_ocr_result = await run_in_threadpool(extract_id_from_image, id_card_back_image)
        
        # Parse structured data from FRONT and BACK OCR results separately
        parsed_data = await run_in_threadpool(parse_yemen_id_card, front_ocr_result, back_ocr_result)
        
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
        face_result = await run_in_threadpool(verify_identity, id_card_front_image, selfie_image)
        
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


@test_router.post("/verify-json", response_model=VerifyResponse)
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
        search_result = await run_in_threadpool(search_id_card_by_number, request.id_number)
        
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
        face_result = await run_in_threadpool(verify_identity, id_card_image, selfie_image)
        
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


@test_router.post("/process-batch", response_model=BatchProcessResponse)
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
                
                ocr_result = await run_in_threadpool(extract_id_from_image, image)
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


@test_router.post("/compare-form-ocr", response_model=FormOCRComparisonResponse)
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
        result = await run_in_threadpool(
            validate_form_vs_ocr,
            request.manual_data,
            request.ocr_data,
            request.ocr_confidence
        )
        
        # Convert to response model
        return FormOCRComparisonResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Form-OCR comparison failed: {str(e)}"
        )


@test_router.post("/submit-id-form", response_model=IDFormSubmitResponse)
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


@test_router.post("/validate-id")
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
    UNIFIED ID VALIDATION API (Front + Back)
    
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
        front_ocr = await run_in_threadpool(extract_id_from_image, front_image)
        
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
            back_ocr = await run_in_threadpool(extract_id_from_image, back_image)
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
        parsed_data = await run_in_threadpool(parse_yemen_id_card, front_ocr, back_ocr)
        
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
        
        comparison_result = await run_in_threadpool(
            validate_form_vs_ocr,
            manual_data,
            response["ocr_extracted_data"],
            front_ocr.get("confidence", 0.9)
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


@test_router.post("/selfie-check")
async def test_selfie_verification_endpoint(
    selfie: UploadFile = File(..., description="Selfie image")
):
    """
    TEST ENDPOINT: Simple image upload check.
    
    Just returns the filename to confirm the API is receiving files.
    """
    return {
        "success": True,
        "message": "Image received successfully",
        "filename": selfie.filename
    }


@test_router.post("/verify-id-card")
async def verify_id_card_endpoint(
    idCardFront: UploadFile = File(..., description="ID card front side image"),
    idCardBack: UploadFile = File(..., description="ID card back side image"),
    payloadJson: str = Form(..., description="JSON payload with id_details")
):
    """
    Verify ID card with front/back images and form data.
    
    Accepts:
    - idCardFront: Front side image of ID card
    - idCardBack: Back side image of ID card
    - payloadJson: JSON string with structure:
        {
            "id_details": {
                "full_name": "...",
                "id_type": "...",
                "id_number": "...",
                "issue_date": "...",
                "dob": "...",
                "referral_code": "..."
            }
        }
    
    Returns:
    - OCR extracted data from both sides
    - Comparison scores between form data and OCR
    """
    import json
    from datetime import datetime
    from services.id_card_parser import parse_yemen_id_card
    from services.field_comparison_service import validate_form_vs_ocr
    
    response = {
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "request": {
            "has_front_image": True,
            "has_back_image": True,
            "payload": None
        },
        "ocr_extracted_data": None,
        "comparison_results": None,
        "errors": []
    }
    
    try:
        # ============================================
        # STEP 1: Parse JSON payload
        # ============================================
        try:
            payload = json.loads(payloadJson)
            id_details = payload.get("id_details", {})
            response["request"]["payload"] = payload
        except json.JSONDecodeError as e:
            response["errors"].append(f"Invalid JSON payload: {str(e)}")
            return response
        
        # Extract fields from payload
        full_name = id_details.get("full_name")
        id_type = id_details.get("id_type")
        id_number = id_details.get("id_number")
        issue_date = id_details.get("issue_date")
        dob = id_details.get("dob")
        referral_code = id_details.get("referral_code")
        
        # ============================================
        # STEP 2: Load images
        # ============================================
        front_bytes = await idCardFront.read()
        front_image = load_image(front_bytes)
        
        if front_image is None:
            response["errors"].append("Failed to load front image")
            return response
        
        back_bytes = await idCardBack.read()
        back_image = load_image(back_bytes)
        
        if back_image is None:
            response["errors"].append("Failed to load back image")
            return response
        
        # ============================================
        # STEP 3 & 4: OCR Extraction (Branch by ID type)
        # ============================================
        
        # Normalize id_type for comparison
        id_type_normalized = (id_type or "").lower().replace("-", "_").replace(" ", "_")
        is_passport = "passport" in id_type_normalized
        
        if is_passport:
            # ========== PASSPORT PIPELINE ==========
            from services.passport_ocr_service import extract_passport_data
            
            # Passport uses single image (front = data page)
            passport_result = await run_in_threadpool(extract_passport_data, front_image)
            
            if not passport_result.get("success"):
                response["errors"].append(passport_result.get("error", "Passport extraction failed"))
                return response
            
            detected_id_type = "yemen_passport"
            extracted_id = passport_result.get("passport_number")
            
            # Map passport fields to standard response format
            response["ocr_extracted_data"] = {
                "id_number": passport_result.get("passport_number"),
                "name_arabic": None,  # Construct from parts if available
                "name_english": passport_result.get("name_english"),
                "date_of_birth": passport_result.get("date_of_birth"),
                "gender": passport_result.get("gender"),
                "place_of_birth": passport_result.get("place_of_birth"),
                "issuance_date": passport_result.get("issuance_date"),
                "expiry_date": passport_result.get("expiry_date"),
                "detected_id_type": detected_id_type,
                # Passport-specific fields
                "given_names": passport_result.get("given_names"),
                "surname": passport_result.get("surname"),
                "nationality": passport_result.get("nationality"),
                "mrz_valid": passport_result.get("mrz_valid"),
                "mrz_confidence": passport_result.get("mrz_confidence"),
            }
            
            # Build Arabic name if parts available
            given_ar = passport_result.get("given_name_arabic") or ""
            surname_ar = passport_result.get("surname_arabic") or ""
            if given_ar or surname_ar:
                response["ocr_extracted_data"]["name_arabic"] = f"{given_ar} {surname_ar}".strip()
        
        else:
            # ========== NATIONAL ID PIPELINE ==========
            front_ocr = await run_in_threadpool(extract_id_from_image, front_image)
            back_ocr = await run_in_threadpool(extract_id_from_image, back_image)
            
            if not front_ocr:
                response["errors"].append("OCR extraction failed on front image")
                return response
            
            detected_id_type = front_ocr.get("id_type", "unknown")
            extracted_id = front_ocr.get("extracted_id")
            
            # Parse structured data from both sides
            parsed_data = await run_in_threadpool(parse_yemen_id_card, front_ocr, back_ocr)
            
            response["ocr_extracted_data"] = {
                "id_number": parsed_data.get("id_number"),
                "name_arabic": parsed_data.get("name_arabic"),
                "name_english": parsed_data.get("name_english"),
                "date_of_birth": parsed_data.get("date_of_birth"),
                "gender": parsed_data.get("gender"),
                "place_of_birth": parsed_data.get("place_of_birth"),
                "issuance_date": parsed_data.get("issuance_date"),
                "expiry_date": parsed_data.get("expiry_date"),
                "detected_id_type": detected_id_type
            }
        
        # ============================================
        # STEP 5: Compare form data with OCR data
        # ============================================
        manual_data = {
            "id_number": id_number,
            "name_english": full_name,  # Map full_name to name_english
            "date_of_birth": dob,
            "issuance_date": issue_date
        }
        
        # Get confidence score based on pipeline used
        if is_passport:
            # Use MRZ confidence from passport result
            confidence_score = passport_result.get("mrz_confidence", 0.9)
        else:
            # Use OCR confidence from national ID result
            confidence_score = front_ocr.get("confidence", 0.9) if front_ocr else 0.9
        
        comparison_result = await run_in_threadpool(
            validate_form_vs_ocr,
            manual_data,
            response["ocr_extracted_data"],
            confidence_score
        )
        
        response["comparison_results"] = {
            "overall_score": comparison_result.get("overall_score"),
            "field_comparisons": comparison_result.get("field_comparisons"),
            "summary": comparison_result.get("summary")
        }
        
        response["success"] = True
        
        # Add summary
        response["summary"] = {
            "extracted_id": extracted_id,
            "detected_id_type": detected_id_type,
            "expected_id_type": id_type,
            "referral_code": referral_code,
            "fields_compared": len(comparison_result.get("field_comparisons", [])),
            "overall_score": comparison_result.get("overall_score")
        }
        
        return response
        
    except Exception as e:
        response["errors"].append(f"Unexpected error: {str(e)}")
        response["success"] = False
        import traceback
        response["traceback"] = traceback.format_exc()
        return response
