# Document Validation – Methods, Terms & Thresholds

Reference for **Yemen ID** and **Passport** validation: which checks run, how they work, and what thresholds/conditions are used.

---

## 1. Shared configuration (config.py)

All thresholds below are defined in **`utils/config.py`** unless noted as hardcoded in code.

| Constant | Value | Used for | Meaning |
|----------|--------|----------|---------|
| **Resolution & layout** ||||
| `DOC_MIN_RESOLUTION_PX` | 320 | Both | Minimum side length (pixels). Image must have `min(height, width) >= 320`. |
| `DOC_MIN_MARGIN_RATIO` | 0.005 (0.5%) | Both | Margin check: document edge to image edge ≥ 0.5% of image size (relaxed when document fills frame). |
| `DOC_MIN_COVERAGE_RATIO` | 0.5 | Both | Document must occupy ≥ 50% of image area (fully visible, no extra objects). |
| `DOC_ASPECT_RATIO_YEMEN_ID` | (1.3, 1.8) | Yemen ID front | Width/height of detected document must be in this range. |
| `DOC_ASPECT_RATIO_YEMEN_ID_BACK` | (1.0, 2.0) | Yemen ID back | Same for back side. |
| `DOC_ASPECT_RATIO_PASSPORT` | (0.6, 1.7) | Passport | Same for passport data page. |
| **Sharpness** ||||
| `DOC_MIN_SHARPNESS` | 0.04 | Yemen ID | Min normalized sharpness (Laplacian); below = blurry/copy. |
| `DOC_MIN_SHARPNESS_PASSPORT` | 0.08 | Passport | Stricter for passport. |
| **Not screenshot/copy – Moiré** ||||
| `DOC_MOIRE_THRESHOLD` | 0.30 | Yemen ID front | Moiré score must be **>** this (higher score = less moiré = more natural). |
| `DOC_MOIRE_THRESHOLD_BACK` | 0.25 | Yemen ID back | More lenient (barcode/QR can add pattern). |
| `DOC_MOIRE_THRESHOLD_PASSPORT` | 0.33 | Passport | Stricter for passport. |
| **Not screenshot/copy – Screen grid** ||||
| `DOC_SCREEN_GRID_MAX` | 0.55 | Yemen ID front | Screen-grid score must be **≤** this (higher = more LCD/screen pattern). |
| `DOC_SCREEN_GRID_MAX_BACK` | 0.65 | Yemen ID back | More lenient. |
| `DOC_SCREEN_GRID_MAX_PASSPORT` | 0.53 | Passport | Stricter. |
| **Passport – combined screen-capture rule** ||||
| `DOC_PASSPORT_MOIRE_BORDERLINE_MIN` | 0.33 | Passport | If moiré in [min, max] **and** screen_grid in suspicious range → reject (screen capture). |
| `DOC_PASSPORT_MOIRE_BORDERLINE_MAX` | 0.36 | Passport | |
| `DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MIN` | 0.38 | Passport | |
| `DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MAX` | 0.50 | Passport | |
| **Not screenshot/copy – Texture, halftone, saturation** ||||
| `DOC_TEXTURE_THRESHOLD` | 0.08 | Both | LBP texture score must be **≥** this (photocopies flatter). |
| `DOC_TEXTURE_MAX` | 1.0 | Both | Texture score must be **≤** this. |
| `DOC_HALFTONE_MAX` | 0.35 | Yemen ID | Halftone score must be **≤** this (printed copies show dots). |
| `DOC_HALFTONE_MAX_PASSPORT` | 0.28 | Passport | Stricter for passport. |
| `DOC_HIGH_TEXTURE_THRESHOLD` | 0.92 | Both | When texture **≥** this, saturation is also checked. |
| `DOC_MIN_SATURATION_FOR_HIGH_TEXTURE` | 0.06 | Both | If texture high, mean saturation must be **≥** this (reject very flat prints). |
| **Readability** ||||
| `DOC_MIN_OCR_CONFIDENCE` | 0.55 | Both | OCR confidence for required text must be **≥** this. |
| **Glare / obstruction** ||||
| `DOC_GLARE_MAX_RATIO` | 0.15 (15%) | Both | Fraction of (document ROI or full) pixels that may be overexposed/saturated; above = fail. |
| `DOC_OBSTRUCTION_SKIN_RATIO_MAX` | 0.22 | Both | Max fraction of document pixels that may be skin-colored (finger/hand); above = fail. |
| `DOC_OBSTRUCTION_FLAT_CELL_RATIO_MAX` | 0.25 | Both | Max fraction of document grid cells allowed with very low variance (sticker/tape/paper). |
| `DOC_OBSTRUCTION_FLAT_VARIANCE_THRESHOLD` | 80 | Both | Cell variance below this = flat (possible sticker/tape/paper). |

