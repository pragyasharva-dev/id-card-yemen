"""
Pydantic models for API request/response schemas.
"""
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

# Import form validators for ID card data entry
from models.form_validators import (
    YemenNationalIDForm,
    YemenPassportForm,
    IDFormSubmitRequest,
    IDFormSubmitResponse,
    IDFormValidationError
)


class VerifyRequest(BaseModel):
    """Request model for the /verify endpoint."""
    id_number: str = Field(
        ..., 
        description="ID number to search for in the database"
    )
    selfie_path: Optional[str] = Field(
        None, 
        description="Path to the selfie image file"
    )
    selfie_base64: Optional[str] = Field(
        None, 
        description="Base64 encoded selfie image"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id_number": "123456789012",
                "selfie_path": "data/selfies/sample_01.png"
            }
        }


class TextResult(BaseModel):
    """Individual text result with language detection."""
    text: str = Field(..., description="Extracted text")
    score: float = Field(0.0, description="OCR confidence score")
    detected_language: str = Field("en", description="Detected language code")
    detected_language_display: str = Field("English 🇬🇧", description="Language name with flag")


class OCRResult(BaseModel):
    """Result of OCR extraction from ID card."""
    extracted_id: Optional[str] = Field(
        None, 
        description="Extracted unique ID number"
    )
    id_type: Optional[str] = Field(
        None, 
        description="Detected ID type (aadhaar, pan, yemen_id, etc.)"
    )
    confidence: float = Field(
        0.0, 
        description="OCR confidence score"
    )
    all_texts: List[str] = Field(
        default_factory=list, 
        description="All text extracted by OCR"
    )
    text_results: List[TextResult] = Field(
        default_factory=list,
        description="Detailed text results with per-text language detection"
    )
    detected_languages: List[str] = Field(
        default_factory=list,
        description="List of detected language codes"
    )
    detected_languages_display: List[str] = Field(
        default_factory=list,
        description="List of detected languages with names and flags"
    )


class FaceMatchResult(BaseModel):
    """Result of face comparison."""
    similarity_score: float = Field(
        ..., 
        description="Cosine similarity between faces (0.0 to 1.0)"
    )
    id_card_face_detected: bool = Field(
        ..., 
        description="Whether a face was detected in ID card"
    )
    selfie_face_detected: bool = Field(
        ..., 
        description="Whether a face was detected in selfie"
    )


class LivenessCheckResult(BaseModel):
    """Result of an individual liveness check."""
    passed: bool = Field(..., description="Whether this check passed")
    score: float = Field(..., description="Raw score for this check")
    threshold: float = Field(..., description="Threshold used for comparison")


class LivenessResult(BaseModel):
    """Complete liveness detection result."""
    is_live: bool = Field(
        ..., 
        description="Whether the image appears to be from a live person"
    )
    confidence: float = Field(
        ..., 
        description="Overall liveness confidence (0.0-1.0)"
    )
    spoof_probability: float = Field(
        ..., 
        description="Probability that this is a spoof attempt (0.0-1.0)"
    )
    checks: dict = Field(
        default_factory=dict,
        description="Individual check results (texture, color, sharpness, reflection)"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if liveness detection failed"
    )


class VerifyResponse(BaseModel):
    """Response model for the /verify endpoint."""
    success: bool = Field(
        ..., 
        description="Whether the verification process completed successfully"
    )
    extracted_id: Optional[str] = Field(
        None, 
        description="Extracted unique ID number from the ID card"
    )
    id_type: Optional[str] = Field(
        None, 
        description="Detected type of ID card"
    )
    similarity_score: Optional[float] = Field(
        None, 
        description="Face similarity score (0.0 to 1.0)"
    )
    id_front: Optional[str] = Field(
        None,
        description="Filename of the front ID card image"
    )
    id_back: Optional[str] = Field(
        None,
        description="Filename of the back ID card image"
    )
    # Structured ID card data fields
    name_arabic: Optional[str] = Field(
        None,
        description="Cardholder name in Arabic"
    )
    name_english: Optional[str] = Field(
        None,
        description="Cardholder name in English"
    )
    date_of_birth: Optional[str] = Field(
        None,
        description="Date of birth in YYYY-MM-DD format"
    )
    gender: Optional[str] = Field(
        None,
        description="Gender (Male/Female)"
    )
    place_of_birth: Optional[str] = Field(
        None,
        description="Place of Birth"
    )
    issuance_date: Optional[str] = Field(
        None,
        description="ID card issuance date in YYYY-MM-DD format"
    )
    expiry_date: Optional[str] = Field(
        None,
        description="ID card expiry date in YYYY-MM-DD format"
    )
    liveness: Optional[LivenessResult] = Field(
        None,
        description="Liveness detection result for the selfie (warning only, non-blocking)"
    )
    error: Optional[str] = Field(
        None, 
        description="Error message if verification failed"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "extracted_id": "123456789012",
                "id_type": "yemen_id",
                "similarity_score": 0.85,
                "id_front": "123456789012_front_1234567890.jpg",
                "id_back": "123456789012_back_1234567890.jpg",
                "name_arabic": "أحمد محمد علي",
                "name_english": "Ahmed Mohammed Ali",
                "date_of_birth": "1990-05-15",
                "gender": "Male",
                "address": "Sanaa, Yemen",
                "issuance_date": "2020-01-10",
                "expiry_date": "2030-01-10",
                "error": None
            }
        }


