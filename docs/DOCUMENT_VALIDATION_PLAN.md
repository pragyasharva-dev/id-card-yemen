# Document Validation Implementation Plan

This plan maps regulatory requirements for **Yemen identity documents** and **passports** to technical validations. It defines **new dedicated services** for document validation: one for **Yemen ID cards** and one for **passports**. These new services implement all validation logic; they may call existing low-level components (e.g. OCR, face detection) only as **dependencies**, not by extending previous services.

---

## 0. Upload Flow and Validation Purpose

### Upload flow
- **Yemen ID card:** User uploads **front and back** (both sides required).
- **Passport:** User uploads **one side** only (single image).

### What we validate (original and genuine)
The system must ensure that the **captured document is original and genuine**, and must **reject**:
- **Photographs of documents** (e.g. a photo of an ID on a screen or printed)
- **Scanned copies** (flatbed or scanner output)
- **Black-and-white or color copies** (photocopies, printed copies)
- **Forged, altered, or otherwise invalid IDs**

Validation checks (sharpness, moiré, texture, clarity, layout, face, readability) are designed to detect these: e.g. moiré suggests screen capture, texture/sharpness suggest photocopy or re-capture, and consistency checks support detection of forgery or alteration.

---

## 1. New Services (Scope)

| Service | Purpose | Entry points |
|---------|---------|--------------|
| **Yemen ID Document Validation Service** | Validate that **front and back** captured images are original, genuine Yemen national ID (not photograph/scan/copy/forged). | `validate_yemen_id(front_image, back_image)` → full result |
| **Passport Document Validation Service** | Validate that the **single** captured image is an original, genuine passport (not photograph/scan/copy/forged). | `validate_passport(image)` → full result |

- **Location:** e.g. `services/yemen_id_validation_service.py` and `services/passport_validation_service.py` (or a single `services/document_validation/` package with `yemen_id.py` and `passport.py`).
- **Dependencies (use, do not extend):**  
  - OCR: call `ocr_service` for text and confidence (readability).  
  - Face: call `face_extractor` for face region / visibility when needed.  
  - No changes to `image_quality_service` or `liveness_service`; their logic is not reused—equivalent checks (e.g. clarity, “not screenshot”) are **implemented inside the new services** for document images.

---

## 2. Requirements Mapping Overview

| # | Requirement | Category | Implemented in |
|---|-------------|----------|----------------|
| 1 | Official identity document / Original passport | Document type & authenticity | New Yemen ID service / New Passport service |
| 2 | Not forged / altered / tampered | Integrity | New Yemen ID service / New Passport service |
| 3 | Not screenshot or copy / photocopy | Capture source | New Yemen ID service / New Passport service |
| 4 | Clear, readable, properly focused | Readability & focus | New Yemen ID service / New Passport service |
| 5 | Fully visible, not cropped | Completeness | New Yemen ID service / New Passport service |
| 6 | Not covered, obscured, or blocked | Occlusion | New Yemen ID service / New Passport service |
| 7 | No non-document objects | Scene purity | New Yemen ID service / New Passport service |

---

## 2. Validation Categories and Technical Approach

### 2.1 Document type and authenticity (official / original)

**Requirement:**  
- ID: “Is an official identity document.”  
- Passport: “Is an original passport … not forged, altered, or tampered with.”

**Approach (implemented inside new services):**

| Check | Technique | Notes |
|-------|-----------|--------|
| Document class | ID vs passport vs “other” classifier | Rule-based (aspect ratio, MRZ presence, layout) or small classifier. Yemen ID service / Passport service each implement their own rules. |
| Layout / template | Expected regions present | Yemen ID: photo zone, text block, 11-digit ID number. Passport: MRZ, photo, key fields. |
| Security features (optional) | Hologram/UV (if images allow) | Lower priority; depends on capture hardware. |

**In new services:**  
- Yemen ID service: `_check_official_yemen_id(image)` → layout + expected regions (photo + ID number).  
- Passport service: `_check_official_passport(image)` → layout + MRZ + photo.  
- Shared enum: `DocumentType` (e.g. `yemen_id`, `passport`, `unknown`) used in responses.

---

### 2.2 Not forged, altered, or tampered

**Requirement:**  
- “Original and not forged or tampered with” (ID).  
- “Not forged, altered, or tampered with” (passport).

