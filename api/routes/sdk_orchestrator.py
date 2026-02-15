"""
SDK Orchestrator Endpoint
-------------------------
This module provides a single endpoint for the SDK to perform full e-KYC verification.
It orchestrates OCR, Liveness, and Face Matching in a single request and persists
results to the local database.
"""
import time
import cv2
import logging
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import VerifyResponse, LivenessResult
from services.db import get_db
from services.ocr_service import extract_id_from_image, get_ocr_service
from services.face_recognition import verify_identity
from services.id_card_parser import parse_yemen_id_card
from services.data_service import save_document, save_verification
from services.image_quality_service import check_id_quality, check_selfie_quality
from utils.image_manager import load_image, save_image
from utils.exceptions import AppError, ImageProcessingError
from utils.config import PROCESSED_DIR

router = APIRouter(tags=["SDK Verification"])
logger = logging.getLogger(__name__)

@router.post("/sdk/verify", response_model=VerifyResponse)
async def sdk_verify(
    id_front: UploadFile = File(..., description="ID card front image"),
    id_back: UploadFile = File(..., description="ID card back image"),
    selfie: UploadFile = File(..., description="Selfie image"),
    db: AsyncSession = Depends(get_db)
):
    """
    SDK Orchestration Endpoint.
    
    Performs full verification workflow in one request:
    1. OCR extraction (Front + Back)
    2. Face Verification (ID vs Selfie)
    3. Liveness Check (on Selfie)
    4. Data Persistence (Documents + Verifications tables)
    """
    # Initialize variables for error handling context
    extracted_id = None
    id_type = None
    id_front_filename = None
    id_back_filename = None
    parsed_data = {}
    liveness_response = None
    doc_record = None

    try:
        # 1. Load Images
        front_bytes = await id_front.read()
        back_bytes = await id_back.read()
        selfie_bytes = await selfie.read()

        front_img = load_image(front_bytes)
        back_img = load_image(back_bytes)
        selfie_img = load_image(selfie_bytes)

        if front_img is None or back_img is None or selfie_img is None:
            raise ImageProcessingError("Failed to decode one or more images")

        # 2. Extract ID Data (OCR)
        # Front
        front_ocr = extract_id_from_image(front_img)
        extracted_id = front_ocr.get("extracted_id")
        id_type = front_ocr.get("id_type")
        
        # Back
        ocr_service = get_ocr_service()
        back_ocr = ocr_service.process_id_card(back_img, side="back")
        
        # Parse & Merge Data
        parsed_data = parse_yemen_id_card(front_ocr, back_ocr)

        # 3. Save Processed Images (if ID found)
        if extracted_id:
            timestamp = int(time.time())
            id_front_filename = f"{extracted_id}_front_{timestamp}.jpg"
            id_back_filename = f"{extracted_id}_back_{timestamp}.jpg"
            save_image(front_img, id_front_filename, PROCESSED_DIR)
            save_image(back_img, id_back_filename, PROCESSED_DIR)

        # 4. Face Verification + Liveness
        face_result = verify_identity(front_img, selfie_img)
        
        # Build Liveness Response
        if face_result.get("liveness"):
            live_data = face_result["liveness"]
            liveness_response = LivenessResult(
                is_live=live_data.get("is_live", False),
                confidence=live_data.get("confidence", 0.0),
                spoof_probability=live_data.get("spoof_probability", 1.0),
                checks=live_data.get("checks", {}),
                error=live_data.get("error")
            )

        # 5. Handle Processing Errors (e.g. Face Not Detected)
        if face_result.get("error"):
            # Logic to save failure to DB
            if extracted_id:
                try:
                    await _save_failure_to_db(
                        db, extracted_id, id_type, parsed_data, front_ocr,
                        front_img, back_img, face_result.get("liveness"),
                        {"status": "error", "code": "PROCESSING_ERROR", "message": face_result["error"]}
                    )
                except Exception:
                    logger.exception("Failed to save processing error to DB")
            
            return _build_response(False, extracted_id, id_type, None, id_front_filename, id_back_filename, parsed_data, liveness_response, face_result["error"])

        # 6. Success Path - Persist to DB
        if extracted_id:
             # Prepare blobs
            _, front_enc = cv2.imencode('.jpg', front_img)
            _, back_enc = cv2.imencode('.jpg', back_img)
            _, selfie_enc = cv2.imencode('.jpg', selfie_img)
            
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
                "confidence": front_ocr.get("confidence"),
                "extraction_method": front_ocr.get("extraction_method")
            }

            # Upsert Document
            doc_record = await save_document(
                session=db,
                document_number=extracted_id,
                document_type=id_type or "unknown",
                ocr_data=ocr_store_data,
                front_image_data=front_enc.tobytes(),
                back_image_data=back_enc.tobytes()
            )

            # Determine Verification Status based on business logic
            is_live = liveness_response.is_live if liveness_response else False
            similarity = face_result.get("similarity_score", 0.0)
            
            # --- Status Logic ---
            if similarity and similarity > 0.6 and is_live:
                status_val = "verified"
            else:
                status_val = "failed"
            
            # --- Failure Reason ---
            failure_reason = {}
            if status_val == "failed":
                reasons = []
                details = {}
                if not is_live: 
                    reasons.append("Liveness check failed")
                    details["liveness_error"] = liveness_response.error if liveness_response else None
                if similarity is None or similarity <= 0.6: 
                    reasons.append(f"Face mismatch ({similarity:.2f})" if similarity is not None else "Face comparison failed")
                    details["similarity_score"] = similarity
                
                code = "multiple_failures" if len(reasons) > 1 else ("liveness_failed" if "Liveness" in reasons[0] else "face_mismatch")
                failure_reason = {
                     "code": code, 
                     "message": "; ".join(reasons),
                     "details": details
                }

            # --- Save Verification ---
            if doc_record:
                # Calculate quality metrics
                id_quality = check_id_quality(front_img)
                selfie_quality = check_selfie_quality(selfie_img)
                quality_metrics = {
                    "id_card": {"score": id_quality.get("quality_score"), "details": id_quality.get("details")},
                    "selfie": {"score": selfie_quality.get("quality_score"), "details": selfie_quality.get("details")}
                }
                
                await save_verification(
                    session=db,
                    document_id=doc_record.id,
                    status=status_val,
                    similarity_score=similarity,
                    selfie_image_data=selfie_enc.tobytes(),
                    liveness_data=face_result.get("liveness") or {},
                    image_quality_metrics=quality_metrics,
                    authenticity_checks={"ocr_confidence": front_ocr.get("confidence")},
                    failure_reason=failure_reason
                )

        return _build_response(True, extracted_id, id_type, face_result.get("similarity_score"), id_front_filename, id_back_filename, parsed_data, liveness_response, None)

    except AppError as e:
        logger.error(f"[{e.code}] {e.message} | Details: {e.details}")
        if extracted_id:
            try:
                await _save_failure_to_db(
                    db, extracted_id, id_type, parsed_data, locals().get('front_ocr', {}),
                    locals().get('front_img'), locals().get('back_img'), 
                    {}, e.to_dict()
                )
            except Exception:
                pass
        return _build_response(False, extracted_id, id_type, None, id_front_filename, id_back_filename, parsed_data, liveness_response, e.message)

    except Exception as e:
        logger.exception("Unknown error in SDK verify")
        if extracted_id:
             try:
                await _save_failure_to_db(
                    db, extracted_id, id_type, parsed_data, locals().get('front_ocr', {}),
                    locals().get('front_img'), locals().get('back_img'), 
                    {}, {"code": "UNKNOWN_ERROR", "message": str(e)}
                )
             except Exception:
                 pass
        return _build_response(False, extracted_id, id_type, None, id_front_filename, id_back_filename, parsed_data, liveness_response, str(e))


