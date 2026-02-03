# Image Quality Service Documentation

The Image Quality Service validates that faces in ID cards/passports and selfies are clearly visible and not obscured before the e-KYC verification process begins.

## Overview

This service acts as a **pre-verification gate** to ensure input images are usable for facial recognition and identity verification.

### Key Features
- Face detection and landmark analysis using InsightFace
- Occlusion detection (masks, niqabs, hands, etc.)
- Support for diverse skin tones
- Separate validation rules for ID cards vs selfies

---

## API Endpoints

### Check ID Card Quality
```
POST /check-id-quality
```
Validates the face photo on an ID card or passport.

### Check Selfie Quality  
```
POST /check-selfie-quality
```
Validates that a selfie shows a clearly visible, uncovered face.

---

## Requirements

### For Selfies

| Requirement | Description |
|-------------|-------------|
| Face Detection | A face must be detected in the image |
| Eyes Visible | Both eyes must be clearly visible |
| Nose Visible | Nose must be clearly visible |
| Mouth Visible | Mouth must be clearly visible |
| No Occlusion | Face must not be covered by masks, niqab, or other objects |
| Face Size | Face must occupy at least 2% of the image area |
| Detection Confidence | Minimum 50% face detection confidence |
| Minimum Landmarks | At least 3 out of 5 facial landmarks must be visible |

### For ID Cards/Passports

| Requirement | Description |
|-------------|-------------|
| Face Detection | A face must be detected on the document |
| Eyes Visible | Both eyes must be clearly visible |
| Nose Visible | Nose must be clearly visible |
| Mouth Visible | Mouth must be clearly visible |
| No Occlusion | Photo on ID must not be obscured or damaged |
| Face Size | **Not required** (skipped for ID cards) |
| Detection Confidence | Minimum 50% face detection confidence |

---

## Configuration Thresholds

These thresholds are defined in `utils/config.py`:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `FACE_QUALITY_ENABLED` | `True` | Enable/disable quality checks |
| `FACE_QUALITY_MIN_LANDMARKS` | `3` | Minimum visible landmarks (out of 5) |
| `FACE_QUALITY_MIN_CONFIDENCE` | `0.5` | Minimum detection confidence (50%) |
| `FACE_QUALITY_MIN_FACE_RATIO` | `0.02` | Minimum face area ratio (2%) - selfies only |

---

## Internal Detection Thresholds

### Occlusion Detection (Nose/Mouth)

| Check | Condition | Meaning |
|-------|-----------|---------|
| Black fabric | `skin_ratio < 0.10` AND `brightness < 50` | Detects black niqabs/masks |
| Low skin + dark | `skin_ratio < 0.15` AND `brightness < 70` | Covered by dark object |

### Eye Detection

| Check | Threshold | Meaning |
|-------|-----------|---------|
| Variance | `< 30` | Too uniform = likely covered |

### Skin Color Detection (HSV Ranges)

| Skin Tone | Hue | Saturation | Value |
|-----------|-----|------------|-------|
| Light-medium | 0-25 | 15-255 | 60-255 |
| Dark | 0-35 | 10-180 | 30-200 |
| Very dark | 0-40 | 5-150 | 20-150 |

---

## Response Format

```json
{
  "passed": true/false,
  "face_detected": true/false,
  "face_visible": true/false,
  "quality_score": 0.0-1.0,
  "error": "Error message if failed",
  "details": {
    "eyes_visible": true/false,
    "nose_visible": true/false,
    "mouth_visible": true/false,
    "face_area_ratio": 0.0-1.0,
    "landmark_confidence": 0.0-1.0,
    "landmarks_detected": 0-5,
    "occlusion_detected": true/false
  }
}
```

---

## Quality Score Calculation

The quality score (0.0-1.0) is a weighted average:

| Component | Weight | Calculation |
|-----------|--------|-------------|
| Landmark Score | 40% | `landmarks_detected / 5` |
| Confidence Score | 30% | `detection_confidence` |
| Face Ratio Score | 30% | `face_ratio / 0.15` (capped at 1.0) |

---

## Rejection Reasons

Images are **REJECTED** if:

1. **No face detected** in the image
2. **Face is covered** by niqab, mask, scarf, hands, or other objects
3. **Eyes are not visible** (sunglasses, looking away)
4. **Nose or mouth is covered** (face covering, mask)
5. **Image is too blurry** (low detection confidence < 50%)
6. **Selfie face is too small** (less than 2% of image area)

---

## Error Messages

| Condition | ID Card Message | Selfie Message |
|-----------|-----------------|----------------|
| No face | "No face detected on ID card..." | "No face detected in selfie..." |
| Covered | "Face is partially covered...on ID card..." | "Face is partially covered..." |
| Unclear | "Face on ID card is unclear..." | "Face is not clearly visible..." |
| Too small | N/A | "Face is too small...come closer..." |
| Features hidden | "Cannot see eyes, nose, or mouth...on ID card..." | "Cannot see your eyes, nose, or mouth..." |

---

## Usage Example

### Python
```python
from services.image_quality_service import check_id_quality, check_selfie_quality
import cv2

# Load image
image = cv2.imread("path/to/image.jpg")

# Check ID card quality
result = check_id_quality(image)
print(f"Passed: {result['passed']}")

# Check selfie quality
result = check_selfie_quality(image)
print(f"Passed: {result['passed']}")
```

### API (cURL)
```bash
# Check ID card
curl -X POST "http://localhost:8000/check-id-quality" \
  -F "id_card=@path/to/id_card.jpg"

# Check selfie
curl -X POST "http://localhost:8000/check-selfie-quality" \
  -F "selfie=@path/to/selfie.jpg"
```

---

## Dependencies

- **InsightFace** (`buffalo_l` model) - Face detection and landmark extraction
- **OpenCV** - Image processing
- **NumPy** - Numerical operations

---

## Files

| File | Purpose |
|------|---------|
| `services/image_quality_service.py` | Main service implementation |
| `utils/config.py` | Configuration thresholds |
| `services/face_extractor.py` | InsightFace wrapper for face detection |