class ExtractIDRequest(BaseModel):
    """Request model for the /extract-id endpoint."""
    image_path: Optional[str] = Field(
        None, 
        description="Path to the ID card image"
    )
    image_base64: Optional[str] = Field(
        None, 
        description="Base64 encoded ID card image"
    )


class ExtractIDResponse(BaseModel):
    """Response model for the /extract-id endpoint."""
    success: bool
    ocr_result: Optional[OCRResult] = None
    error: Optional[str] = None


class CompareFacesRequest(BaseModel):
    """Request model for the /compare-faces endpoint."""
    image1_path: Optional[str] = None
    image2_path: Optional[str] = None
    image1_base64: Optional[str] = None
    image2_base64: Optional[str] = None


class CompareFacesResponse(BaseModel):
    """Response model for the /compare-faces endpoint."""
    success: bool
    similarity_score: Optional[float] = None
    error: Optional[str] = None


class BatchProcessRequest(BaseModel):
    """Request for batch processing ID cards."""
    id_cards_directory: str = Field(
        ..., 
        description="Directory containing ID card images"
    )


class BatchProcessResponse(BaseModel):
    """Response for batch processing."""
    success: bool
    processed_count: int = 0
    failed_count: int = 0
    results: List[dict] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ImageQualityResponse(BaseModel):
    """Response for image quality check endpoints (/check-id-quality, /check-selfie-quality)."""
    passed: bool = Field(..., description="Whether the image quality check passed")
    face_detected: bool = Field(..., description="Whether a face was detected in the image")
    quality_score: float = Field(..., description="Quality score (0.0-1.0)")
    error: Optional[str] = Field(None, description="Error message if check failed")
    details: Optional[dict] = Field(None, description="Detailed quality check breakdown")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    ocr_ready: bool = False
    face_recognition_ready: bool = False
    liveness_enabled: bool = False
    face_quality_enabled: bool = False


# Translation schemas
class TranslateRequest(BaseModel):
    """Request model for the /translate endpoint."""
    texts: List[str] = Field(
        ..., 
        description="List of Arabic texts to translate to English"
    )


class TranslatedText(BaseModel):
    """Single translation result."""
    original: str = Field(..., description="Original Arabic text")
    translated: str = Field(..., description="Translated English text")


class TranslateResponse(BaseModel):
    """Response model for the /translate endpoint."""
    success: bool = Field(..., description="Whether translation completed successfully")
    translations: List[TranslatedText] = Field(
        default_factory=list,
        description="List of translation results"
    )
    error: Optional[str] = Field(None, description="Error message if translation failed")


# =====================================================
# DATABASE SCHEMAS - ID Card and Passport Storage
# =====================================================

class SaveIDCardRequest(BaseModel):
    """Request model for saving ID card data to database."""
    national_id: str = Field(..., description="11-digit Yemen National ID number")
    name_arabic: Optional[str] = Field(None, description="Full name in Arabic")
    name_english: Optional[str] = Field(None, description="Full name in English")
    # Or individual name components
    first_name_arabic: Optional[str] = Field(None, description="First name in Arabic")
    middle_name_arabic: Optional[str] = Field(None, description="Middle name in Arabic")
    last_name_arabic: Optional[str] = Field(None, description="Last name in Arabic")
    first_name_english: Optional[str] = Field(None, description="First name in English")
    middle_name_english: Optional[str] = Field(None, description="Middle name in English")
    last_name_english: Optional[str] = Field(None, description="Last name in English")
    date_of_birth: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    gender: Optional[str] = Field(None, description="Male/Female")
    nationality: Optional[str] = Field("Yemeni", description="Nationality")
    address: Optional[str] = Field(None, description="Full address")
    governorate: Optional[str] = Field(None, description="Governorate/Province")
    issuance_date: Optional[str] = Field(None, description="Card issuance date")
    expiry_date: Optional[str] = Field(None, description="Card expiry date")
    front_image_path: Optional[str] = Field(None, description="Path to front image")
    back_image_path: Optional[str] = Field(None, description="Path to back image")


