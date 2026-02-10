"""
Custom Application Exceptions.

Provides a hierarchy of exceptions for consistent error handling.

Usage:
    from utils.exceptions import ServiceError, ResourceNotFoundError
    
    # In services
    raise ServiceError("Face not detected", code="FACE_NOT_FOUND")
    
    # In database operations
    raise ResourceNotFoundError("IDCard", id_number)
"""
from typing import Optional, Dict, Any


class AppError(Exception):
    """
    Base exception for all application errors.
    
    Attributes:
        message: Human-readable error description
        code: Machine-readable error code (e.g., "FACE_NOT_FOUND")
        status_code: HTTP status code to return
        details: Additional context for debugging
    """
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to API response format."""
        return {
            "status": "error",
            "code": self.code,
            "message": self.message,
            "details": self.details
        }


# =============================================================================
# SERVICE LAYER EXCEPTIONS (400-level errors)
# =============================================================================

class ServiceError(AppError):
    """
    General service-layer error (bad input, processing failure).
    
    Use for: Generic service failures not covered by specific exceptions below.
    """
    def __init__(
        self,
        message: str,
        code: str = "SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, status_code=400, details=details)


class ImageProcessingError(ServiceError):
    """
    Image is invalid, corrupt, or does not meet requirements.
    
    Use for: Corrupt uploads, images too small, unreadable formats.
    """
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code="IMAGE_PROCESSING_ERROR", details=details)


class OCRExtractionError(ServiceError):
    """
    OCR failed to extract expected data from the image.
    
    Use for: No ID number found, text unreadable, layout detection failed.
    """
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        _details = details or {}
        if field:
            _details["field"] = field
        super().__init__(message, code="OCR_EXTRACTION_ERROR", details=_details)


class FaceDetectionError(ServiceError):
    """
    Face could not be detected or extracted from image.
    
    Use for: No face in ID card, no face in selfie, multiple faces detected.
    """
    def __init__(
        self,
        message: str,
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        _details = details or {}
        if source:
            _details["source"] = source  # "id_card" or "selfie"
        super().__init__(message, code="FACE_DETECTION_ERROR", details=_details)


class ValidationError(AppError):
    """
    Input validation failed.
    
    Use for: Invalid date format, Missing required field, etc.
    """
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        _details = details or {}
        if field:
            _details["field"] = field
        super().__init__(message, "VALIDATION_ERROR", status_code=422, details=_details)


class ResourceNotFoundError(AppError):
    """
    Requested resource not found in database.
    
    Use for: ID card not found, Passport not found, etc.
    """
    def __init__(
        self,
        resource: str,
        identifier: str,
        details: Optional[Dict[str, Any]] = None
    ):
        _details = details or {}
        _details["resource"] = resource
        _details["identifier"] = identifier
        super().__init__(
            f"{resource} with identifier '{identifier}' not found",
            "NOT_FOUND",
            status_code=404,
            details=_details
        )


# =============================================================================
# INFRASTRUCTURE EXCEPTIONS (500-level errors)
# =============================================================================

class ModelLoadError(AppError):
    """
    ML model failed to load.
    
    Use for: OCR model, Face recognition model, YOLO model, etc.
    """
    def __init__(
        self,
        model_name: str,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        _details = details or {}
        _details["model"] = model_name
        if reason:
            _details["reason"] = reason
        super().__init__(
            f"Failed to load model: {model_name}",
            "MODEL_LOAD_ERROR",
            status_code=503,
            details=_details
        )


class ExternalServiceError(AppError):
    """
    External service/API call failed.
    
    Use for: Translation API, Database connection, etc.
    """
    def __init__(
        self,
        service_name: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        _details = details or {}
        _details["service"] = service_name
        super().__init__(
            f"{service_name} error: {message}",
            "EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=_details
        )


class DatabaseError(AppError):
    """
    Database connection or query failed.
    
    Use for: Connection timeouts, query failures, constraint violations.
    """
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        _details = details or {}
        if operation:
            _details["operation"] = operation  # "insert", "update", "query", "connect"
        super().__init__(
            f"Database error: {message}",
            "DATABASE_ERROR",
            status_code=500,
            details=_details
        )
