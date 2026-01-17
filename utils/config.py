"""
Configuration settings for the e-KYC system.
"""
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
ID_CARDS_DIR = DATA_DIR / "id_cards"
SELFIES_DIR = DATA_DIR / "selfies"
PROCESSED_DIR = DATA_DIR / "processed"

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
    "yemen_passport": {
        "pattern": r"^\d{8}$",
        "description": "8-digit numeric Yemen Passport",
        "length": 8,
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

# Place of Birth Validation Settings
# Low-severity, non-blocking field - NEVER auto-rejects
PLACE_OF_BIRTH_ENABLED = True
PLACE_OF_BIRTH_PASS_THRESHOLD = 0.70  # Score >= 0.70 → pass
PLACE_OF_BIRTH_MANUAL_THRESHOLD = 0.40  # Score < 0.70 → manual review
# NOTE: No reject threshold - this field NEVER causes auto-rejection