---

## 2. Check methods and logic

### 2.1 Resolution

- **Method:** `check_document_resolution(image)` in **`document_validation_helpers.py`**.
- **Condition:** `min(height, width) >= DOC_MIN_RESOLUTION_PX` (320).
- **Used by:** Yemen ID (front + back), Passport.

---

### 2.2 Official document (Yemen ID)

- **Method:** `_check_official_yemen_id(image, ocr_result, face_detected)` in **`yemen_id_validation_service.py`**.
- **Terms:**
  - OCR must return 11-digit Yemen ID (`id_type == "yemen_id"`, `extracted_id` present).
  - Face must be detected on the document.
- **Pass:** Both true. No numeric threshold beyond OCR/face logic.

---

### 2.3 Official document & document is passport (Passport)

- **Methods:**
  - `_check_official_passport(image, ocr_result, face_detected)`  
  - `_check_document_is_passport_not_id(ocr_result)`
- **Terms:**
  - **Official:** OCR has passport content (MRZ starting with `P<` or text containing "PASSPORT" / "REPUBLIC OF YEMEN PASSPORT") **and** face detected.
  - **Is passport:** Document must not be treated as Yemen ID only (reject ID card sent to passport endpoint).

---

### 2.4 Not screenshot or copy

- **Method:** `check_not_screenshot_or_copy(image, for_back=..., for_passport=...)` in **`document_validation_helpers.py`**.
- **Sub-checks and thresholds:**

| Sub-check | Method | Score meaning | Pass condition | Yemen ID front | Yemen ID back | Passport |
|-----------|--------|----------------|-----------------|-----------------|---------------|----------|
| **Sharpness** | `check_document_sharpness` | Higher = sharper | score ≥ threshold | ≥ 0.04 | ≥ 0.04 | ≥ 0.08 |
| **Moiré** | `check_document_moire` | Higher = less moiré (more natural) | score **>** threshold | > 0.30 | > 0.25 | > 0.33 |
| **Screen grid** | `check_screen_grid` | Higher = more screen/LCD pattern | score **≤** max | ≤ 0.55 | ≤ 0.65 | ≤ 0.53 |
| **Texture** | `check_document_texture` | LBP variance; flat = copy | threshold ≤ score ≤ max | 0.08–1.0 | same | same |
| **Halftone** | `check_halftone` | Higher = more print-dot pattern | score **≤** max | ≤ 0.35 | ≤ 0.35 | ≤ 0.28 |
| **Saturation** | `_mean_saturation` (when texture ≥ 0.92) | Mean saturation in HSV | score ≥ 0.06 | ≥ 0.06 | same | same |

- **Passport-only extra rule (combined):**  
  If **both**  
  - moiré in `[DOC_PASSPORT_MOIRE_BORDERLINE_MIN, DOC_PASSPORT_MOIRE_BORDERLINE_MAX]` (0.33–0.36)  
  - **and** screen_grid in `[DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MIN, DOC_PASSPORT_SCREEN_GRID_SUSPICIOUS_MAX]` (0.38–0.50)  
  then **fail** as suspected screen capture, even if individual moiré/screen_grid pass.

**Technical summary of sub-methods:**

