# 🧪 API Testing Guide

## Quick Start

### Step 1: Install Dependencies
```bash
# Install Python packages
uv sync

# Install spaCy language models for NER (optional but recommended)
python -m spacy download xx_ent_wiki_sm  # Multilingual (Arabic)
python -m spacy download en_core_web_sm  # English
```

### Step 2: Start the API Server
```bash
# Start the server
uvicorn main:app --reload --port 8000

# Or with explicit host binding
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Wait for the server to start. You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 3: Test the API

## 🎯 Testing Methods

### Method 1: Python Test Script (Recommended)

**Enhanced Test Script with Full Output:**
```bash
python test_verify_enhanced.py <id_front.jpg> <selfie.jpg> [id_back.jpg]
```

**Examples:**
```bash
# Test with front ID only
python test_verify_enhanced.py data/id_cards/yemen_id.jpg data/selfies/person.jpg

# Test with front and back ID
python test_verify_enhanced.py data/id_cards/front.jpg data/selfies/person.jpg data/id_cards/back.jpg
```

**Expected Output:**
```
============================================================
  Health Check
============================================================
  Status                ✓ ok
  OCR Ready            ✓
  Face Recognition     ✓

============================================================
  e-KYC Verification Test
============================================================

  Files:
    ID Front : data/id_cards/front.jpg
    Selfie   : data/selfies/person.jpg

============================================================
  Identity Information
============================================================
  ID Number            123456789012
  ID Type              yemen_id

============================================================
  Personal Details
============================================================
  Name (Arabic)        أحمد محمد علي
  Name (English)       Ahmed Mohammed Ali
  Date of Birth        1990-05-15
  Gender               Male
  Nationality          Yemeni

============================================================
  Address
============================================================
  Address              Sanaa, Yemen

============================================================
  Card Validity
============================================================
  Issuance Date        2020-01-10
  Expiry Date          2030-01-10

============================================================
  Face Verification
============================================================
  Similarity Score     0.8734
  Match Status         ✓ Match
```

---

### Method 2: cURL Commands

**Test Health Endpoint:**
```bash
curl http://localhost:8000/health
```

**Test Verify Endpoint (Front ID + Selfie):**
```bash
curl -X POST http://localhost:8000/verify \
  -F "id_card_front=@data/id_cards/front.jpg" \
  -F "selfie=@data/selfies/person.jpg"
```

**Test Verify Endpoint (Front + Back ID + Selfie):**
```bash
curl -X POST http://localhost:8000/verify \
  -F "id_card_front=@data/id_cards/front.jpg" \
  -F "id_card_back=@data/id_cards/back.jpg" \
  -F "selfie=@data/selfies/person.jpg"
```

**Pretty Print JSON Response:**
```bash
curl -X POST http://localhost:8000/verify \
  -F "id_card_front=@data/id_cards/front.jpg" \
  -F "selfie=@data/selfies/person.jpg" \
  | python -m json.tool
```

---

### Method 3: Postman / Insomnia

1. **Create a new POST request**
2. **URL:** `http://localhost:8000/verify`
3. **Body Type:** `form-data`
4. **Add fields:**
   - `id_card_front` (file) → Select your ID front image
   - `selfie` (file) → Select your selfie image
   - `id_card_back` (file, optional) → Select your ID back image
5. **Send** and view the response

---

### Method 4: Python Requests

```python
import requests

# Prepare files
files = {
    'id_card_front': open('data/id_cards/front.jpg', 'rb'),
    'selfie': open('data/selfies/person.jpg', 'rb'),
    # Optional: 'id_card_back': open('data/id_cards/back.jpg', 'rb')
}

# Make request
response = requests.post('http://localhost:8000/verify', files=files)
result = response.json()

# Print results
print(f"Success: {result['success']}")
print(f"Name: {result['name_english']}")
print(f"ID Number: {result['extracted_id']}")
print(f"Similarity: {result['similarity_score']}")
```

---

### Method 5: FastAPI Interactive Docs

1. **Open your browser** and go to: `http://localhost:8000/docs`
2. **Click** on `/verify` endpoint
3. **Click** "Try it out"
4. **Upload** your files:
   - `id_card_front`: Browse and select front ID image
   - `selfie`: Browse and select selfie image
   - `id_card_back` (optional): Browse and select back ID image
5. **Click** "Execute"
6. **View** the response below

---

## 📊 Understanding the Response

