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
    address: Optional[str] = Field(
        None,
        description="Address in English"
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

