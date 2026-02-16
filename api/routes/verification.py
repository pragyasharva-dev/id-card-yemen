"""e-KYC verification endpoints."""
import cv2
from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import VerifyRequest, VerifyResponse, LivenessResult
from services.ocr_service import extract_id_from_image, get_ocr_service
from services.id_card_parser import parse_yemen_id_card
from services.face_recognition import verify_identity
# from services.database import get_id_card_db  # Deprecated
from services.db import get_db
from services.data_service import save_document, save_verification
from services.image_quality_service import check_id_quality, check_selfie_quality
from services.field_comparison_service import compare_exact, compare_dates_with_tolerance, compare_gender_with_fraud_check
from services.name_matching_service import validate_name_match_simple, normalize_arabic_name, normalize_english_name
from difflib import SequenceMatcher
from services.yemen_id_validation_service import validate_yemen_id
from utils.image_manager import load_image, save_image
from utils.exceptions import AppError
from utils.config import PROCESSED_DIR

# New Policy Service
from services.verification_policy import VerificationPolicyService
from services.transliteration_core import arabic_to_latin
import uuid


router = APIRouter(tags=["Verification"])


def _is_arabic(text: str) -> bool:
    """Detect if text contains Arabic script."""
    return any('\u0600' <= ch <= '\u06FF' or '\u0750' <= ch <= '\u077F' for ch in text)


# ── Data Match comparison helpers ──────────────────────────────────────

def _compare_id(user_input: Optional[str], ocr_value: Optional[str]) -> float:
    """Compare user-entered ID number vs OCR-extracted using field_comparison_service."""
    if not user_input:
        return 1.0  # Not provided → skip
    result = compare_exact(ocr_value, user_input)
    return result["score"]


def _compare_name(user_input: Optional[str], parsed_data: dict) -> float:
    """Compare user-entered name vs matching-language OCR name.

    Detects whether user input is Arabic or English script,
    then compares only against the matching-language OCR name
    using validate_name_match_simple (same as compare_field uses).
    """
    if not user_input:
        return 1.0  # Not provided → skip

    # Detect language and pick the right OCR name
    if _is_arabic(user_input):
        ocr_name = parsed_data.get("name_arabic")
        language = "arabic"
    else:
        ocr_name = parsed_data.get("name_english")
        language = "english"

    if not ocr_name:
        # Cross-language fallback:
        # If user input is English but we only have Arabic OCR, try transliterating
        if language == "english":
            arabic_ocr = parsed_data.get("name_arabic")
            if arabic_ocr:
                try:
                    ocr_name = arabic_to_latin(arabic_ocr)
                    print(f"[NAME_MATCH] Cross-language fallback: transliterated '{arabic_ocr}' -> '{ocr_name}'")
                except Exception as e:
                    print(f"[NAME_MATCH] Transliteration failed: {e}")

    if not ocr_name:
        print(f"[NAME_MATCH] No OCR name for {language}")
        return 0.0  # OCR didn't extract a name in this language

    # Quick exact match after normalization
    if _is_arabic(user_input):
        ocr_norm = normalize_arabic_name(ocr_name)
        user_norm = normalize_arabic_name(user_input)
    else:
        ocr_norm = normalize_english_name(ocr_name)
        user_norm = normalize_english_name(user_input)

    # Exact match (same text)
    if ocr_norm == user_norm:
        print(f"[NAME_MATCH] EXACT match: '{ocr_name}' == '{user_input}'")
        return 1.0

    # Token-set match: same words in any order (handles Arabic family-name-first vs last)
    ocr_tokens = set(ocr_norm.split())
    user_tokens = set(user_norm.split())
    if ocr_tokens == user_tokens and len(ocr_tokens) > 0:
        print(f"[NAME_MATCH] TOKEN SET match (same words, different order): '{ocr_name}' vs '{user_input}'")
        return 1.0

    # Fuzzy token-set match: handles OCR typos and transliteration variants
    if len(ocr_tokens) > 0 and len(user_tokens) > 0:
        # Lower threshold for English (transliteration variance is higher)
        sim_threshold = 0.75 if language == "arabic" else 0.65

        def _best_token_match(token, candidates):
            """Find best matching token from candidates."""
            return max(SequenceMatcher(None, token, c).ratio() for c in candidates)

        # Count how many tokens from each side have a fuzzy match
        user_matched = sum(1 for t in user_tokens if _best_token_match(t, ocr_tokens) >= sim_threshold)
        ocr_matched = sum(1 for t in ocr_tokens if _best_token_match(t, user_tokens) >= sim_threshold)

        user_ratio = user_matched / len(user_tokens)
        ocr_ratio = ocr_matched / len(ocr_tokens)
        avg_ratio = (user_ratio + ocr_ratio) / 2

        # All tokens matched → perfect score
        if user_ratio == 1.0 and ocr_ratio == 1.0:
            print(f"[NAME_MATCH] FUZZY TOKEN SET match: '{ocr_name}' vs '{user_input}'")
            return 1.0

        # Most tokens matched (≥60%) → proportional high score
        if avg_ratio >= 0.6:
            score = 0.7 + (0.3 * avg_ratio)  # maps 0.6→0.88, 0.8→0.94, 1.0→1.0
            print(f"[NAME_MATCH] PARTIAL TOKEN match ({user_matched}/{len(user_tokens)} user, {ocr_matched}/{len(ocr_tokens)} ocr): score={score:.4f} | '{ocr_name}' vs '{user_input}'")
            return score

    result = validate_name_match_simple(
        ocr_name=ocr_name,
        user_name=user_input,
        language=language,
        ocr_confidence=1.0,
    )
    print(f"[NAME_MATCH] lang={language} | ocr='{ocr_name}' | user='{user_input}' | score={result['final_score']:.4f} | details={result.get('comparison', {})}")
    return result["final_score"]