**Approach (implemented inside new services):**

| Check | Technique | Notes |
|-------|-----------|--------|
| Consistency | Face on document; text vs layout | New services call face_extractor for face presence; optional name/DOB consistency from OCR. |
| Cloning / splicing | Inconsistency in lighting, noise, or edges | New services implement region-based noise/lighting consistency (e.g. different stats in patches = suspect). |
| Text overlay | Suspicious text alignment / font vs background | New services implement heuristics or call optional tampering model. |

**In new services:**  
- Yemen ID service: `_check_integrity_yemen_id(image)` → consistency + noise/lighting.  
- Passport service: `_check_integrity_passport(image)` → same.  
- No dependency on existing “face match” service for document-side logic; that stays in verification flow.

---

### 2.3 Not screenshot or copy (including photocopy)

**Requirement:**  
- “Not a screenshot or copy” (ID).  
- “Not a screenshot or photocopy” (passport).

**Approach (implemented inside new services):**

| Check | Technique | Notes |
|-------|-----------|--------|
| Screen capture | Moiré, pixel grid, refresh artifacts | New services implement FFT/moiré analysis on document image (or shared helper used only by document validation). |
| Photocopy / scan | Flat lighting, loss of detail, halftone patterns | New services implement texture (e.g. LBP) and frequency analysis. |
| Re-capture | Compression artifacts, secondary framing | New services implement “photo of photo” detection (e.g. rectangular frame, blur). |

**In new services:**  
- Yemen ID service: `_check_not_screenshot_or_copy(image)` (or shared `_document_capture_source_checks(image, document_type)`).  
- Passport service: same logic with passport-specific thresholds if needed.  
- Logic is **new code** in the document validation services, not an extension of liveness_service.

---

### 2.4 Clear, readable, and properly focused

**Requirement:**  
- “Clear, readable, and properly focused” (both ID and passport).

**Approach (implemented inside new services):**

| Check | Technique | Notes |
|-------|-----------|--------|
| Blur / focus | Laplacian variance, frequency content | New services implement sharpness check with document-specific thresholds. |
| Readability | OCR confidence + required fields | New services **call** `ocr_service.extract_id_from_image` (or passport OCR) and enforce min confidence + “required fields present”. |
| Resolution | Min width/height and DPI proxy | New services implement min resolution check. |

**In new services:**  
- Yemen ID service: `_check_clarity_yemen_id(image)` → sharpness + call OCR for 11-digit ID + confidence.  
- Passport service: `_check_clarity_passport(image)` → sharpness + call OCR for MRZ/fields + confidence.  
- Optional shared helper: `_check_document_resolution(image, min_side_px)`.

---

### 2.5 Fully visible and not cropped

**Requirement:**  
- “Fully visible and not cropped or partially captured” (ID).  
- “Fully visible and not cropped” (passport).

**Approach (implemented inside new services):**

| Check | Technique | Notes |
|-------|-----------|--------|
| Document boundary | Detect document contour / quadrilateral | New services implement contour detection; validate aspect ratio (Yemen ID vs passport ranges). |
| Edge margin | Document not flush with image edges | New services require minimum margin between document and image edges. |
| Required regions | Photo + ID number (ID); MRZ + photo (passport) | New services ensure key zones fall inside detected document. |

**In new services:**  
- Yemen ID service: `_check_fully_visible_yemen_id(image)` → boundary + margins + aspect ratio for ID.  
- Passport service: `_check_fully_visible_passport(image)` → same with passport aspect ratio.  
- Optional shared module: `document_detection.py` (contour + aspect) used only by these two services.

---

### 2.6 Not covered, obscured, or blocked

**Requirement:**  
- “Not covered, obscured, or blocked (including face or ID details)” (ID).  
- “Not covered or obscured in any way” (passport).

**Approach (implemented inside new services):**

| Check | Technique | Notes |
|-------|-----------|--------|
| Face on document | Face visibility and occlusion | New services **call** `face_extractor` to get face/landmarks; implement own rules for “face visible, not covered” on document (or shared helper). |
| Text regions | OCR coverage and confidence | New services use OCR result (from clarity step) to ensure expected text present and not low-confidence (obscuring). |
| Glare / reflection | Bright spots, saturation | New services implement glare/overexposure detection on document region. |