class SavePassportRequest(BaseModel):
    """Request model for saving passport data to database."""
    passport_number: str = Field(..., description="Passport number")
    name_arabic: Optional[str] = Field(None, description="Full name in Arabic")
    name_english: Optional[str] = Field(None, description="Full name in English")
    # Or individual name components
    first_name_arabic: Optional[str] = Field(None, description="First name in Arabic")
    middle_name_arabic: Optional[str] = Field(None, description="Middle name in Arabic")
    last_name_arabic: Optional[str] = Field(None, description="Last name in Arabic")
    first_name_english: Optional[str] = Field(None, description="First name in English")
    middle_name_english: Optional[str] = Field(None, description="Middle name in English")
    last_name_english: Optional[str] = Field(None, description="Last name in English")
    date_of_birth: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    place_of_birth: Optional[str] = Field(None, description="Place of birth")
    gender: Optional[str] = Field(None, description="Male/Female")
    nationality: Optional[str] = Field("Yemeni", description="Nationality")
    passport_type: Optional[str] = Field("Ordinary", description="Passport type")
    issuance_date: Optional[str] = Field(None, description="Passport issuance date")
    expiry_date: Optional[str] = Field(None, description="Passport expiry date")
    issuing_authority: Optional[str] = Field(None, description="Issuing authority")
    mrz_line_1: Optional[str] = Field(None, description="MRZ line 1")
    mrz_line_2: Optional[str] = Field(None, description="MRZ line 2")
    image_path: Optional[str] = Field(None, description="Path to passport image")


class IDCardRecord(BaseModel):
    """Schema for an ID card database record."""
    id: int
    national_id: str
    first_name_arabic: Optional[str] = None
    middle_name_arabic: Optional[str] = None
    last_name_arabic: Optional[str] = None
    first_name_english: Optional[str] = None
    middle_name_english: Optional[str] = None
    last_name_english: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    address: Optional[str] = None
    governorate: Optional[str] = None
    issuance_date: Optional[str] = None
    expiry_date: Optional[str] = None
    front_image_path: Optional[str] = None
    back_image_path: Optional[str] = None
    created_at: Optional[str] = None


class PassportRecord(BaseModel):
    """Schema for a passport database record."""
    id: int
    passport_number: str
    first_name_arabic: Optional[str] = None
    middle_name_arabic: Optional[str] = None
    last_name_arabic: Optional[str] = None
    first_name_english: Optional[str] = None
    middle_name_english: Optional[str] = None
    last_name_english: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    passport_type: Optional[str] = None
    issuance_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    mrz_line_1: Optional[str] = None
    mrz_line_2: Optional[str] = None
    image_path: Optional[str] = None
    created_at: Optional[str] = None


class IDCardListResponse(BaseModel):
    """Response for listing ID card records."""
    success: bool = True
    count: int = 0
    records: List[IDCardRecord] = Field(default_factory=list)
    error: Optional[str] = None


class PassportListResponse(BaseModel):
    """Response for listing passport records."""
    success: bool = True
    count: int = 0
    records: List[PassportRecord] = Field(default_factory=list)
    error: Optional[str] = None


class SaveRecordResponse(BaseModel):
    """Response for save operations."""
    success: bool
    record_id: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ExportResponse(BaseModel):
    """Response for export operations."""
    success: bool
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    record_count: int = 0
    error: Optional[str] = None
# Place of Birth Validation Schemas
class PlaceOfBirthNormalized(BaseModel):
    """Normalized place of birth components."""
    district: Optional[str] = Field(None, description="Identified district")
    governorate: Optional[str] = Field(None, description="Identified governorate")


class PlaceOfBirthData(BaseModel):
    """
    Place of Birth validation result.
    
    Low-severity field - NEVER causes auto-rejection.
    At most, marks for manual review.
    """
    ocr_raw: Optional[str] = Field(None, description="Raw OCR extracted text")
    user_input: Optional[str] = Field(None, description="User-provided place of birth")
    normalized: Optional[PlaceOfBirthNormalized] = Field(
        None,
        description="Normalized governorate and district components"
    )
    ocr_confidence: float = Field(0.0, description="OCR confidence score (0-1)")
    matching_score: float = Field(
        0.0,
        description="Token matching score (0-1), weighted by governorate/district"
    )
    decision: Literal["pass", "manual_review"] = Field(
        "manual_review",
        description="Validation decision - NEVER 'reject'"
    )
    reason: Optional[str] = Field(None, description="Explanation for the decision")


