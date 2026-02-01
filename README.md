# e-KYC Verification System

A modular e-KYC (electronic Know Your Customer) verification system that compares facial images from ID cards with selfies to verify customer identity.

## Features

- **Intelligent ID Extraction**: Uses OCR with pattern matching to detect and extract unique IDs from various card types:
  - Aadhaar (12-digit numeric)
  - PAN Card (10-character alphanumeric)
  - Yemen ID (11-digit numeric)
  - Passport (8-character alphanumeric)
  - Voter ID (10-character alphanumeric)
  - Driving License (15-character alphanumeric)

- **Face Extraction**: Detects and extracts faces from ID card images using InsightFace

- **Face Comparison**: Compares ID card face with selfie using cosine similarity on face embeddings

- **RESTful API**: FastAPI-based endpoints for easy integration

## Project Structure

```
id-card-yemen/
├── api/
│   ├── __init__.py
│   └── routes.py              # FastAPI endpoints
├── models/
│   ├── __init__.py
│   └── schemas.py             # Pydantic request/response models
├── services/
│   ├── __init__.py
│   ├── ocr_service.py         # OCR for ID number extraction
│   ├── face_extractor.py      # Face detection using InsightFace
│   └── face_recognition.py    # Face comparison
├── utils/
│   ├── __init__.py
│   ├── config.py              # Configuration constants
│   └── image_manager.py       # Image utilities
├── data/
│   ├── id_cards/              # Place ID card images here
│   ├── selfies/               # Place selfie images here
│   └── processed/             # Processed images (auto-generated)
├── main.py                    # FastAPI application entry
└── pyproject.toml             # Dependencies
```

## Installation

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # or
   source .venv/bin/activate  # Linux/Mac
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   # or with uv
   uv sync
   ```

## Usage

### Start the API Server

```bash
uvicorn main:app --reload
```

Access the API documentation at: http://localhost:8000/docs

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/verify` | POST | Full e-KYC verification (OCR + Face Match) |
| `/verify-json` | POST | Verification using JSON body with paths |
| `/extract-id` | POST | Extract ID number from ID card |
| `/compare-faces` | POST | Compare two face images |
| `/process-batch` | POST | Batch process ID cards |
| `/health` | GET | Health check |

### Example: Verify Identity

Using curl:
```bash
curl -X POST "http://localhost:8000/verify" \
  -F "id_card=@data/id_cards/sample_01.png" \
  -F "selfie=@data/selfies/sample_01.png"
```

Response:
```json
{
  "success": true,
  "extracted_id": "123456789012",
  "id_type": "aadhaar",
  "similarity_score": 0.85,
  "error": null
}
```

### Example: Extract ID Only

```bash
curl -X POST "http://localhost:8000/extract-id" \
  -F "image=@data/id_cards/sample_01.png"
```

## Testing

1. Place your ID card images in `data/id_cards/`
2. Place corresponding selfies in `data/selfies/`
3. Start the server and use the Swagger UI at `/docs` to test

## Architecture

```
Request → FastAPI Router → Services → Utils
                ↓
         ┌──────────────┐
         │ OCR Service  │ → Extract ID using PaddleOCR
         └──────────────┘
                ↓
         ┌──────────────────┐
         │ Face Extractor   │ → Detect face using InsightFace
         └──────────────────┘
                ↓
         ┌──────────────────┐
         │ Face Recognition │ → Compare embeddings (cosine similarity)
         └──────────────────┘
                ↓
         Response (similarity_score: 0.0 - 1.0)
```

## License

MIT

## For AI Agents

See [CONTEXT.md](CONTEXT.md) for detailed architectural context, design patterns, and maintenance instructions.
