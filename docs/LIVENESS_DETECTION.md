# Liveness Detection System Documentation

## Overview

This document describes the passive liveness detection system integrated into the eKYC verification flow. The system analyzes selfie images to detect spoof attacks (photos, screens, prints) and ensure the user is a live, physically present person.

**Current Implementation:**
- Strict mode: ALL checks must pass
- Normalized scores: 0-1 range for all checks
- ML Model: MiniFASNetV2SE ONNX model
- Configurable thresholds via `config.py`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SELFIE IMAGE                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  LIVENESS SERVICE                           │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  1. Image Size Check (min 160px)                    │   │
│   │  2. Texture Analysis (LBP variance)                 │   │
│   │  3. Color Analysis (skin tone ratio)                │   │
│   │  4. Sharpness Check (Laplacian variance)            │   │
│   │  5. Moiré Pattern Detection (FFT)                   │   │
│   │  6. ML Model (MiniFASNetV2SE)                       │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  STRICT MODE DECISION                       │
│          ALL 6 checks must pass → LIVE                      │
│          ANY check fails → SPOOF                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Detection Techniques

### 1. Image Size Check
- **Purpose:** Ensure image quality is sufficient for analysis
- **Method:** Check minimum dimension
- **Threshold:** > 20% (160px of 800px max)
- **Score:** `min(dimension, 800) / 800`

### 2. Texture Analysis (LBP)
- **Purpose:** Detect flat surfaces lacking skin micro-texture
- **Method:** Local Binary Pattern variance
- **Threshold:** > 8%
- **Score:** `min(lbp_variance, 20) / 20`
- **Spoof Indicator:** Low score = printed/screen attack

### 3. Color Distribution
- **Purpose:** Detect limited color range of screens/prints
- **Method:** Skin tone ratio in HSV color space
- **Threshold:** > 35%
- **Score:** Already 0-1 (skin ratio)
- **Spoof Indicator:** Low skin ratio = artificial image

### 4. Sharpness Analysis
- **Purpose:** Detect blurry images from prints/captures
- **Method:** Laplacian variance
- **Threshold:** > 2%
- **Score:** `min(laplacian_var, 100) / 100`
- **Spoof Indicator:** Low sharpness = print/screen

### 5. Moiré Pattern Detection
- **Purpose:** Detect interference patterns from screens
- **Method:** FFT frequency analysis
- **Threshold:** > 20%
- **Score:** Already 0-1 (moiré energy)
- **Spoof Indicator:** High moiré = screen replay

### 6. ML-Based Anti-Spoofing
- **Purpose:** Deep learning spoof detection
- **Model:** MiniFASNetV2SE (ONNX, 128x128 input)
- **Threshold:** > 70%
- **Score:** `1.0 - spoof_probability`
- **Location:** `models/antispoof/best_model_quantized.onnx`

---

## Configuration

All thresholds are in `utils/config.py`:

```python
# Liveness Detection Settings (STRICT MODE)
# All thresholds are normalized to 0-1 range
LIVENESS_ENABLED = True
LIVENESS_TEXTURE_THRESHOLD = 0.08   # 8%
LIVENESS_COLOR_THRESHOLD = 0.35    # 35%
LIVENESS_SHARPNESS_THRESHOLD = 0.02 # 2%
LIVENESS_MOIRE_THRESHOLD = 0.20    # 20%
LIVENESS_ML_THRESHOLD = 0.70       # 70%
LIVENESS_SIZE_THRESHOLD = 0.20     # 20%
```

---

## Decision Logic

```
1. Run all 6 checks on selfie image
2. Each check returns: passed (bool), score (0-1), threshold (0-1)
3. STRICT MODE: ALL checks must pass
4. If ANY check fails → is_live = false
5. Confidence = passed_count / total_checks
```

---

## API Response Format

```json
{
  "is_live": true,
  "confidence": 1.0,
  "spoof_probability": 0.0,
  "checks": {
    "image_size": {
      "passed": true,
      "score": 0.84,
      "threshold": 0.2,
      "raw_score": 672
    },
    "texture": {
      "passed": true,
      "score": 0.42,
      "threshold": 0.08,
      "raw_score": 8.4
    },
    "color": {
      "passed": true,
      "score": 1.0,
      "threshold": 0.35
    },
    "sharpness": {
      "passed": true,
      "score": 0.72,
      "threshold": 0.02,
      "raw_score": 72.1
    },
    "moire_pattern": {
      "passed": true,
      "score": 0.32,
      "threshold": 0.2
    },
    "ml_model": {
      "passed": true,
      "score": 0.94,
      "threshold": 0.7,
      "model": "best_model_quantized.onnx"
    }
  },
  "error": null
}
```

---

## Files

| File | Purpose |
|------|---------|
| `services/liveness_service.py` | Core detection logic (6 checks) |
| `services/antispoof_model.py` | ML model wrapper (MiniFASNetV2SE) |
| `utils/config.py` | All thresholds and settings |
| `models/antispoof/best_model_quantized.onnx` | ONNX model file |

---

## Limitations

This passive liveness system **can detect:**
- Low-quality printed photos
- Blurry/compressed images
- Screen displays with moiré patterns
- Obvious spoof attempts

This system **cannot reliably detect:**
- High-quality printed photos
- HD screens without moiré
- 3D masks
- Deepfakes/AI-generated faces
- Video replays

For higher security, consider active liveness (blink/smile detection) with video input.

---

## Version
- **Implementation Date:** January 2026
- **Last Updated:** February 2, 2026
- **ML Model:** MiniFASNetV2SE (ONNX, quantized)