# Name Matching Schemas
class NameComparison(BaseModel):
    """Result of comparing a single name (Arabic or English)."""
    ocr_normalized: str = Field(..., description="Normalized OCR name")
    user_normalized: str = Field(..., description="Normalized user name")
    exact_match: bool = Field(..., description="Whether names match exactly after normalization")
    similarity_score: float = Field(..., description="String similarity score (0-1)")
    token_overlap: float = Field(..., description="Token overlap score (0-1)")
    final_score: float = Field(..., description="Weighted final score")


class NameMatchingResult(BaseModel):
    """
    Name matching validation result.
    
    High-severity field - Low scores may cause rejection.
    """
    arabic_comparison: Optional[NameComparison] = Field(
        None,
        description="Arabic name comparison results"
    )
    english_comparison: Optional[NameComparison] = Field(
        None,
        description="English name comparison results"
    )
    combined_score: float = Field(
        0.0,
        description="Combined score from both languages"
    )
    final_score: float = Field(
        0.0,
        description="Final score after OCR confidence multiplier"
    )
    decision: Literal["pass", "manual_review", "reject"] = Field(
        "manual_review",
        description="Validation decision - MAY reject on low scores (high severity)"
    )
    reason: str = Field(..., description="Explanation for the decision")


# Field Comparison Data Models
class FieldComparisonResult(BaseModel):
    """Result of comparing a single field between OCR and manual input."""
    field_name: str = Field(..., description="Name of the field")
    severity: Literal["high", "medium", "low"] = Field(..., description="Field severity level")
    matching_type: str = Field(..., description="Matching type (exact/fuzzy/token)")
    match: bool = Field(..., description="Whether values match")
    score: float = Field(..., description="Matching score (0-1)")
    ocr_value: Optional[str] = Field(None, description="OCR value")
    user_value: Optional[str] = Field(None, description="User value")
    decision: Literal["pass", "manual_review", "reject"] = Field(..., description="Decision")
    reason: str = Field(..., description="Explanation")
    fraud_detected: Optional[bool] = Field(None, description="Fraud detection flag")
    fraud_reason: Optional[str] = Field(None, description="Fraud reason if detected")
    days_diff: Optional[int] = Field(None, description="Days difference for dates")


class FormOCRComparisonSummary(BaseModel):
    """Summary statistics."""
    total_fields: int
    passed_fields: int
    review_fields: int
    failed_fields: int


class FormOCRComparisonRequest(BaseModel):
    """Request to compare manual vs OCR data."""
    manual_data: Dict[str, Any] = Field(..., description="Manual form data")
    ocr_data: Dict[str, Any] = Field(..., description="OCR extracted data")
    ocr_confidence: float = Field(1.0, ge=0.0, le=1.0, description="OCR confidence")


class FormOCRComparisonResponse(BaseModel):
    """Response with comparison results."""
    overall_decision: Literal["approved", "manual_review", "rejected"]
    overall_score: float = Field(..., ge=0.0, le=1.0)
    field_comparisons: List[FieldComparisonResult]
    summary: FormOCRComparisonSummary
    recommendations: List[str]


# Selfie Verification Test Schemas
class SelfieVerificationResponse(BaseModel):
    """
    Response model for the /test-selfie-verification endpoint.
    
    Provides detailed face matching results for testing selfie verification
    in isolation without the full e-KYC pipeline.
    """
    success: bool = Field(
        ...,
        description="Whether the verification process completed successfully"
    )
    similarity_score: Optional[float] = Field(
        None,
        description="Face similarity score between 0.0 and 1.0"
    )
    threshold: float = Field(
        0.5,
        description="Threshold used for pass/fail decision"
    )
    decision: Literal["PASS", "FAIL", "ERROR"] = Field(
        ...,
        description="Verification decision based on threshold"
    )
    reference_face_detected: bool = Field(
        False,
        description="Whether a face was detected in the reference image"
    )
    selfie_face_detected: bool = Field(
        False,
        description="Whether a face was detected in the selfie image"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if verification failed"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "similarity_score": 0.87,
                "threshold": 0.5,
                "decision": "PASS",
                "reference_face_detected": True,
                "selfie_face_detected": True,
                "error": None
            }
        }


# =====================================================
<<<<<<< HEAD
# DOCUMENT VALIDATION (Yemen ID & Passport)
# =====================================================

