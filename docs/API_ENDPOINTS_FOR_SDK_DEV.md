# API Endpoints for SDK Integration

**Base URL:** `https://cheeriest-alysa-exilable.ngrok-free.dev`

---

## 📍 Available APIs (4 Main Endpoints)

### 1. **Full Verification** (Recommended - Most Common Use Case)
```
POST /verify
```

**What it does:** Complete ID verification - uploads ID card (front + optional back) + selfie, gets ID number and similarity score

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body:
  - `id_card_front` (file) - **Required** - ID card front side image
  - `selfie` (file) - **Required** - Selfie image
  - `id_card_back` (file) - **Optional** - ID card back side image

**Response:**
```json
{
  "success": true,
  "extracted_id": "123456789",
  "id_type": "Yemen ID",
  "similarity_score": 0.85,
  "error": null
}
```

**cURL Example (Front only):**
```bash
curl -X POST https://cheeriest-alysa-exilable.ngrok-free.dev/verify \
  -F "id_card_front=@id_front.jpg" \
  -F "selfie=@selfie.jpg"
```

**cURL Example (Front + Back):**
```bash
curl -X POST https://cheeriest-alysa-exilable.ngrok-free.dev/verify \
  -F "id_card_front=@id_front.jpg" \
  -F "id_card_back=@id_back.jpg" \
  -F "selfie=@selfie.jpg"
```

---

### 2. **Extract ID Only**
```
POST /extract-id
```

**What it does:** Extracts ID number and text from ID card (no face comparison)

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body:
  - `image` (file) - ID card image

**Response:**
```json
{
  "success": true,
  "ocr_result": {
    "extracted_id": "123456789",
    "id_type": "Yemen ID",
    "confidence": 0.95,
    "all_texts": ["text1", "text2"],
    "detected_languages": ["ar", "en"]
  },
  "error": null
}
```

**cURL Example:**
```bash
curl -X POST https://cheeriest-alysa-exilable.ngrok-free.dev/extract-id \
  -F "image=@id_card.jpg"
```

---

### 3. **Compare Faces Only**
```
POST /compare-faces
```

**What it does:** Compares two face images (no OCR)

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body:
  - `image1` (file) - First image (e.g., ID card)
  - `image2` (file) - Second image (e.g., selfie)

**Response:**
```json
{
  "success": true,
  "similarity_score": 0.82,
  "error": null
}
```

**cURL Example:**
```bash
curl -X POST https://cheeriest-alysa-exilable.ngrok-free.dev/compare-faces \
  -F "image1=@id_card.jpg" \
  -F "image2=@selfie.jpg"
```

---

### 4. **Translate Arabic Text**
```
POST /translate
```

**What it does:** Translates Arabic text to English

**Request:**
- Method: `POST`
- Content-Type: `application/json`
- Body:
```json
{
  "texts": {
    "name": "محمد علي",
    "address": "صنعاء"
  }
}
```

**Response:**
```json
{
  "success": true,
  "translations": [
    {
      "original": "محمد علي",
      "translated": "Mohammed Ali"
    },
    {
      "original": "صنعاء",
      "translated": "Sanaa"
    }
  ],
  "error": null
}
```

**cURL Example:**
```bash
curl -X POST https://cheeriest-alysa-exilable.ngrok-free.dev/translate \
  -H "Content-Type: application/json" \
  -d '{"texts": {"name": "محمد علي"}}'
```

---

## 🎯 Quick Summary

**Total APIs: 4**

| # | Endpoint | Purpose | Files Needed |
|---|----------|---------|--------------|
| 1 | `/verify` | Full verification (OCR + Face) | ID front + Selfie (+ optional back) |
| 2 | `/extract-id` | Extract ID number only | ID card |
| 3 | `/compare-faces` | Face comparison only | 2 images |
| 4 | `/translate` | Translate Arabic to English | JSON text |

---

## 💡 Recommended Workflow

**Most SDK developers only need endpoint #1:**

```
POST /verify  →  Upload ID Front + Back + Selfie  →  Get ID number + similarity score
```

This single endpoint handles everything:
- ✅ OCR extraction (from front)
- ✅ Face detection
- ✅ Face comparison
- ✅ Returns ID number and similarity score

**Note:** The `id_card_back` is **optional**. If you only have the front, that works too!

---

## 📚 Interactive Documentation

**Full API docs available at:**
```
https://cheeriest-alysa-exilable.ngrok-free.dev/docs
```

The SDK developer can test all endpoints directly in the browser using Swagger UI!

---

## ✅ Health Check

Before testing, verify the API is running:
```bash
curl https://cheeriest-alysa-exilable.ngrok-free.dev/health
```

Should return:
```json
{
  "status": "ok",
  "ocr_ready": true,
  "face_recognition_ready": true
}
```

---

## 🔑 Key Points for SDK Developer

1. **No authentication required** - Public API for testing
2. **All endpoints accept files** via `multipart/form-data` (except `/translate`)
3. **Image formats supported:** JPG, JPEG, PNG
4. **CORS enabled** - Can call from browser/mobile
5. **Response always JSON** - Check `success` field first
