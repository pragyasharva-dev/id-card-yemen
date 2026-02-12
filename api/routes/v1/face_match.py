"""
API 2: Biometric Face Matching & Liveness Check

This endpoint performs:
1. Face detection and extraction from both images
2. Face similarity comparison
3. Passive liveness detection on selfie
4. Image quality assessment
5. Combined final score calculation
"""
import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Request, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from models.v1_schemas import (
    FaceMatchResponse,
    FaceMatchResult,
    LivenessResult_,
    SelfieImageQuality,
    FaceAndLivenessScore,
)
from services.face_recognition import compare_faces
from services.liveness_service import detect_spoof
from services.image_quality_service import check_selfie_quality
from utils.image_manager import load_image
from services.scoring_service import calculate_face_liveness_score
from services.db import get_db
from services.config_service import get_dynamic_config
from utils.config import (
    FACE_MATCH_THRESHOLD as DEFAULT_FACE_MATCH_THRESHOLD,
    LIVENESS_ENABLED as DEFAULT_LIVENESS_ENABLED,
    LIVENESS_THRESHOLD as DEFAULT_LIVENESS_THRESHOLD,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/face-match", tags=["Face Match"])


def _parse_json_form(json_str: str, field_name: str) -> dict:
    """Parse JSON string."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in {field_name}: {str(e)}")


def _determine_face_match_status(score: float, has_error: bool, threshold: float = None) -> str:
    """Determine face match status per contract: MATCH | NO_MATCH | INCONCLUSIVE."""
    if has_error:
        return "INCONCLUSIVE"
    if threshold is None:
        threshold = DEFAULT_FACE_MATCH_THRESHOLD
    threshold_100 = threshold * 100
    if score >= threshold_100:
        return "MATCH"
    elif score >= threshold_100 * 0.7:
        return "INCONCLUSIVE"
    return "NO_MATCH"


def _determine_liveness_result(is_live: bool, has_error: bool, enabled: bool = True) -> str:
    """Determine liveness result per contract: LIVE | NOT_LIVE."""
    if not enabled:
        return "LIVE"  # Or "DISABLED"? Contract says enum. Treating as LIVE is safest fallback.
    if has_error:
        return "NOT_LIVE"
    return "LIVE" if is_live else "NOT_LIVE"


@router.post("", response_model=FaceMatchResponse)
async def face_match_endpoint(
    request: Request,
    metadata: str = Form(..., alias="metadata", description="JSON: transactionId, documentType"),
    selfie_image: UploadFile = File(..., alias="selfieImage", description="User selfie image (live capture)"),
    id_front_image: UploadFile = File(..., alias="idFrontImage", description="ID card front image with face"),
    db: AsyncSession = Depends(get_db),
):
    """
    Biometric Face Matching & Liveness Check (API 2 Contract)
    
    Compares selfie with ID card face, performs liveness detection,
    and returns combined score.
    
    Constraints:
    - No approval or rejection decision shall be returned
    - No thresholds shall be exposed
    """
    errors = []
    
    # Parse metadata
    meta = _parse_json_form(metadata, "metadata")
    transaction_id = meta.get("transactionId", "unknown")
    
    try:
        # Fetch dynamic threshold from DB (falls back to config.py default)
        face_match_threshold = await get_dynamic_config(
            db, "FACE_MATCH_THRESHOLD", DEFAULT_FACE_MATCH_THRESHOLD
        )
        liveness_enabled = await get_dynamic_config(
            db, "LIVENESS_ENABLED", DEFAULT_LIVENESS_ENABLED
        )
        liveness_threshold = await get_dynamic_config(
            db, "LIVENESS_THRESHOLD", DEFAULT_LIVENESS_THRESHOLD
        )

        # Load images
        selfie_bytes = await selfie_image.read()
        id_bytes = await id_front_image.read()
        
        try:
            selfie_img = load_image(selfie_bytes)
        except ValueError:
            return FaceMatchResponse(
                transaction_id=transaction_id,
                face_match=FaceMatchResult(status="INCONCLUSIVE", score=0.0),
                liveness=LivenessResult_(result="NOT_LIVE", confidence_score=0.0),
                image_quality=SelfieImageQuality(score=0.0, failure_reasons=["Could not decode selfie"]),
                final_score=0.0,
                errors=["Failed to load selfie image"]
            )
        
        try:
            id_img = load_image(id_bytes)
        except ValueError:
            return FaceMatchResponse(
                transaction_id=transaction_id,
                face_match=FaceMatchResult(status="INCONCLUSIVE", score=0.0),
                liveness=LivenessResult_(result="NOT_LIVE", confidence_score=0.0),
                image_quality=SelfieImageQuality(score=0.0, failure_reasons=["Could not decode ID image"]),
                final_score=0.0,
                errors=["Failed to load ID card image"]
            )
        
        # Run face comparison (CPU-bound)
        face_result = await run_in_threadpool(compare_faces, selfie_img, id_img)
        
        # Normalize score to 0-100 scale
        raw_score = face_result.get("similarity_score", 0.0)
        normalized_score = raw_score * 100
        
        has_face_error = bool(face_result.get("error"))
        if has_face_error:
            errors.append(f"Face comparison error: {face_result['error']}")
        
        face_match = FaceMatchResult(
            score=normalized_score,
            status=_determine_face_match_status(normalized_score, has_face_error, face_match_threshold)
        )
        
        # Run liveness detection on selfie
        if liveness_enabled:
            # Pass dynamic threshold to switch from strict mode to score mode
            liveness_result = await run_in_threadpool(detect_spoof, selfie_img, liveness_threshold)
            
            is_live = liveness_result.get("is_live", False)
            liveness_confidence = liveness_result.get("confidence", 0.0) * 100
            
            has_liveness_error = bool(liveness_result.get("error"))
            if has_liveness_error:
                errors.append(f"Liveness error: {liveness_result['error']}")
        else:
            # Liveness disabled - simulate perfect score
            is_live = True
            liveness_confidence = 100.0
            has_liveness_error = False
            liveness_result = {}
        
        liveness = LivenessResult_(
            result=_determine_liveness_result(is_live, has_liveness_error, liveness_enabled),
            confidence_score=liveness_confidence
        )
        
        # Run image quality assessment on selfie
        selfie_quality_result = await run_in_threadpool(check_selfie_quality, selfie_img)
        
        image_quality = SelfieImageQuality(
            score=selfie_quality_result.get("overall_quality", 0.0),
            failure_reasons=selfie_quality_result.get("issues", [])
        )
        
        # Calculate Face and Liveness Score breakdown
        face_and_liveness_score = calculate_face_liveness_score(
            face_match_score=normalized_score,
            liveness_confidence=liveness_confidence,
            is_live=is_live
        )
        
        # Calculate final score (weighted combination for display)
        # Re-calc using weights relative to total 100
        # This is just for the 'final_score' field required by API 2 contract
        # which combines Face + Liveness + Quality for this endpoint context
        final_score = (
            (normalized_score * 0.6) +
            (liveness_confidence * 0.3) +
            (selfie_quality_result.get("overall_quality", 0.0) * 100 * 0.1)
        )
        
        return FaceMatchResponse(
            transaction_id=transaction_id,
            face_match=face_match,
            liveness=liveness,
            image_quality=image_quality,
            final_score=final_score,
            errors=errors,
            face_and_liveness_score=face_and_liveness_score,
        )
        
    except Exception as e:
        logger.exception(f"Face match failed: {e}")
        return FaceMatchResponse(
            transaction_id=transaction_id,
            face_match=FaceMatchResult(status="INCONCLUSIVE", score=0.0),
            liveness=LivenessResult_(result="NOT_LIVE", confidence_score=0.0),
            image_quality=SelfieImageQuality(score=0.0),
            final_score=0.0,
            errors=[f"Unexpected error: {str(e)}"]
        )
