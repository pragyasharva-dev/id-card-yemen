"""Configuration settings for the e-KYC system."""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
ID_CARDS_DIR = DATA_DIR / "id_cards"
SELFIES_DIR = DATA_DIR / "selfies"
PROCESSED_DIR = DATA_DIR / "processed"

# Models directory for offline deployment
# Set MODELS_DIR environment variable to override
MODELS_DIR = Path(os.environ.get("MODELS_DIR", str(BASE_DIR / "models")))
PADDLEOCR_MODEL_DIR = MODELS_DIR / "paddleocr"
INSIGHTFACE_MODEL_DIR = MODELS_DIR / "insightface"

# Persistence settings - No Persistence mode
# Set to False to disable saving images to disk/database
PERSIST_IMAGES = os.environ.get("PERSIST_IMAGES", "true").lower() == "true"

# API Security (API Key Authentication)
# Comma-separated list of valid API keys. If empty, auth is disabled.
API_KEYS = [k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()]

# Logging configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_JSON_FORMAT = os.environ.get("LOG_JSON_FORMAT", "true").lower() == "true"

# Ensure directories exist
for dir_path in [ID_CARDS_DIR, SELFIES_DIR, PROCESSED_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


# ID Type Patterns - Used for intelligent ID detection
# Format: (pattern_name, regex_pattern, description)
ID_PATTERNS = {
    # Indian IDs - commented out
    # "aadhaar": {
    #     "pattern": r"^\d{12}$",
    #     "description": "12-digit numeric Aadhaar number",
    #     "length": 12,
    #     "type": "numeric"
    # },
    # "pan": {
    #     "pattern": r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    #     "description": "10-character alphanumeric PAN (AAAAA9999A)",
    #     "length": 10,
    #     "type": "alphanumeric"
    # },
    "yemen_id": {
        "pattern": r"^\d{11}$",
        "description": "11-digit numeric Yemen ID",
        "length": 11,
        "type": "numeric"
    },
    # "passport": {
    #     "pattern": r"^[A-Z][0-9]{7}$",
    #     "description": "Indian passport format (A1234567)",
    #     "length": 8,
    #     "type": "alphanumeric"
    # },
    # "voter_id": {
    #     "pattern": r"^[A-Z]{3}[0-9]{7}$",
    #     "description": "Indian Voter ID (AAA1234567)",
    #     "length": 10,
    #     "type": "alphanumeric"
    # },
    # "driving_license": {
    #     "pattern": r"^[A-Z]{2}[0-9]{2}[0-9]{11}$",
    #     "description": "Indian Driving License format",
    #     "length": 15,
    #     "type": "alphanumeric"
    # }
}


OCR_CONFIDENCE_THRESHOLD = 0.7

# Face Recognition Settings
FACE_DETECTION_MODEL = "buffalo_l"  # InsightFace model
FACE_DETECTION_CTX = 0  # GPU context, -1 for CPU

# Image Processing Settings
SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]
MAX_IMAGE_SIZE = (2000, 2000)  # Maximum dimensions for processing

# Liveness Detection Settings (Passive Anti-Spoofing - STRICT MODE)
# All thresholds are normalized to 0-1 range (percentage / 100)
LIVENESS_ENABLED = True  # Enable/disable liveness checks
LIVENESS_TEXTURE_THRESHOLD = 0.08  # 8% - Texture variance
LIVENESS_COLOR_THRESHOLD = 0.35  # 35% - Skin tone detection
LIVENESS_SHARPNESS_THRESHOLD = 0.02  # 2% - Image sharpness
LIVENESS_MOIRE_THRESHOLD = 0.20  # 20% - Moiré/reflection detection
LIVENESS_ML_THRESHOLD = 0.70  # 70% - ML model confidence
LIVENESS_SIZE_THRESHOLD = 0.20  # 20% - Minimum image size
LIVENESS_THRESHOLD = 0.5  # Overall liveness confidence threshold (0-1)

# Face Quality Check Settings (for ID card and selfie validation)
FACE_QUALITY_ENABLED = True  # Enable/disable face quality checks
FACE_QUALITY_MIN_LANDMARKS = 3  # Minimum visible landmarks (eyes, nose, mouth)
FACE_QUALITY_MIN_CONFIDENCE = 0.5  # Minimum face detection confidence
FACE_QUALITY_MIN_FACE_RATIO = 0.02  # Minimum face area ratio in image (2%)

