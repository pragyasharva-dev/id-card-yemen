# Document Validation Logic – Explained

This document explains the **logic** behind the Yemen ID and Passport document validation: what each check does, how it works, and why the thresholds are set as they are.

---

## 1. Overall flow

- **Yemen ID:** User uploads **front** (required) and **back** (optional). We validate that both sides are **original and genuine** (not a photograph of a screen, scan, photocopy, or forged document).
- **Passport:** User uploads **one image** (biodata page). Same “original and genuine” idea.

Validation runs a set of **checks**. The document **passes** only if **all** of these checks pass. If any check fails, we return `passed: false` and list which checks failed.

---

## 2. Checks and their logic

### 2.1 Resolution

**Purpose:** Reject images that are too small to be useful (e.g. thumbnails, very low resolution).

**Logic:**
- Take the **minimum of image width and height** (in pixels).
- If `min_side >= DOC_MIN_RESOLUTION_PX` (320) → **pass**.
- Otherwise → **fail** (“Image too small”).

**Config:** `DOC_MIN_RESOLUTION_PX = 320`

---

### 2.2 Official document (Yemen ID) / Official passport

**Purpose:** Ensure the image is actually an ID card or passport (expected content + face where relevant).

**Yemen ID:**
- Run **OCR** on the front image.
- Check that we found an **11-digit national number** and that the detected ID type is `yemen_id`.
- Use **face detection** (InsightFace) to confirm a **face is present** on the document.
- **Pass** only if: 11-digit Yemen ID found **and** face detected.

**Passport:**
- Run OCR and look for **passport-like content**: long alphanumeric lines (e.g. MRZ), or long numeric strings that could be a passport number.
- Confirm a **face** is present on the document.
- **Pass** only if: passport-like text found **and** face detected.

---

### 2.3 Not screenshot or copy (original and genuine – capture source)

**Purpose:** Reject images that are **not** a direct capture of a physical document, e.g.:
- Screenshot of a document on a screen (moire, pixel grid),
- Photocopy or flatbed scan (different texture, often flatter),
- Photo of a printed copy (often blurrier, different sharpness).

We use **three sub-checks**. All three must pass for “not screenshot or copy” to pass.

#### (a) Sharpness (Laplacian variance)

- Convert image to grayscale and compute the **Laplacian** (edge operator).
- Take the **variance** of the Laplacian image → high value means many edges (sharp), low value means blur.
- Variance is **normalized** by image size (so small vs large images are comparable).
- **Pass** if normalized sharpness is above a minimum (config: `DOC_MIN_SHARPNESS`).
- **Rejects:** Blurry images, “photo of a photo”, heavily compressed or low-quality captures.

#### (b) Moiré (FFT-based)

- Resize to a fixed size (e.g. 256×256), apply a **Hann window**, then take the **2D FFT**.
- Look at the **mid-frequency** energy relative to total energy (excluding very low and very high frequencies).
- **Screen captures** often show a **moire pattern** (interference between camera and screen), which increases mid-frequency energy.
- We compute a **score** that is **high when moiré is low** (more natural image).
- **Pass** if `score > DOC_MOIRE_THRESHOLD` (0.20).
- **Rejects:** Screenshots, photos of screens, some scanned displays.

#### (c) Texture (LBP – Local Binary Pattern)

- Compute **LBP** on the grayscale image (local texture pattern around each pixel).
- Build a histogram of LBP values and use its **variance** (or similar spread) as a “texture richness” score.
- **Real documents** and **live photos** tend to have more varied texture; **photocopies** and **flat scans** often look more uniform.
- **Pass** if texture score is above `DOC_TEXTURE_THRESHOLD` (0.08).
- **Rejects:** Very flat, uniform images (e.g. some photocopies or scans).

**Combined:** “Not screenshot or copy” **passes** only if sharpness **and** moiré **and** texture all pass. If any fails, we treat the image as possibly a photograph of a screen, a scan, or a copy.

---

### 2.4 Clear and readable

**Purpose:** Ensure the document is in focus and that we can read the key data (ID number / MRZ) with sufficient confidence.

**Logic:**
- **Sharpness:** Same Laplacian-based sharpness as above (image must not be blurry).
- **OCR:** Run OCR on the image. We require:
  - At least one **relevant field** (e.g. 11-digit ID for Yemen ID, or passport-like text for passport),
  - And OCR **confidence** for that content `>= DOC_MIN_OCR_CONFIDENCE` (0.55).
- **Pass** only if: sharpness passes **and** required text is present **and** confidence is high enough.

**Why 0.55:** Real documents often have holographic glare, slight MRZ softness, or lighting variation. A stricter threshold (e.g. 0.7) would reject many valid passports/IDs. 0.55 keeps readability requirement meaningful but allows normal capture conditions.

---

### 2.5 Fully visible (not cropped)

**Purpose:** Ensure the **whole document** is in frame and that we are not looking at a cropped or badly framed shot.

**Logic:**
- **Document boundary:** Use edge detection + contours to find the **largest quadrilateral** that looks like a document (rectangle) and whose **aspect ratio** matches the expected range:
  - Yemen ID: `DOC_ASPECT_RATIO_YEMEN_ID` (e.g. width/height between 1.3 and 1.8).
  - Passport: `DOC_ASPECT_RATIO_PASSPORT` (e.g. 0.6–1.7 so both portrait and landscape are allowed).
