"""Image quality and liveness check endpoints."""
from fastapi import APIRouter, UploadFile, File

from models.schemas import ImageQualityResponse, LivenessResult
from utils.image_manager import load_image

router = APIRouter(tags=["Quality"])


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
