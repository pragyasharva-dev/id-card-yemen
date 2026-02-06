"""
e-KYC Verification API

A modular e-KYC (electronic Know Your Customer) verification system
that compares facial images from ID cards with selfies.

Usage:
    uvicorn main:app --reload
    
Then access the API documentation at http://localhost:8000/docs
"""
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from utils.exceptions import AppError
from utils.logging_config import configure_logging
from utils.config import API_KEYS, LOG_LEVEL, LOG_JSON_FORMAT
from middleware.request_id import RequestIDMiddleware
from middleware.api_key import APIKeyMiddleware

# Configure structured JSON logging
configure_logging(level=LOG_LEVEL, json_format=LOG_JSON_FORMAT)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Initializes models on startup for faster first requests.
    """
    logger.info("Starting e-KYC API...")
    
    # Pre-load OCR model
    try:
        from services.ocr_service import get_ocr_service
        logger.info("Loading OCR model...")
        get_ocr_service()
        logger.info("OCR model loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to preload OCR model: {e}")
    
    # Pre-load face recognition model
    try:
        from services.face_extractor import get_face_extractor, is_available
        if is_available():
            logger.info("Loading face recognition model...")
            get_face_extractor()
            logger.info("Face recognition model loaded successfully")
        else:
            logger.warning("InsightFace not installed - face recognition disabled")
    except Exception as e:
        logger.warning(f"Failed to preload face recognition model: {e}")
    
    # Pre-load YOLO layout detection models
    try:
        from services.layout_service import get_layout_service, is_layout_available
        logger.info("Loading YOLO layout detection models...")
        layout_service = get_layout_service()
        if is_layout_available("yemen_id_front"):
            logger.info("YOLO front model loaded successfully")
        if is_layout_available("yemen_id_back"):
            logger.info("YOLO back model loaded successfully")
        if not layout_service.models:
            logger.warning("No YOLO models found - layout detection disabled")
    except Exception as e:
        logger.warning(f"Failed to preload YOLO models: {e}")
    
    logger.info("e-KYC API ready!")
    
    yield  # Application runs here
    
    logger.info("Shutting down e-KYC API...")


# Create FastAPI application
app = FastAPI(
    title="e-KYC Verification API",
    description="""
    Electronic Know Your Customer (e-KYC) verification API.
    
    ## Features
    
    * **ID Card OCR**: Extract unique ID numbers from various ID cards (Aadhaar, PAN, Yemen ID, etc.)
    * **Face Extraction**: Detect and extract faces from ID card photos
    * **Face Comparison**: Compare ID card face with selfie using InsightFace
    * **Similarity Score**: Returns confidence score (0.0 - 1.0) for face matching
    
    ## Workflow
    
    1. Upload ID card image and selfie to `/verify` endpoint
    2. System extracts ID number using OCR with intelligent pattern matching
    3. System extracts face from ID card and compares with selfie
    4. Returns extracted ID and similarity score
    """,
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware (order matters: first added = outermost)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(APIKeyMiddleware, api_keys=API_KEYS)


# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """
    Global handler for all AppError exceptions.
    
    Converts custom exceptions to consistent JSON responses.
    """
    logger.warning(f"[{exc.code}] {exc.message} | Details: {exc.details}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

# Include API routes
from api.routes import router as production_router
from api.test_routes import test_router
from api.routes.metrics import router as metrics_router
app.include_router(production_router, prefix="/api/v1")
app.include_router(test_router, prefix="/test", tags=["Testing"])
app.include_router(metrics_router)  # /metrics at root level

# Serve static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the frontend page."""
    return FileResponse(static_dir / "index.html")


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "e-KYC Verification API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