class DocumentCheckResult(BaseModel):
    """Result of a single document validation check."""
    passed: bool = Field(..., description="Whether the check passed")
    score: Optional[float] = Field(None, description="Numeric score if applicable")
    threshold: Optional[float] = Field(None, description="Threshold used")
    detail: Optional[str] = Field(None, description="Short reason or detail")


class DocumentValidationResult(BaseModel):
    """Full result from Yemen ID or Passport document validation."""
    passed: bool = Field(..., description="Overall validation passed")
    document_type: str = Field(..., description="yemen_id or passport")
    checks: dict = Field(
        default_factory=dict,
        description="Per-check results: official_document, not_screenshot_or_copy, "
                    "clear_and_readable, fully_visible, not_obscured, no_extra_objects, integrity"
    )
    checks_back: Optional[dict] = Field(
        None,
        description="Yemen ID only: per-check results for back image (not_screenshot_or_copy, sharpness, fully_visible, no_extra_objects)"
    )
    error: Optional[str] = Field(None, description="Error message if validation failed")

# EXPIRY DATE CHECK SCHEMAS
# =====================================================

class ExpiryCheckRequest(BaseModel):
    """Request model for checking document expiry."""
    expiry_date: str = Field(
        ...,
        description="Document expiry date (YYYY-MM-DD or similar format)"
    )
    expiring_soon_days: int = Field(
        90,
        description="Number of days before expiry to trigger 'expiring_soon' status",
        ge=1,
        le=365
    )
    grace_period_days: int = Field(
        30,
        description="Number of days after expiry for grace period",
        ge=0,
        le=180
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "expiry_date": "2025-06-15",
                "expiring_soon_days": 90,
                "grace_period_days": 30
            }
        }


class ExpiryCheckResponse(BaseModel):
    """Response model for document expiry check."""
    is_expired: bool = Field(
        ...,
        description="Whether the document is expired"
    )
    status: Literal["valid", "expiring_soon", "expired", "unknown"] = Field(
        ...,
        description="Document expiry status"
    )
    expiry_date: Optional[str] = Field(
        None,
        description="Parsed expiry date in YYYY-MM-DD format"
    )
    days_until_expiry: Optional[int] = Field(
        None,
        description="Days until expiry (negative if expired)"
    )
    days_since_expiry: Optional[int] = Field(
        None,
        description="Days since expiry (only set if expired)"
    )
    is_within_grace_period: bool = Field(
        False,
        description="Whether within grace period after expiry"
    )
    message: str = Field(
        ...,
        description="Human-readable expiry status message"
    )
    severity: Literal["critical", "warning", "info", "none"] = Field(
        "none",
        description="Severity level for UI display"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_expired": False,
                "status": "expiring_soon",
                "expiry_date": "2026-03-15",
                "days_until_expiry": 38,
                "days_since_expiry": None,
                "is_within_grace_period": False,
                "message": "Document will expire in 38 day(s)",
                "severity": "info"
            }
        }


class DocumentDateValidationRequest(BaseModel):
    """Request model for comprehensive document date validation."""
    issuance_date: Optional[str] = Field(
        None,
        description="Document issuance date"
    )
    expiry_date: Optional[str] = Field(
        None,
        description="Document expiry date"
    )
    date_of_birth: Optional[str] = Field(
        None,
        description="Holder's date of birth"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "issuance_date": "2020-01-15",
                "expiry_date": "2030-01-15",
                "date_of_birth": "1990-05-20"
            }
        }


class DocumentDateValidationResponse(BaseModel):
    """Response model for comprehensive document date validation."""
    is_valid: bool = Field(
        ...,
        description="Overall validity of document dates"
    )
    message: str = Field(
        ...,
        description="Summary message"
    )
    expiry_check: Optional[ExpiryCheckResponse] = Field(
        None,
        description="Detailed expiry check results"
    )
    date_sequence_valid: bool = Field(
        True,
        description="Whether date sequence is valid (DOB < Issuance < Expiry)"
    )
    validity_period_days: Optional[int] = Field(
        None,
        description="Document validity period in days"
    )
    validity_period_years: Optional[float] = Field(
        None,
        description="Document validity period in years"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warning messages"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_valid": True,
                "message": "All document dates are valid",
                "expiry_check": {
                    "is_expired": False,
                    "status": "valid",
                    "expiry_date": "2030-01-15",
                    "days_until_expiry": 1439,
                    "message": "Document is valid for 1439 more day(s)"
                },
                "date_sequence_valid": True,
                "validity_period_days": 3652,
                "validity_period_years": 10.0,
                "warnings": []
            }
        }
9e4b74fc983bb56addf0508742119ae06c547b1c