### Success Response Example:
```json
{
  "success": true,
  "extracted_id": "123456789012",
  "id_type": "yemen_id",
  "similarity_score": 0.8734,
  "id_front": "123456789012_front_1736921535.jpg",
  "id_back": "123456789012_back_1736921535.jpg",
  "name_arabic": "أحمد محمد علي",
  "name_english": "Ahmed Mohammed Ali",
  "date_of_birth": "1990-05-15",
  "gender": "Male",
  "address": "Sanaa, Yemen",
  "nationality": "Yemeni",
  "issuance_date": "2020-01-10",
  "expiry_date": "2030-01-10",
  "error": null
}
```

### Field Descriptions:

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Overall verification success status |
| `extracted_id` | string | Extracted ID number from card |
| `id_type` | string | Type of ID (yemen_id, aadhaar, etc.) |
| `similarity_score` | float | Face match score (0.0-1.0) |
| `id_front` | string | Filename of saved front ID image |
| `id_back` | string | Filename of saved back ID image |
| `name_arabic` | string | Name in Arabic (original) |
| `name_english` | string | Name in English (translated) |
| `date_of_birth` | string | Birth date (YYYY-MM-DD) |
| `gender` | string | "Male" or "Female" |
| `address` | string | Address in English |
| `nationality` | string | Nationality |
| `issuance_date` | string | Card issue date (YYYY-MM-DD) |
| `expiry_date` | string | Card expiry date (YYYY-MM-DD) |
| `error` | string | Error message if failed |

### Similarity Score Interpretation:

| Score | Interpretation |
|-------|----------------|
| >= 0.7 | ✅ Strong Match (High confidence) |
| 0.5 - 0.7 | ⚠️ Possible Match (Review recommended) |
| < 0.5 | ❌ No Match (Different person) |

---

## 🐛 Troubleshooting

### Server Won't Start
```bash
# Check if port 8000 is already in use
# Windows:
netstat -ano | findstr :8000

# Kill the process if needed
taskkill /PID <process_id> /F

# Try a different port
uvicorn main:app --reload --port 8001
```

### Connection Refused
- ✅ Make sure server is running
- ✅ Check firewall settings
- ✅ Try `http://127.0.0.1:8000` instead of `localhost`

### OCR Not Ready
```bash
# Models might be loading
# Wait 10-20 seconds and try again

# Check health endpoint
curl http://localhost:8000/health
```

### NER Models Not Found
```bash
# Install spaCy models
python -m spacy download xx_ent_wiki_sm
python -m spacy download en_core_web_sm

# System will work without NER (lower accuracy)
```

### Low Accuracy / Missing Data
- ✅ Use high-quality, clear ID card scans
- ✅ Ensure good lighting and no glare
- ✅ Install NER models for better extraction
- ✅ Make sure text is readable

### Timeout Errors
```bash
# Increase timeout in test script
response = requests.post(url, files=files, timeout=60)

# First request might be slow (model loading)
# Subsequent requests should be faster
```

---

## 📝 Sample Test Data

If you don't have test images, you can:

1. **Use sample images** from previous tests
2. **Create test ID cards** using image editing software
3. **Find public Yemen ID samples** online (for testing only, not production data)
4. **Use the existing test images** in `data/id_cards/` directory

---

## 🔍 Advanced Testing

### Test Only ID Extraction
```bash
curl -X POST http://localhost:8000/extract-id \
  -F "image=@data/id_cards/front.jpg"
```

### Test Only Face Comparison
```bash
curl -X POST http://localhost:8000/compare-faces \
  -F "image1=@data/id_cards/front.jpg" \
  -F "image2=@data/selfies/person.jpg"
```

### Test Translation
```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{"texts": ["أحمد محمد", "صنعاء"]}'
```

### Test Quality Checks
**Check ID Quality:**
```bash
curl -X POST http://localhost:8000/check-id-quality \
  -F "id_card=@data/id_cards/front.jpg"
```

**Check Selfie Quality:**
```bash
curl -X POST http://localhost:8000/check-selfie-quality \
  -F "selfie=@data/selfies/person.jpg"
```

---

## 🎯 Next Steps

After successful testing:

1. ✅ **Review extracted data** accuracy
2. ✅ **Adjust confidence thresholds** if needed
3. ✅ **Integrate with your database**
4. ✅ **Deploy** to production environment
5. ✅ **Monitor** performance and accuracy

---

## 📚 Additional Resources

- **API Documentation**: `http://localhost:8000/docs`
- **Alternative API Docs**: `http://localhost:8000/redoc`
- **NER Setup Guide**: `NER_SETUP.md`
- **SDK Integration**: `API_ENDPOINTS_FOR_SDK_DEV.md`
