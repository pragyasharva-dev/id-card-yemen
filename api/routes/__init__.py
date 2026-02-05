"""
API Routes Module.

This module combines all route modules into a single router for the e-KYC system.
"""
from fastapi import APIRouter

from .health import router as health_router
from .quality import router as quality_router
from .verification import router as verification_router
from .validation import router as validation_router
from .ocr import router as ocr_router
from .face import router as face_router
from .translation import router as translation_router
from .database import router as database_router

# Combined router that includes all sub-routers
router = APIRouter()

router.include_router(health_router)
router.include_router(quality_router)
router.include_router(verification_router)
router.include_router(validation_router)
router.include_router(ocr_router)
router.include_router(face_router)
router.include_router(translation_router)
router.include_router(database_router)

__all__ = ["router"]