- If no such contour is found, we **fallback** to “the whole image is the document” **if** the image’s own aspect ratio is in that range.
- From the chosen region we get:
  - **area_ratio** = (document area) / (image area) → how much of the image is “document”.
  - **margin_ok** = whether there is a small margin between the document rectangle and the image edges (margin width/height ≥ `DOC_MIN_MARGIN_RATIO`, e.g. 0.5%).

**Pass rule (relaxed for live capture):**
- We require the document to **dominate** the frame: `area_ratio >= DOC_MIN_COVERAGE_RATIO` (0.5).
- **And** either:
  - **margin_ok** is true (enough margin), **or**
  - **area_ratio >= 0.75** (document fills most of the frame, so we accept even with very small margins).

**Why:** When the user holds the card/passport and takes a photo, the card often fills the frame and margins are tiny. Requiring a large margin would reject these. So we allow “small margin” when the document clearly dominates (≥ 75% of the image).

---

### 2.6 Not obscured

**Purpose:** Ensure the document is not covered by glare, hands, or other obstructions so that face and text are usable.

**Logic:**
- **Face:** Face detection must find a face on the document (same as “official document”).
- **Glare:** We measure how much of the image is **overexposed or saturated** (e.g. pixels near 255). If the proportion of such pixels is above a limit (e.g. 15%), we consider glare too strong and **fail**.
- **Text:** We require that OCR found the expected content (ID number or passport content).
- **Pass** only if: face present **and** glare acceptable **and** text found.

---

### 2.7 No extra objects

**Purpose:** Ensure the image is **mostly the document**, not a scene with multiple cards, phones, or other objects.

**Logic:**
- Use the same **document boundary** as in “fully visible”.
- **area_ratio** = (detected document area) / (image area).
- **Pass** if `area_ratio >= DOC_MIN_COVERAGE_RATIO` (0.5).
- **Fail** if the document occupies less than half of the image (suggesting other objects or background dominate).

---

### 2.8 Integrity (not forged or altered)

**Purpose:** Basic sanity that the document **has a face** and looks like a single, consistent document (no obvious cut-paste at this stage).

**Logic:**
- **Yemen ID / Passport:** We require that a **face is detected** on the document (same as official document). No face → fail.
- **Future:** Can add consistency checks (e.g. noise/lighting similar across regions) to flag pasted or altered areas.

---

### 2.9 Original and genuine (front and back for Yemen ID)

**Purpose:** Explicitly tie the previous checks to “this side is an **original, genuine** document; not a photograph of a screen, scan, or copy”.

**Logic (per side):**
- For **front** (and **back** if provided), we run:
  - Not screenshot or copy (sharpness + moiré + texture),
  - Sharpness,
  - Fully visible,
  - No extra objects.
- **original_and_genuine_front** passes only if **all** of these pass for the front image.
- **original_and_genuine_back** passes only if **all** pass for the back image (or we report “Back not provided” if no back image).

So “original and genuine” is a **summary** of: capture source (not screen/copy), sharpness, full visibility, and single-document dominance.

---

## 3. How the final result is decided

- **Yemen ID:**  
  Overall **pass** only if **all** of these pass:  
  resolution, official_document, not_screenshot_or_copy, clear_and_readable, fully_visible, not_obscured, no_extra_objects, integrity, original_and_genuine_front, and (if back was uploaded) original_and_genuine_back.

- **Passport:**  
  Same idea: **all** of the corresponding checks must pass (resolution, official_document, not_screenshot_or_copy, clear_and_readable, fully_visible, not_obscured, no_extra_objects, integrity).

If **any** check fails, we set `passed: false` and list the failed checks in the `error` message (e.g. “Failed: clear_and_readable, fully_visible”).

---

## 4. Config summary (where the logic is tuned)

| Config key | Value (example) | Role |
|------------|------------------|------|
| `DOC_MIN_RESOLUTION_PX` | 320 | Minimum side length in pixels; reject tiny images. |
| `DOC_MIN_SHARPNESS` | 0.02 | Minimum sharpness (normalized); reject very blurry. |
| `DOC_MOIRE_THRESHOLD` | 0.20 | Moiré score must be above this; reject screen-like images. |
| `DOC_TEXTURE_THRESHOLD` | 0.08 | Texture score must be above this; reject very flat copies. |
| `DOC_MIN_OCR_CONFIDENCE` | 0.55 | Min OCR confidence for “clear and readable”. |
| `DOC_MIN_MARGIN_RATIO` | 0.005 | Min margin (0.5%); used only when document does not fill frame. |
| `DOC_MIN_COVERAGE_RATIO` | 0.5 | Document must occupy ≥ 50% of image. |
| `DOC_ASPECT_RATIO_YEMEN_ID` | (1.3, 1.8) | Allowed width/height range for Yemen ID. |
| `DOC_ASPECT_RATIO_PASSPORT` | (0.6, 1.7) | Allowed width/height for passport (portrait or landscape). |

The **0.75** rule (allow “fully visible” when document covers ≥ 75% even with small margins) is in code: `margin_ok or area_ratio >= 0.75`.

---

## 5. Summary in one sentence

We treat the document as **original and genuine** only if: it has enough resolution and sharpness; it doesn’t look like a screenshot or copy (moire/texture); it’s fully visible and not cropped (with relaxed margins when the document fills the frame); it’s readable by OCR; it’s not obscured by glare; it dominates the frame (no extra objects); and a face is present (integrity). For Yemen ID, both front and back (when provided) must satisfy these “original and genuine” checks.
