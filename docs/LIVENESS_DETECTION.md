# Liveness Detection System Documentation

## Overview

This document describes the passive liveness detection system integrated into the eKYC verification flow. The system analyzes selfie images to detect spoof attacks (photos, screens, prints) and ensure the user is a live, physically present person.

**Version 2 Optimizations:**
- Fast LBP using skimage (vectorized, 10x faster)
- Color analysis applied to face ROI only
- Sharpness normalized by image size (device-independent)
- FFT with Hann window (noise reduction)
- Weighted voting instead of equal voting

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
│   │  1. Image Size Check                                │   │
│   │  2. Texture Analysis (LBP)                          │   │
│   │  3. Color Analysis (HSV)                            │   │
│   │  4. Sharpness Check (Laplacian)                     │   │
│   │  5. Moiré Detection (FFT)                           │   │
│   │  6. ML Model (Enhanced Fallback)                    │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               SAME-SOURCE CHECK                             │
│   Similarity > 95% → HARD FAIL (ID card crop detected)      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  FINAL DECISION                             │
│   Confidence ≥ 60% → PASS | Otherwise → WARNING             │
└─────────────────────────────────────────────────────────────┘
```

---

## Detection Techniques

### 1. Sharpness Analysis (Laplacian Variance)
- **Purpose:** Detect blurry images typical of printed photos or screen captures
- **Method:** Calculate Laplacian variance of grayscale image
- **Threshold:** > 100.0
- **Spoof Indicator:** Low sharpness → likely spoof

### 2. Texture Analysis (Local Binary Patterns)
- **Purpose:** Detect flat or artificial surfaces lacking skin micro-texture
- **Method:** LBP variance calculation
- **Threshold:** > 50.0
- **Spoof Indicator:** Low texture score → printed or replay attack

### 3. Color Distribution (HSV Analysis)
- **Purpose:** Detect limited color range typical of screens/prints
- **Method:** Analyze skin tone ratio in HSV color space
- **Threshold:** > 0.3 (30% skin tone)
- **Spoof Indicator:** Low saturation variance → spoof

### 4. Moiré Pattern Detection (FFT)
- **Purpose:** Detect interference patterns from screen captures
- **Method:** FFT frequency analysis on mid-frequency bands
- **Threshold:** > 0.15
- **Spoof Indicator:** High moiré energy → screen replay

### 5. ML-Based Anti-Spoofing
- **Purpose:** Combined analysis using multiple image features
- **Method:** Enhanced fallback with 4 sub-techniques:
  - Laplacian sharpness
  - High-frequency content (FFT)
  - Edge density (Canny)
  - Color saturation variance
- **Threshold:** spoof_probability < 0.5

### 6. Same-Source Detection
- **Purpose:** Detect if selfie is cropped from ID card
- **Method:** Face embedding similarity comparison
- **Threshold:** 95%
- **Effect:** **HARD FAIL** - Overrides all other checks

---

## Configuration Parameters

```json
{
  "liveness_detection": {
    "enabled": true,
    "overall_threshold": 0.6,
    "checks": {
      "image_size": {
        "min_dimension": 100,
        "unit": "pixels"
      },
      "texture": {
        "threshold": 50.0,
        "method": "LBP_variance"
      },
      "color": {
        "threshold": 0.3,
        "method": "skin_tone_ratio"
      },
      "sharpness": {
        "threshold": 100.0,
        "method": "laplacian_variance"
      },
      "moire": {
        "threshold": 0.15,
        "method": "FFT_analysis"
      },
      "ml_model": {
        "threshold": 0.5,
        "method": "enhanced_fallback"
      }
    },
    "same_source": {
      "threshold": 0.95,
      "effect": "hard_fail"
    }
  }
}
```

---

## Decision Logic

1. **Run all 6 checks** on the selfie image
2. **Calculate confidence:** `passed_checks / total_checks`
3. **Apply same-source override:** If face similarity > 95%, force FAIL
4. **Final decision:**
   - Confidence ≥ 60% → **PASS**
   - Confidence < 60% → **WARNING**

---

## API Response Format

```json
{
  "liveness": {
    "is_live": true,
    "confidence": 0.833,
    "spoof_probability": 0.167,
    "checks": {
      "image_size": {"passed": true, "score": 640, "threshold": 100},
      "texture": {"passed": true, "score": 1250.5, "threshold": 50.0},
      "color": {"passed": true, "score": 0.45, "threshold": 0.3},
      "sharpness": {"passed": true, "score": 850.2, "threshold": 100.0},
      "reflection": {"passed": false, "score": 0.12, "threshold": 0.15},
      "ml_model": {"passed": true, "score": 0.72, "threshold": 0.5}
    },
    "error": null
  }
}
```

---

## Files

| File | Purpose |
|------|---------|
| `services/liveness_service.py` | Core liveness detection logic |
| `services/antispoof_model.py` | ML-based anti-spoofing model |
| `services/face_recognition.py` | Same-source detection |
| `utils/config.py` | Configuration parameters |
| `models/schemas.py` | API response schemas |

---

## Non-Blocking Behavior

The liveness detection is **non-blocking**:
- Verification continues even if liveness fails
- Results are returned as warnings
- Frontend displays liveness status with confidence
- Business logic can decide how to handle warnings

---

## Version
- **Implementation Date:** January 2026
- **Last Updated:** January 23, 2026
