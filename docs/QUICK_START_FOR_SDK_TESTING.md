# Quick Start: Exposing API to SDK Developers

## Your Setup (2 Simple Steps)

### Step 1: Start Your API

```bash
cd c:\Users\user\Desktop\id-card-yemen
python main.py
```

Wait for:
```
INFO - e-KYC API ready!
```

### Step 2: Expose with ngrok

Open a **new terminal**:

```bash
ngrok http 8000
```

You'll see something like:
```
Forwarding   https://abc123-xyz.ngrok-free.app -> http://localhost:8000
```

**Copy the HTTPS URL** (e.g., `https://abc123-xyz.ngrok-free.app`)

---

## ✅ Give SDK Developers This Information

### Base URL
```
https://YOUR-NGROK-URL.ngrok-free.app
```

### Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Check API health |
| `/verify` | POST | Full verification (ID + Selfie) |
| `/extract-id` | POST | Extract ID number only |
| `/compare-faces` | POST | Compare two faces |
| `/translate` | POST | Translate Arabic to English |

### Example Test (cURL)

```bash
# Health check
curl https://YOUR-NGROK-URL.ngrok-free.app/health

# Full verification
curl -X POST https://YOUR-NGROK-URL.ngrok-free.app/verify \
  -F "id_card=@id_card.jpg" \
  -F "selfie=@selfie.jpg"
```

### SDK Example (Python)

```python
from sdk_examples.python_sdk_example import YemenEKYCClient

# Use your ngrok URL
client = YemenEKYCClient(base_url="https://YOUR-NGROK-URL.ngrok-free.app")

# Test
result = client.verify_identity("id.jpg", "selfie.jpg")
print(result)
```

### SDK Example (JavaScript)

```javascript
const YemenEKYCClient = require('./sdk_examples/javascript_sdk_example');

// Use your ngrok URL
const client = new YemenEKYCClient('https://YOUR-NGROK-URL.ngrok-free.app');

// Test
const result = await client.verifyIdentity('id.jpg', 'selfie.jpg');
console.log(result);
```

---

## 📝 Important Notes for SDK Developer

1. **API Documentation**: Available at `https://YOUR-NGROK-URL.ngrok-free.app/docs`
2. **Response Format**: All endpoints return JSON
3. **File Upload**: Use `multipart/form-data` for image uploads
4. **Image Formats**: Supports JPG, PNG, JPEG
5. **CORS Enabled**: API accepts requests from any origin

---

## 🔄 When ngrok Restarts

Free ngrok URLs change on each restart. When you restart ngrok:

1. Get the new URL from ngrok terminal
2. Share the new URL with SDK developers
3. No code changes needed - just update the base URL

---

## ⚠️ Keep Running

Keep **both terminals open** while SDK developers are testing:
- Terminal 1: `python main.py` (API server)
- Terminal 2: `ngrok http 8000` (Public tunnel)

Close them when testing is done.