**In new services:**  
- Yemen ID service: `_check_not_obscured_yemen_id(image, ocr_result?)` → face visibility (via face_extractor) + text regions + glare.  
- Passport service: `_check_not_obscured_passport(image, ocr_result?)` → same.  
- No dependency on `image_quality_service`; validation logic lives in the new document validation services.

---

### 2.7 No non-document objects (ID) / No non-passport objects (passport)

**Requirement:**  
- “Does not contain non-ID objects (e.g. paper, phone screens, other cards …).”  
- “Does not include non-passport objects or backgrounds.”

**Approach (implemented inside new services):**

| Check | Technique | Notes |
|-------|-----------|--------|
| Document dominance | Document should occupy majority of frame | New services use document boundary from §2.5; require document area / image area above threshold. |
| Background clutter | Reject multiple strong “cards” or many small objects | New services implement contour count and size distribution; expect one dominant document. |
| Phone/screen | Rectangular bright regions, UI-like edges | New services implement heuristic or simple “screen vs document” check. |
| Other cards / paper | Multiple rectangles, text outside document | Optional: new services use OCR/contours to ensure single primary document. |

**In new services:**  
- Yemen ID service: `_check_no_extra_objects_yemen_id(image, document_bbox?)`.  
- Passport service: `_check_no_extra_objects_passport(image, document_bbox?)`.  
- Shared logic possible in a common helper used only by these two services.

---

## 3. Implementation Phases

All phases deliver **new code inside the Yemen ID validation service and the Passport validation service**. Existing services are not extended; they may be **called** only as dependencies (e.g. OCR, face_extractor).

### Phase 1 – Foundation (readability, focus, occlusion)

**Goal:** Implement “clear, readable, focused” and “not covered/obscured” **inside the new Yemen ID and Passport services**.

| Task | Description | Owner |
|------|-------------|--------|
| 1.1 | Implement **document sharpness/blur** check (Laplacian/frequency) in new services; expose as `_check_clarity_*`. | Yemen ID service, Passport service |
| 1.2 | Implement **readability**: call `ocr_service.extract_id_from_image` (or passport OCR); enforce min confidence and “ID number / MRZ present”. | Yemen ID service, Passport service |
| 1.3 | Implement **face and text not obscured**: call `face_extractor` for face visibility; use OCR result for text regions; implement **glare** check (bright/saturated regions). | Yemen ID service, Passport service |
| 1.4 | Add config flags and thresholds (e.g. min sharpness, min OCR confidence) in `config.py` for document validation. | `utils/config.py` |

**Exit criteria:**  
- Yemen ID and Passport services each return: focus/sharpness passed, readable (OCR + confidence), face not obscured; optional glare.

---

### Phase 2 – Completeness and capture source

**Goal:** Implement “fully visible, not cropped” and “not screenshot/copy” **inside the new services**.

| Task | Description | Owner |
|------|-------------|--------|
| 2.1 | **Document boundary**: implement contour/quadrilateral detection; validate aspect ratio (Yemen ID vs passport). Can live in shared helper used only by the two new services. | Yemen ID service, Passport service (or shared `document_detection` helper) |
| 2.2 | **Completeness**: require margins between document and image edges; optional “required regions inside bbox”. | Yemen ID service, Passport service |
| 2.3 | **Not screenshot/copy**: implement moiré (FFT), texture (LBP), and sharpness checks **in the new services** for document image (or document ROI). | Yemen ID service, Passport service |
| 2.4 | Expose `validate_yemen_id(image)` and `validate_passport(image)` from new services; add API routes that call them. | New services + `api/routes.py` |

**Exit criteria:**  
- Cropped documents rejected (margins + aspect ratio).  
- Screenshot/photocopy-like images rejected (moire/texture/sharpness).  
- All logic in new Yemen ID and Passport services (or shared helper used only by them).

---

### Phase 3 – Document type and scene purity

**Goal:** Implement “official document” / “original passport” and “no non-document objects” **inside the new services**.

| Task | Description | Owner |
|------|-------------|--------|
| 3.1 | **Document type**: implement rule-based (or small model) Yemen ID vs passport vs other (aspect ratio, MRZ for passport, layout). | Yemen ID service, Passport service |
| 3.2 | **No extra objects**: implement document dominance (document area / image area); reject multiple large rectangles or “second card”. | Yemen ID service, Passport service |
| 3.3 | Optional: implement “screen vs document” heuristic (e.g. very uniform bright rectangle, phone aspect). | Yemen ID service, Passport service |
| 3.4 | Return structured result: `document_type`, `document_bbox`, `completeness_ok`, `no_extra_objects_ok` from each new service. | Yemen ID service, Passport service + schemas |