async def _save_failure_to_db(db, extracted_id, id_type, parsed_data, front_ocr, front_img, back_img, liveness_data, failure_data):
    """Helper to persist failure data to DB when verification fails or errors occur."""
    if not extracted_id:
        return
        
    # Prepare image blobs
    front_blob = None
    back_blob = None
    if front_img is not None:
        _, enc = cv2.imencode('.jpg', front_img)
        front_blob = enc.tobytes()
    if back_img is not None:
        _, enc = cv2.imencode('.jpg', back_img)
        back_blob = enc.tobytes()
        
    # Prepare OCR data
    ocr_store_data = {
        "extracted_id": extracted_id,
        "id_type": id_type,
        "name_arabic": parsed_data.get("name_arabic"),
        "name_english": parsed_data.get("name_english"),
        "date_of_birth": parsed_data.get("date_of_birth"),
        "confidence": front_ocr.get("confidence") if front_ocr else None,
    }
    
    # Save Document
    doc_record = await save_document(
        session=db,
        document_number=extracted_id,
        document_type=id_type or "unknown",
        ocr_data=ocr_store_data,
        front_image_data=front_blob,
        back_image_data=back_blob
    )
    
    # Save Verification (Failed)
    if doc_record:
        await save_verification(
            session=db,
            document_id=doc_record.id,
            status="failed",
            similarity_score=None,
            selfie_image_data=None, # Only ID images saved on error to save space/bandwidth
            liveness_data=liveness_data or {},
            image_quality_metrics={}, 
            authenticity_checks={},
            failure_reason=failure_data
        )

def _build_response(success, extracted_id, id_type, score, front, back, parsed, liveness, error):
    """Helper to build VerifyResponse object."""
    return VerifyResponse(
        success=success,
        extracted_id=extracted_id,
        id_type=id_type,
        similarity_score=score,
        id_front=front,
        id_back=back,
        name_arabic=parsed.get("name_arabic"),
        name_english=parsed.get("name_english"),
        date_of_birth=parsed.get("date_of_birth"),
        gender=parsed.get("gender"),
        place_of_birth=parsed.get("place_of_birth"),
        issuance_date=parsed.get("issuance_date"),
        expiry_date=parsed.get("expiry_date"),
        liveness=liveness,
        error=error
    )
