# Yemen e-KYC API - SDK Integration Quick Reference

## 📍 API Endpoints (Receiving Images from SDK)

**Base URL**: `http://localhost:8000` (development)

### 1. Full Verification (Recommended)
```
POST /verify
```
- **Receives**: ID card image + selfie image
- **Returns**: Similarity score, match result
- **Use when**: You want complete OCR + face verification

### 2. Extract ID Only
```
POST /extract-id
```
- **Receives**: ID card image
- **Returns**: ID number, OCR data
- **Use when**: You only need ID extraction

### 3. Compare Faces Only
```
POST /compare-faces
```
- **Receives**: Two images
- **Returns**: Similarity score
- **Use when**: You already have ID data, just need face match

### 4. Translate Arabic
```
POST /translate
```
- **Receives**: Arabic text (JSON)
- **Returns**: English translation

---

## 📤 Sending Results Back (Webhook)

The API **does NOT have a separate "send results back" endpoint**. Instead:

### Option 1: Direct Response (Synchronous)
Results are returned immediately in the HTTP response. Your SDK receives them directly.

### Option 2: Webhook (Asynchronous)
Configure a webhook to receive results at your server:

1. **Configure webhook** in [`config/webhook_config.py`](file:///c:/Users/user/Desktop/id-card-yemen/config/webhook_config.py):
   ```python
   WEBHOOK_ENABLED = True
   WEBHOOK_URL = "https://your-server.com/webhook/ekyc"
   WEBHOOK_SECRET_KEY = "your-secret"
   ```

2. **Your server receives**:
   ```json
   {
     "event_type": "verification_complete",
     "timestamp": "2026-01-14T10:45:00",
     "data": {
       "success": true,
       "similarity_score": 0.85,
       "match": true
     }
   }
   ```

---

## 🚀 Quick Start Examples

### Python
```python
from sdk_examples.python_sdk_example import YemenEKYCClient

client = YemenEKYCClient("http://localhost:8000")
result = client.verify_identity("id.jpg", "selfie.jpg")
print(result)
```

### JavaScript
```javascript
const YemenEKYCClient = require('./sdk_examples/javascript_sdk_example');
const client = new YemenEKYCClient('http://localhost:8000');
const result = await client.verifyIdentity('id.jpg', 'selfie.jpg');
console.log(result);
```

### cURL
```bash
curl -X POST http://localhost:8000/verify \
  -F "id_card=@id.jpg" \
  -F "selfie=@selfie.jpg"
```

---

## 📚 Documentation

- **Complete SDK Guide**: [`api_integration_guide.md`](file:///C:/Users/user/.gemini/antigravity/brain/4175558a-743c-4dd1-b714-8935ed981676/api_integration_guide.md)
- **Webhook Setup**: [`webhook_setup_guide.md`](file:///C:/Users/user/.gemini/antigravity/brain/4175558a-743c-4dd1-b714-8935ed981676/webhook_setup_guide.md)
- **SDK Examples**: [`sdk_examples/`](file:///c:/Users/user/Desktop/id-card-yemen/sdk_examples/)

---

## 📍 Created Files

### SDK Examples
- [`python_sdk_example.py`](file:///c:/Users/user/Desktop/id-card-yemen/sdk_examples/python_sdk_example.py) - Python client
- [`javascript_sdk_example.js`](file:///c:/Users/user/Desktop/id-card-yemen/sdk_examples/javascript_sdk_example.js) - Node.js client
- [`curl_examples.sh`](file:///c:/Users/user/Desktop/id-card-yemen/sdk_examples/curl_examples.sh) - cURL test commands

### Webhook System
- [`webhook_service.py`](file:///c:/Users/user/Desktop/id-card-yemen/services/webhook_service.py) - Webhook forwarding service
- [`webhook_config.py`](file:///c:/Users/user/Desktop/id-card-yemen/config/webhook_config.py) - Configuration file
- [`webhook_receiver_example.py`](file:///c:/Users/user/Desktop/id-card-yemen/sdk_examples/webhook_receiver_example.py) - Example Flask receiver

### Updated Files
- [`routes.py`](file:///c:/Users/user/Desktop/id-card-yemen/api/routes.py) - Added webhook integration