# Document Validation (Yemen ID and Passport services)
DOC_VALIDATION_ENABLED = True
DOC_MIN_SHARPNESS = 0.04  # Laplacian variance (normalized), reject blurry/soft copies
# OCR confidence thresholds (not used in document validation; kept for other flows if needed)
DOC_MIN_OCR_CONFIDENCE = 0.55
DOC_MIN_RESOLUTION_PX = 320  # Minimum side length in pixels
DOC_MIN_MARGIN_RATIO = 0.005  # Min margin (0.5%); allow card to fill frame in live capture
DOC_MIN_COVERAGE_RATIO = 0.5  # Document must occupy ≥ 50% of image
DOC_ASPECT_RATIO_YEMEN_ID = (1.3, 1.8)  # (min, max) width/height for Yemen ID front
DOC_ASPECT_RATIO_YEMEN_ID_BACK = (1.0, 2.0)  # Wider for back (QR/text layout, different framing)
DOC_ASPECT_RATIO_PASSPORT = (0.6, 1.7)  # (min, max) width/height - allow portrait or landscape
DOC_MOIRE_THRESHOLD = 0.30  # Above this = less moiré (good); allow originals ~0.31; screen photos often lower
DOC_MOIRE_THRESHOLD_BACK = 0.25  # More lenient for ID back (barcode/QR can cause subtle moiré on originals)
DOC_MOIRE_THRESHOLD_PASSPORT = 0.33  # Above this = less moiré (good); originals ~0.34; screen captures often lower; combined with screen_grid for borderline
DOC_SCREEN_GRID_MAX = 0.55  # FFT grid score above this = photo of screen; scoring tuned so originals stay below
DOC_SCREEN_GRID_MAX_BACK = 0.65  # More lenient for ID back (dense barcode can add periodic structure)
DOC_SCREEN_GRID_MAX_PASSPORT = 0.52  # Reject screen_grid >= 0.52 (catches screen captures ~0.53); originals ~0.51 pass
# Passport: reject borderline moiré + medium screen_grid (screen-capture pattern); originals have higher screen_grid
DOC_PASSPORT_MOIRE_BORDERLINE_MIN = 0.33
DOC_PASSPORT_MOIRE_BORDERLINE_MAX = 0.36
DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MIN = 0.38
DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MAX = 0.50
DOC_MIN_SHARPNESS_PASSPORT = 0.09  # Reject soft/color copies (0.085); originals typically sharper
DOC_HALFTONE_MAX_PASSPORT = 0.28  # Stricter for passport: reject printed copies (halftone dots)
DOC_TEXTURE_THRESHOLD = 0.08  # LBP variance, photocopies tend lower
DOC_TEXTURE_MAX = 1.0  # Cap at 1.0; originals with security printing/holograms can score 1.0
DOC_HALFTONE_MAX = 0.35  # FFT halftone score above this = suspected print/copy, reject
# When texture is high (>= this), require mean saturation >= DOC_MIN_SATURATION_FOR_HIGH_TEXTURE
DOC_HIGH_TEXTURE_THRESHOLD = 0.92
DOC_MIN_SATURATION_FOR_HIGH_TEXTURE = 0.06  # Reject only very flat prints; originals can be muted (lighting/passport design)




# Place of Birth Validation Thresholds
PLACE_OF_BIRTH_PASS_THRESHOLD = 0.8
PLACE_OF_BIRTH_MANUAL_THRESHOLD = 0.4

# Date Comparison Tolerance (Days)
DATE_TOLERANCE_DAYS = 1

# Field Validation Configuration
SEVERITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.2
}

FIELD_CONFIGURATIONS = {
    "id_number": {
        "severity": "high",
        "matching_type": "exact",
        "pass_threshold": 1.0,
        "manual_threshold": 1.0,
        "enabled": True
    },
    "passport_number": {
        "severity": "high",
        "matching_type": "exact",
        "pass_threshold": 1.0,
        "manual_threshold": 1.0,
        "enabled": True
    },
    "date_of_birth": {
        "severity": "high",
        "matching_type": "exact",
        "pass_threshold": 1.0,
        "manual_threshold": 1.0,
        "enabled": True
    },
    "name_english": {
        "severity": "high",
        "matching_type": "fuzzy",
        "pass_threshold": 0.85,
        "manual_threshold": 0.60,
        "enabled": True
    },
    "name_arabic": {
        "severity": "high",
        "matching_type": "fuzzy",
        "pass_threshold": 0.85,
        "manual_threshold": 0.60,
        "enabled": True
    },
    "issuance_date": {
        "severity": "medium",
        "matching_type": "exact",  # with tolerance logic in code
        "pass_threshold": 1.0,
        "manual_threshold": 0.5,
        "enabled": True
    },
    "expiry_date": {
        "severity": "medium",
        "matching_type": "exact",  # with tolerance logic in code
        "pass_threshold": 1.0,
        "manual_threshold": 0.5,
        "enabled": True
    },
    "gender": {
        "severity": "medium",
        "matching_type": "exact",
        "pass_threshold": 1.0,
        "manual_threshold": 1.0,
        "enabled": True
    },
    "place_of_birth": {
        "severity": "medium",
        "matching_type": "token",
        "pass_threshold": PLACE_OF_BIRTH_PASS_THRESHOLD,
        "manual_threshold": PLACE_OF_BIRTH_MANUAL_THRESHOLD,
        "enabled": True
    },
    "nationality": {
        "severity": "low",
        "matching_type": "fuzzy",
        "pass_threshold": 0.80,
        "manual_threshold": 0.50,
        "enabled": True
    },
    "profession": {
        "severity": "low",
        "matching_type": "fuzzy",
        "pass_threshold": 0.75,
        "manual_threshold": 0.40,
        "enabled": True
    },
    "issuance_place": {
        "severity": "low",
        "matching_type": "fuzzy",
        "pass_threshold": 0.75,
        "manual_threshold": 0.40,
        "enabled": True
    }
}
