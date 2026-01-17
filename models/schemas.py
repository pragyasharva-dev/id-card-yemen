"""
Pydantic models for API request/response schemas.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


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


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    ocr_ready: bool = False
    face_recognition_ready: bool = False


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