- **Sharpness:** Laplacian variance on grayscale, normalized by image size; score = min(1, variance/100).
- **Moiré:** 256×256 FFT (Hann window); ratio of mid-frequency to valid energy; score = 1 − 1.5×ratio (clamped 0–1).
- **Screen grid:** FFT; peak/mean in mid-high frequency ring (distance 25–90); score = (ratio−1)/20 (clamped 0–1).
- **Texture:** LBP histogram variance; normalized to ~0–1 (reference 20).
- **Halftone:** FFT; concentration of energy in top bins in mid-frequency band; score scaled so halftone prints score high.

---

### 2.5 Clear and readable

- **Methods:** `_check_clarity_yemen_id` / `_check_clarity_passport`.
- **Terms:**
  - Sharpness check passes (same as in not_screenshot_or_copy).
  - OCR returns required content (11-digit ID or passport content).
  - OCR confidence **≥** `DOC_MIN_OCR_CONFIDENCE` (0.55).

---

### 2.6 Fully visible

- **Method:** `get_document_boundary(image, aspect_range)` then coverage/margin logic in `_check_fully_visible_*`.
- **Terms:**
  - Document boundary found with aspect ratio in document-specific range.
  - **Coverage:** `area_ratio >= DOC_MIN_COVERAGE_RATIO` (0.5).
  - **Margin:** `margin_ok` (each side ≥ 0.5% of image) **or** `area_ratio >= 0.75` (document fills frame).

---

### 2.7 Not obscured (covered/obstructed)

- **Methods:** `check_glare(image, roi=document_bbox)` + `check_document_obstruction(image, boundary)` + face + OCR content.
- **Terms:**
  - **Face** detected on document.
  - **Glare:** When document boundary is available, glare is measured on the document ROI only; otherwise full image. Fraction of pixels with value ≥ 250 must be **≤** `DOC_GLARE_MAX_RATIO` (0.15).
  - **Obstruction:** When boundary is available, `check_document_obstruction` runs:
    - **Skin ratio:** Fraction of document pixels in skin-like HSV range (finger/hand) must be **≤** `DOC_OBSTRUCTION_SKIN_RATIO_MAX` (0.22).
    - **Flat cells:** Document is divided into a 4×4 grid; fraction of cells with variance **<** `DOC_OBSTRUCTION_FLAT_VARIANCE_THRESHOLD` (80) must be **≤** `DOC_OBSTRUCTION_FLAT_CELL_RATIO_MAX` (0.25) (sticker/tape/paper).
  - **Required text** present (Yemen ID or passport content).
- **Blur** is handled by sharpness and clear_and_readable checks, not here.

---

### 2.8 No extra objects

- **Method:** `get_document_boundary` then `area_ratio >= DOC_MIN_COVERAGE_RATIO` (0.5).
- **Terms:** Document must occupy ≥ 50% of image (same as coverage).

---

### 2.9 Integrity

- **Method:** `_check_integrity_*`.
- **Terms:** Face must be detected on the document (no numeric threshold).

---

## 3. Which checks run where

| Check | Yemen ID front | Yemen ID back | Passport |
|-------|----------------|---------------|----------|
| resolution | ✓ | ✓ | ✓ |
| official_document | ✓ (11-digit ID + face) | — | ✓ (passport content + face) |
| document_is_passport | — | — | ✓ (reject ID card) |
| not_screenshot_or_copy | ✓ (front thresholds) | ✓ (back thresholds) | ✓ (passport + combined rule) |
| clear_and_readable | ✓ | — | ✓ |
| fully_visible | ✓ | ✓ (back aspect) | ✓ |
| not_obscured | ✓ | — | ✓ |
| no_extra_objects | ✓ | ✓ | ✓ |
| integrity | ✓ | — | ✓ |

---

## 4. Overall pass/fail

- **Yemen ID:** All front checks must pass; if back is uploaded, back-specific checks (resolution, not_screenshot_or_copy, sharpness, fully_visible, no_extra_objects) must also pass.
- **Passport:** All listed checks (including document_is_passport and not_screenshot_or_copy with passport + combined rule) must pass.

All thresholds and document-type rules above are what the code uses for ID and passport checks.
