# AI Agent Context Documentation

> [!IMPORTANT]
> **MAINTENANCE INSTRUCTION**: If you make MAJOR changes to the codebase (architecture, new services, significant refactoring), you **MUST** update this file to keep it accurate.
>
> **CRITICAL**: BEFORE updating this file, you **MUST ASK THE USER FOR PERMISSION**. Do not auto-update this file without explicit consent.

## 1. Project Overview
**Name**: e-KYC Verification System
**Goal**: Verify customer identity by comparing ID card images with selfies.
**Core Features**:
- **ID Layout**: YOLO v8 for field detection (Front/Back models).
- **ID Extraction**: PaddleOCR on cropped fields.
- **Face Verification**: InsightFace (Buffalo_L) for face comparison and liveness detection.
- **Translation**: Hybrid Arabic-to-English name translation.
- **Validation**: Configurable strictness (Low/Medium/High severity fields).
- **Database**: SQLite storage for ID cards, passports, and verification records.

## 2. Architecture

```mermaid
graph TD
    User[User/Client] --> API[FastAPI Router]
    
    subgraph Routes [API Routes]
        API --> Health[Health]
        API --> OCR_API[OCR]
        API --> Verify[Verification]
        API --> Quality[Quality & Liveness]
        API --> DB_API[Database CRUD]
    end
    
    subgraph Services
        OCR_API --> OCR[OCR Service]
        Verify --> Face[Face Recognition]
        Verify --> ID_DB[ID Database Service]
        Quality --> IQS[Image Quality Service]
        Quality --> Liveness[Liveness Service]
        OCR_API --> Parser[ID Parser]
        OCR_API --> Trans[Translation Service]
        DB_API --> DB[Database Service]
    end
    
    subgraph Core Logic
        OCR --> Paddle[PaddleOCR]
        Face --> Insight[InsightFace]
        Liveness --> Spoof[Anti-Spoofing]
        Trans --> Hybrid[Hybrid Pipeline]
        DB --> SQLite[(SQLite DB)]
    end
    
    Services --> Utils[Utilities]
```

## 3. Directory Structure
- **`api/`**: FastAPI application.
    - **`routes/`**: Modular route handlers.
        - `verification.py`: Core e-KYC verification endpoints.
        - `ocr.py`: ID extraction and parsing.
        - `quality.py`: Image quality and liveness checks.
        - `database.py`: CRUD operations for ID/passport records.
        - `health.py`, `face.py`, `translation.py`.
    - `test_routes.py`: Endpoints for testing and debugging.
- **`services/`**: Core business logic.
    - `layout_service.py`: YOLO-based field detection (Reduces need for NER).
    - `ocr_service.py`: Text extraction & ID pattern matching.
    - `face_recognition.py`: Face detection & comparison.
    - `id_database.py`: **NEW** - ID card retrieval logic for verification.
    - `database.py`: SQLite database abstraction.
    - `image_quality_service.py`: Face visibility validation.
    - `liveness_service.py`: Passive anti-spoofing checks.
    - `translation_service.py`: Hybrid translation logic.
    - `id_card_parser.py`: Structured data parsing from OCR text.
- **`models/`**: Pydantic schemas (`schemas.py`) and validators.
- **`utils/`**: Shared utilities.
    - `date_utils.py`: **Core** - Centralized date parsing/formatting (YYYY-MM-DD).
    - `config.py`: **CRITICAL** - contains severity thresholds and ID patterns.
    - `ocr_utils.py`: Preprocessing and text normalization.
- **`data/`**: Local storage for images and SQLite databases.

## 4. Key Engineering Concepts

### A. OCR & Language Detection (`services/ocr_service.py`)
- Uses **PaddleOCR**.
- **Strict Validation**: For non-English models (Arabic), outputs are rejected if they don't contain native script characters.
- **Multilingual**: Detects language per text block.

### B. Hybrid Translation (`services/translation_service.py`)
Pipeline for Arabic-to-English names:
1.  **Dictionary Lookup**: Exact match from `utils/name_dictionary.py`.
2.  **Phonetic Mapping**: Char-by-char transliteration.
3.  **Metaphone Correction**: Uses Double Metaphone to "snap" phonetic output to valid English names.

### C. Validation Severity (`utils/config.py`)
Fields have severity levels determining verification outcome:
- **High** (ID #, Name, DOB): Failure = **REJECT**.
- **Medium** (Dates): Failure = **MANUAL_REVIEW**.
- **Low** (Place of Birth): Failure = **MANUAL_REVIEW** (never rejects).

### D. Modular API Design
- Routes are split by domain in `api/routes/`.
- `main.py` aggregates them via a single router.
- **Verification Flow**: `/verify` endpoint performs OCR, parses data, runs face comparison (with optional liveness), and auto-saves results to the database.

### E. Date Normalization (`utils/date_utils.py`)
- **Single Source of Truth**: All dates are forced to `YYYY-MM-DD`.
- **Robust Parsing**: Handles `DD-MM-YYYY`, `YYYY/MM/DD`, etc.
- **Integrated Services**: Used by `id_card_parser`, `passport_mrz_parser`, and `expiry_date_service`.

## 5. Agent Guidelines
- **Running Tests**: Check `docs/TESTING_GUIDE.md`. Preferred script: `python tests/test_verify_enhanced.py`.
- **Config**: Do not hardcode thresholds. Use `utils.config`.
- **New IDs**: Add patterns to `ID_PATTERNS` in `utils/config.py`.
- **Imports**: When importing services, ensure the module exists (e.g., `services.id_database`).