**Exit criteria:**  
- Classification: Yemen ID vs passport vs unknown.  
- Reject frames where document does not dominate or multiple documents detected.  
- Logic only in new services.

---

### Phase 4 – Integrity and tampering (optional / later)

**Goal:** Implement “not forged or tampered” **inside the new services**.

| Task | Description | Owner |
|------|-------------|--------|
| 4.1 | **Consistency**: use face on document (via face_extractor); optional name/DOB consistency from OCR. Face match with selfie remains in verification flow, not in document validation. | Yemen ID service, Passport service |
| 4.2 | **Noise/lighting consistency**: implement region-based noise/lighting comparison in new services; flag inconsistent regions (e.g. pasted). | Yemen ID service, Passport service |
| 4.3 | Optional: integrate small **tampering detection** model (binary “tampered vs clean”) in new services. | Yemen ID service, Passport service |

**Exit criteria:**  
- Basic consistency and integrity checks in place inside new services; obvious cut-paste or inconsistent regions flagged.

---

## 4. New Service Layout (Yemen ID and Passport Only)

- **New services (create from scratch):**  
  - **Yemen ID Document Validation Service** (`services/yemen_id_validation_service.py`):  
    - Entry: `validate_yemen_id(image) -> DocumentValidationResult`.  
    - Implements all 7 requirement categories for Yemen national ID: official document, not forged, not screenshot/copy, clear/readable/focused, fully visible, not obscured, no extra objects.  
    - May **call** (do not extend): `ocr_service` (readability), `face_extractor` (face visibility on document).  
  - **Passport Document Validation Service** (`services/passport_validation_service.py`):  
    - Entry: `validate_passport(image) -> DocumentValidationResult`.  
    - Implements all 7 requirement categories for passport: original passport, not forged, not screenshot/photocopy, clear/readable/focused, fully visible, not obscured, no extra objects.  
    - May **call** (do not extend): `ocr_service` (MRZ/readability), `face_extractor` (face visibility on document).  

- **Optional shared code (used only by these two new services):**  
  - **Document detection helper** (e.g. `services/document_validation_helpers.py` or `services/document_detection.py`): contour detection, aspect ratio, margins.  
  - **Document capture-source checks** (e.g. moiré, texture, sharpness for document image): can live in the same helper or inside each new service.  
  - No changes to `image_quality_service`, `liveness_service`, or other existing services.

- **Existing services (unchanged; used only as dependencies):**  
  - `ocr_service`: called by new services for text and confidence.  
  - `face_extractor`: called by new services for face region/visibility on document.  
  - `image_quality_service` / `liveness_service`: remain for **selfie** and current flows; **not** used by the new document validation services.

- **API:**  
  - New endpoints that call **only** the new services:  
  - `POST /validate-yemen-id` (id_card_front, id_card_back optional) → calls `validate_yemen_id(front_image, back_image)`.  
  - `POST /validate-passport` (image) → calls `validate_passport(image)` (single image).
  - Response: same structure for both, with `document_type` (`yemen_id` or `passport`) and per-requirement checks (e.g. `official_document`, `not_screenshot_or_copy`, `clear_and_readable`, `fully_visible`, `not_obscured`, `no_extra_objects`, `integrity`).

---

## 5. Dependencies (call only, do not extend)

The **new Yemen ID and Passport validation services** may **call** these existing components only as dependencies:

| Dependency | Used for |
|------------|----------|
| `ocr_service.extract_id_from_image` / OCR for passport | Readability: text extraction, confidence, required fields (11-digit ID, MRZ). |
| `face_extractor` (detect_faces, get_largest_face, landmarks) | Face visibility and occlusion on the document (face region not covered). |

No changes are made to `image_quality_service`, `liveness_service`, or `ocr_service`. All document-specific validation logic (clarity, screenshot/copy, completeness, document type, extra objects, integrity) is **new code** inside the Yemen ID and Passport validation services (or a shared helper used only by them).

---

## 6. Configuration and Response Shape (draft)

