"""Health check endpoints."""
from fastapi import APIRouter

from models.schemas import HealthResponse
from services.ocr_service import get_ocr_service
from services.face_recognition import is_ready as face_ready

router = APIRouter(tags=["Health"])


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
