"""e-KYC verification endpoints."""
import cv2
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import VerifyRequest, VerifyResponse, LivenessResult
from services.ocr_service import extract_id_from_image, get_ocr_service
from services.id_card_parser import parse_yemen_id_card
from services.face_recognition import verify_identity
# from services.database import get_id_card_db  # Deprecated
from services.db import get_db
from services.data_service import save_document, save_verification
from services.image_quality_service import check_id_quality, check_selfie_quality
from utils.image_manager import load_image, save_image
from utils.exceptions import AppError
from utils.config import PROCESSED_DIR

router = APIRouter(tags=["Verification"])


@router.post("/verify", response_model=VerifyResponse)
async def verify_identity_endpoint(
    id_card_front: UploadFile = File(..., description="ID card front side image"),
    selfie: UploadFile = File(..., description="Selfie image file"),
    id_card_back: UploadFile = File(None, description="ID card back side image (optional)"),
    db: AsyncSession = Depends(get_db)
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
    # Initialize variables early so they're available in except blocks
    extracted_id = None
    id_type = None
    id_front_filename = None
    id_back_filename = None
    parsed_data = {}
    liveness_response = None
    doc_record = None
    
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
        
        # Extract from back card if provided
        back_ocr_result = None
        if id_card_back_image is not None:
            ocr_service = get_ocr_service()
            back_ocr_result = ocr_service.process_id_card(id_card_back_image, side="back")
        
        # Parse structured fields from front + back using full parser
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
            # Save processing error to DB before returning
            if extracted_id:
                try:
                    error_msg = face_result["error"]
                    failure_data = {
                        "status": "error",
                        "code": "PROCESSING_ERROR",
                        "message": error_msg,
                        "details": {}
                    }
                    
                    front_blob = None
                    if id_card_front_image is not None:
                        _, front_encoded = cv2.imencode('.jpg', id_card_front_image)
                        front_blob = front_encoded.tobytes()
                    
                    back_blob = None
                    if id_card_back_image is not None:
                        _, back_encoded = cv2.imencode('.jpg', id_card_back_image)
                        back_blob = back_encoded.tobytes()
                    
                    ocr_store_data = {
                        "extracted_id": extracted_id,
                        "id_type": id_type,
                        "name_arabic": parsed_data.get("name_arabic"),
                        "name_english": parsed_data.get("name_english"),
                        "date_of_birth": parsed_data.get("date_of_birth"),
                        "place_of_birth": parsed_data.get("place_of_birth"),
                        "gender": parsed_data.get("gender"),
                        "issuance_date": parsed_data.get("issuance_date"),
                        "expiry_date": parsed_data.get("expiry_date"),
                        "confidence": front_ocr_result.get("confidence"),
                        "extraction_method": front_ocr_result.get("extraction_method"),
                    }
                    
                    doc_record = await save_document(
                        session=db,
                        document_number=extracted_id,
                        document_type=id_type or "unknown",
                        ocr_data=ocr_store_data,
                        front_image_data=front_blob,
                        back_image_data=back_blob
                    )
                    
                    if doc_record:
                        await save_verification(
                            session=db,
                            document_id=doc_record.id,
                            status="failed",
                            similarity_score=None,
                            selfie_image_data=None,
                            liveness_data=face_result.get("liveness") or {},
                            image_quality_metrics={},
                            authenticity_checks={},
                            failure_reason=failure_data
                        )
                except Exception:
                    import traceback
                    traceback.print_exc()
            
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
                
                # Prepare OCR data for JSONB storage
                layout = front_ocr_result.get("layout_fields", {})
                
                ocr_store_data = {
                    "extracted_id": extracted_id,
                    "id_type": id_type,
                    "name_arabic": parsed_data.get("name_arabic"),
                    "name_english": parsed_data.get("name_english"),
                    "date_of_birth": parsed_data.get("date_of_birth"),
                    "place_of_birth": parsed_data.get("place_of_birth"),
                    "gender": parsed_data.get("gender"),
                    "issuance_date": parsed_data.get("issuance_date"),
                    "expiry_date": parsed_data.get("expiry_date"),
                    "confidence": front_ocr_result.get("confidence"),
                    "extraction_method": front_ocr_result.get("extraction_method"),
                    "layout_fields": layout,  # Store full layout for debugging
                }

                # Save Document (Upsert)
                doc_record = await save_document(
                    session=db,
                    document_number=extracted_id,
                    document_type=id_type or "unknown",
                    ocr_data=ocr_store_data,
                    front_image_data=front_blob,
                    back_image_data=back_blob
                )

                # Save Verification Result
                if doc_record:
                    similarity = face_result.get("similarity_score")
                    is_live = liveness_response.is_live if liveness_response else False
                    
                    # Determine status: verified only if face matches AND is live
                    if similarity and similarity > 0.6 and is_live:
                        status_val = "verified"
                    else:
                        status_val = "failed"

                    # --- Calculate detailed quality and authenticity metrics ---

                    # 1. Image Quality Metrics (from Quality Service)
                    id_quality = check_id_quality(id_card_front_image)
                    selfie_quality = check_selfie_quality(selfie_image)
                    
                    quality_metrics = {
                        "id_card": {
                            "score": id_quality.get("quality_score"),
                            "face_visible": id_quality.get("face_visible"),
                            "details": id_quality.get("details", {})
                        },
                        "selfie": {
                            "score": selfie_quality.get("quality_score"),
                            "face_visible": selfie_quality.get("face_visible"),
                            "details": selfie_quality.get("details", {})
                        }
                    }

                    # 2. Authenticity Checks (Derived from OCR + Quality + ID validation)
                    ocr_confidence = float(front_ocr_result.get("confidence", 0.0))
                    extraction_method = front_ocr_result.get("extraction_method", "unknown")
                    detected_langs = front_ocr_result.get("detected_languages", [])
                    
                    # Document validation signals from quality check
                    doc_validation = {
                        "is_clear": id_quality.get("quality_score", 0) > 0.5,
                        "face_detected_on_id": id_quality.get("face_visible", False),
                        "sharpness_ok": id_quality.get("details", {}).get("sharpness", 0) > 50,
                        "not_blurry": id_quality.get("details", {}).get("blur_score", 1) < 0.5,
                    }
                    
                    # ID number validation
                    id_validation = {
                        "format_valid": extracted_id is not None and len(extracted_id) >= 8,
                        "length_correct": extracted_id is not None and len(extracted_id) == 11,  # Yemen ID is 11 digits
                        "is_numeric": extracted_id.isdigit() if extracted_id else False,
                    }
                    
                    # Calculate overall authenticity score
                    base_score = ocr_confidence if extraction_method == "yolo" else min(ocr_confidence * 0.8, 1.0)
                    # Boost if document validation passes
                    validation_boost = 0.1 if all(doc_validation.values()) else 0
                    id_boost = 0.1 if all(id_validation.values()) else 0
                    auth_score = min(base_score + validation_boost + id_boost, 1.0)
                    
                    auth_checks = {
                        "ocr_confidence": ocr_confidence,
                        "extraction_method": extraction_method,
                        "expected_layout_found": extraction_method == "yolo",
                        "languages_found": detected_langs,
                        "document_validation": doc_validation,
                        "id_validation": id_validation,
                        "overall_authenticity_score": auth_score
                    }

                    # 3. Failure Reason (Structured)
                    error_msg = face_result.get("error")
                    failure_data = {}
                    
                    if error_msg:
                        failure_data = {"message": error_msg, "code": "processing_error"}
                    else:
                        # Check for business logic failures
                        failures = []
                        details = {}
                        
                        if not liveness_response.is_live:
                            failures.append("Liveness check failed")
                            details["liveness_error"] = liveness_response.error
                            
                        if similarity is not None:
                            if similarity <= 0.6:
                                failures.append(f"Face mismatch ({similarity:.2f})")
                            details["similarity_score"] = similarity
                        else:
                            failures.append("Face comparison failed (no score)")
                            
                        if failures:
                            code = "multiple_failures" if len(failures) > 1 else ("liveness_failed" if "Liveness" in failures[0] else "face_mismatch")
                            failure_data = {
                                "message": "; ".join(failures), 
                                "code": code,
                                "details": details
                            }

                    # Save to database
                    await save_verification(
                        session=db,
                        document_id=doc_record.id,
                        status=status_val,
                        similarity_score=similarity,
                        selfie_image_data=selfie_blob,
                        liveness_data=face_result.get("liveness") or {},
                        image_quality_metrics=quality_metrics,
                        authenticity_checks=auth_checks,
                        failure_reason=failure_data
                    )
                    
            except Exception as db_error:
                # Log error but don't fail the verification
                print(f"Warning: Failed to save to database: {db_error}")
                import traceback
                traceback.print_exc()
        
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
        
    except AppError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[{e.code}] {e.message} | Details: {e.details}")
        
        # Save structured error to DB
        try:
            failure_data = e.to_dict()
            if extracted_id:
                _doc = await save_document(
                    session=db,
                    document_number=extracted_id,
                    document_type=id_type or "unknown",
                    ocr_data={"extracted_id": extracted_id, "id_type": id_type},
                    front_image_data=None,
                    back_image_data=None
                )
                if _doc:
                    await save_verification(
                        session=db,
                        document_id=_doc.id,
                        status="failed",
                        similarity_score=None,
                        selfie_image_data=None,
                        liveness_data={},
                        image_quality_metrics={},
                        authenticity_checks={},
                        failure_reason=failure_data
                    )
        except Exception:
            pass  # Don't fail on DB save
        
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
            error=e.message
        )
    
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"[UNKNOWN_ERROR] {str(e)}")
        traceback.print_exc()
        
        # Save unknown error to DB
        try:
            failure_data = {
                "status": "error",
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "details": {}
            }
            if extracted_id:
                _doc = await save_document(
                    session=db,
                    document_number=extracted_id,
                    document_type=id_type or "unknown",
                    ocr_data={"extracted_id": extracted_id, "id_type": id_type},
                    front_image_data=None,
                    back_image_data=None
                )
                if _doc:
                    await save_verification(
                        session=db,
                        document_id=_doc.id,
                        status="failed",
                        similarity_score=None,
                        selfie_image_data=None,
                        liveness_data={},
                        image_quality_metrics={},
                        authenticity_checks={},
                        failure_reason=failure_data
                    )
        except Exception:
            pass  # Don't fail on DB save
        
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
            liveness=None,
            error=str(e)
        )


@router.post("/verify-json", response_model=VerifyResponse)
async def verify_identity_json(
    request: VerifyRequest,
    db: AsyncSession = Depends(get_db)
):
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
        search_result = await search_id_card_by_number(db, request.id_number)
        
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
        
    except AppError as e:
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
            error=e.message
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