def _compare_date(user_input: Optional[str], ocr_value: Optional[str]) -> float:
    """Compare dates using field_comparison_service with tolerance."""
    if not user_input:
        return 1.0  # Not provided → skip
    result = compare_dates_with_tolerance(ocr_value, user_input)
    return result["score"]


def _compare_gender(
    user_input: Optional[str], ocr_value: Optional[str],
    id_number: Optional[str] = None, id_type: str = "yemen_national_id"
) -> float:
    """Compare gender using field_comparison_service with fraud check."""
    if not user_input:
        return 1.0  # Not provided → skip
    # Normalize: OCR returns "Male"/"Female" (title case)
    normalized_gender = user_input.strip().title()
    result = compare_gender_with_fraud_check(
        ocr_gender=ocr_value,
        user_gender=normalized_gender,
        id_number=id_number or "",
        id_type=id_type,
    )
    return result["score"]

@router.post("/verify", response_model=VerifyResponse)
async def verify_identity_endpoint(
    id_card_front: UploadFile = File(..., description="ID card front side image"),
    selfie: UploadFile = File(..., description="Selfie image file"),
    id_card_back: UploadFile = File(None, description="ID card back side image (optional)"),
    # Optional user-entered data for Data Match scoring
    user_id_number: Optional[str] = Form(None, description="User-entered ID number"),
    user_name: Optional[str] = Form(None, description="User-entered name (Arabic or English)"),
    user_dob: Optional[str] = Form(None, description="User-entered date of birth (YYYY-MM-DD)"),
    user_issuance_date: Optional[str] = Form(None, description="User-entered issuance date (YYYY-MM-DD)"),
    user_expiry_date: Optional[str] = Form(None, description="User-entered expiry date (YYYY-MM-DD)"),
    user_gender: Optional[str] = Form(None, description="User-entered gender (Male/Female)"),
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

                    # --- Calculate quality and authenticity metrics FIRST ---
                    # These scores feed into the policy evaluation

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

                    # 2. Document Authenticity & Quality from validate_yemen_id()
                    ocr_confidence = float(front_ocr_result.get("confidence", 0.0))
                    extraction_method = front_ocr_result.get("extraction_method", "unknown")
                    
                    try:
                        doc_val = validate_yemen_id(id_card_front_image, id_card_back_image)
                        checks = doc_val.get("checks", {})
                        
                        # --- doc_authenticity (0-1): is this a real, original document? ---
                        auth_checks = [
                            1.0 if checks.get("official_document", {}).get("passed") else 0.0,
                            1.0 if checks.get("not_screenshot_or_copy", {}).get("passed") else 0.0,
                            1.0 if checks.get("original_and_genuine_front", {}).get("passed") else 0.0,
                            1.0 if checks.get("integrity", {}).get("passed") else 0.0,
                            1.0 if checks.get("no_extra_objects", {}).get("passed") else 0.0,
                        ]
                        auth_score = sum(auth_checks) / len(auth_checks)
                        
                        # --- doc_quality (0-1): is the image clear and usable? ---
                        clarity = checks.get("clear_and_readable", {})
                        visibility = checks.get("fully_visible", {})
                        obscured = checks.get("not_obscured", {})
                        
                        quality_scores = [
                            float(clarity.get("score", 0.0)) if clarity.get("score") is not None else (1.0 if clarity.get("passed") else 0.0),
                            float(visibility.get("score", 0.0)) if visibility.get("score") is not None else (1.0 if visibility.get("passed") else 0.0),
                            1.0 if obscured.get("passed") else 0.0,
                        ]
                        quality_score = sum(quality_scores) / len(quality_scores)
                        
                    except Exception as e:
                        # Fallback: use old method if validation service fails
                        import logging
                        logging.getLogger(__name__).warning(f"validate_yemen_id failed: {e}, using fallback scores")
                        base_score = ocr_confidence if extraction_method == "yolo" else min(ocr_confidence * 0.8, 1.0)
                        auth_score = min(base_score + 0.1, 1.0)
                        quality_score = id_quality.get("quality_score", 0.0)

                    # 3. Front/Back ID Match (compare IDs from front and back OCR)
                    front_back_match_score = 0.0
                    if back_ocr_result:
                        back_id = back_ocr_result.get("extracted_id")
                        if extracted_id and back_id and extracted_id == back_id:
                            front_back_match_score = 1.0
                        elif extracted_id and back_id:
                            front_back_match_score = 0.0  # mismatch
                    else:
                        # No back card provided — give full credit
                        front_back_match_score = 1.0

                    # --- Dynamic Policy Check ---
                    # Prepare ALL scores for policy evaluation (normalized 0-1)
                    policy_scores = {
                        # Face & Liveness
                        "face_match": face_result.get("similarity_score", 0.0),
                        "liveness": liveness_response.confidence if liveness_response else 0.0,
                        # Document Verification
                        "ocr_confidence": ocr_confidence,
                        "doc_quality": quality_score,
                        "doc_authenticity": auth_score,
                        "front_back_match": front_back_match_score,
                        # Data Match (user-entered vs OCR-extracted)
                        "id_number_match": _compare_id(user_id_number, extracted_id),
                        "name_match": _compare_name(user_name, parsed_data),
                        "dob_match": _compare_date(user_dob, parsed_data.get("date_of_birth")),
                        "issuance_date_match": _compare_date(user_issuance_date, parsed_data.get("issuance_date")),
                        "expiry_date_match": _compare_date(user_expiry_date, parsed_data.get("expiry_date")),
                        "gender_match": _compare_gender(user_gender, parsed_data.get("gender"), extracted_id, id_type or "yemen_national_id"),
                    }
                    
                    # Evaluate against KycConfig
                    policy_result = await VerificationPolicyService.evaluate_verification(db, policy_scores)
                    
                    # Generate Transaction ID
                    tx_id = str(uuid.uuid4())
                    
                    # Log to KycData
                    await VerificationPolicyService.log_result(
                        db, 
                        user_id=doc_record.id,  # using document id as user reference
                        scores=policy_scores, 
                        result=policy_result, 
                    )

                    # Update status based on Policy decision
                    if policy_result.decision == "APPROVED":
                        status_val = "verified"
                    elif policy_result.decision == "MANUAL_REVIEW":
                        status_val = "manual_review"
                    else:
                        status_val = "failed"
                    
                    if policy_result.reasons:
                        print(f"Policy Decision: {policy_result.decision} — {policy_result.reasons}")
                    # --- End Dynamic Policy Check ---

                    auth_checks = {
                        "ocr_confidence": ocr_confidence,
                        "extraction_method": extraction_method,
                        "expected_layout_found": extraction_method == "yolo",
                        "overall_authenticity_score": auth_score,
                        "policy_result": policy_result.to_dict()
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