**Config (e.g. in `utils/config.py`) – used by new Yemen ID and Passport services:**

```python
# Document validation (Yemen ID and Passport services)
DOC_VALIDATION_ENABLED = True
DOC_MIN_SHARPNESS = 0.02          # document sharpness
DOC_MIN_OCR_CONFIDENCE = 0.7
DOC_MIN_MARGIN_RATIO = 0.02      # min margin (e.g. 2% of width/height)
DOC_MIN_COVERAGE_RATIO = 0.5     # document should occupy ≥ 50% of image
DOC_ASPECT_RATIO_ID = (1.4, 1.7) # Yemen ID approximate
DOC_ASPECT_RATIO_PASSPORT = (1.3, 1.5)
DOC_SCREENSHOT_MOIRE_THRESHOLD = 0.20
```

**Response (same shape for both endpoints):**

- `POST /validate-yemen-id` → `document_type: "yemen_id"`
- `POST /validate-passport` → `document_type: "passport"`

```json
{
  "passed": true,
  "document_type": "yemen_id",
  "checks": {
    "official_document": { "passed": true },
    "not_screenshot_or_copy": { "passed": true },
    "clear_and_readable": { "passed": true },
    "fully_visible": { "passed": true },
    "not_obscured": { "passed": true },
    "no_extra_objects": { "passed": true },
    "integrity": { "passed": true }
  },
  "error": null
}
```

---

## 7. Summary Table (requirement → implementation)

| Requirement | Phase | Main technique | Implemented in |
|-------------|--------|----------------|----------------|
| Official document / Original | 3 | Document type + layout | Yemen ID service, Passport service |
| Not forged/tampered | 4 | Consistency + noise/lighting | Yemen ID service, Passport service |
| Not screenshot/copy | 2 | Moiré, texture, sharpness on doc | Yemen ID service, Passport service |
| Clear, readable, focused | 1 | Sharpness + call OCR for confidence | Yemen ID service, Passport service |
| Fully visible, not cropped | 2 | Boundary + margins + aspect | Yemen ID service, Passport service (or shared helper) |
| Not covered/obscured | 1 | Call face_extractor + glare + OCR | Yemen ID service, Passport service |
| No non-document objects | 3 | Document dominance + one doc | Yemen ID service, Passport service |

This plan defines **new dedicated services** for Yemen ID card and passport validation. All validation logic is implemented inside these new services (or a small shared helper used only by them). Existing services (image_quality_service, liveness_service, ocr_service, face_extractor) are **not extended**; they may be **called** only as dependencies where needed.

---

## 8. Implementation Summary (How to Run and Test)

### Files created

| File | Purpose |
|------|---------|
| `utils/config.py` | Added `DOC_*` constants (sharpness, OCR confidence, resolution, margins, coverage, aspect ratios, moiré, texture). |
| `models/schemas.py` | Added `DocumentCheckResult`, `DocumentValidationResult`. |
| `services/document_validation_helpers.py` | Shared helpers: sharpness, moiré, texture, resolution, document boundary, glare, `check_not_screenshot_or_copy`. |
| `services/yemen_id_validation_service.py` | `validate_yemen_id(image)` – all 7 checks for Yemen ID. |
| `services/passport_validation_service.py` | `validate_passport(image)` – all 7 checks for passport. |
| `api/routes.py` | `POST /validate-yemen-id`, `POST /validate-passport`. |

### Run the API

```bash
uv run uvicorn main:app --reload
```

### Test endpoints

- **Yemen ID:**  
  `POST http://localhost:8000/validate-yemen-id` with form fields `id_card_front` (required) and `id_card_back` (optional; recommended).

- **Passport:**  
  `POST http://localhost:8000/validate-passport` with form field `image` = passport image.

Example (curl):

```bash
curl -X POST "http://localhost:8000/validate-yemen-id" -F "id_card_front=@path/to/id_front.jpg" -F "id_card_back=@path/to/id_back.jpg"
curl -X POST "http://localhost:8000/validate-passport" -F "image=@path/to/passport.jpg"
```

Response: `passed` (bool), `document_type` ("yemen_id" or "passport"), `checks` (per-check results), `error` (if failed).

### Disable validation

Set `DOC_VALIDATION_ENABLED = False` in `utils/config.py` to have both endpoints return `passed: true` without running checks.
