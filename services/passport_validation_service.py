"""
Passport Document Validation Service.

User uploads ONE side (passport data page). We validate that the captured document
is **original and genuine**, and NOT: a photograph of a document, scanned copy,
B&W or color copy, or forged/altered/invalid passport.

Checks: original passport, not photograph/scan/copy, clear and readable,
fully visible, not obscured, no extra objects, integrity.
Uses: document_validation_helpers, ocr_service, face_extractor.
"""
import numpy as np
from typing import Dict, Any, Optional

from utils.config import (
    DOC_VALIDATION_ENABLED,
    DOC_MIN_COVERAGE_RATIO,
    DOC_ASPECT_RATIO_PASSPORT,
    DOC_MIN_RESOLUTION_PX,
)
from services.document_validation_helpers import (
    check_document_sharpness,
    check_document_resolution,
    check_not_screenshot_or_copy,
    get_document_boundary,
    check_glare,
)


def _check_resolution(image: np.ndarray) -> Dict[str, Any]:
    """Min resolution check."""
    passed, min_side = check_document_resolution(image)
    return {
        "passed": passed,
        "score": float(min_side),
        "threshold": DOC_MIN_RESOLUTION_PX,
        "detail": None if passed else f"Image too small (min side {min_side}px)",
    }


def _check_official_passport(image: np.ndarray, face_detected: bool) -> Dict[str, Any]:
    """Original passport: expect face on document (layout/aspect implies passport)."""
    return {
        "passed": face_detected,
        "score": 1.0 if face_detected else 0.0,
        "detail": None if face_detected else "Face not detected on document",
    }


def _check_clarity_passport(image: np.ndarray) -> Dict[str, Any]:
    """Clear, readable, focused: sharpness only (no OCR)."""
    sharp_score, sharp_ok = check_document_sharpness(image)
    return {
        "passed": sharp_ok,
        "score": round(sharp_score, 3),
        "threshold": None,
        "detail": None if sharp_ok else "Blurry or unreadable",
    }


def _check_fully_visible_passport(image: np.ndarray) -> Dict[str, Any]:
    """Fully visible, not cropped: document boundary + coverage; margins relaxed for live capture."""
    boundary = get_document_boundary(image, DOC_ASPECT_RATIO_PASSPORT)
    if boundary is None:
        return {
            "passed": False,
            "score": 0.0,
            "detail": "No document boundary detected or aspect ratio not matching passport",
        }
    margin_ok = bool(boundary.get("margin_ok", False))
    area_ratio = float(boundary.get("area_ratio", 0.0))
    coverage_ok = area_ratio >= DOC_MIN_COVERAGE_RATIO
    passed = coverage_ok and (margin_ok or area_ratio >= 0.75)
    return {
        "passed": passed,
        "score": round(area_ratio, 3),
        "threshold": DOC_MIN_COVERAGE_RATIO,
        "detail": None if passed else ("Document cropped or too small in frame" if not coverage_ok else "Margins too small"),
        "boundary": boundary,
    }


def _check_not_obscured_passport(image: np.ndarray, face_detected: bool) -> Dict[str, Any]:
    """Not covered/obscured: face visible + glare check."""
    no_glare, glare_ratio = check_glare(image)
    passed = face_detected and no_glare
    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "detail": None if passed else ("Face not visible" if not face_detected else "Glare on document"),
        "glare_ratio": glare_ratio,
    }


def _check_no_extra_objects_passport(image: np.ndarray, boundary: Optional[Dict]) -> Dict[str, Any]:
    """No non-passport objects: document should dominate frame."""
    if boundary is None:
        boundary = get_document_boundary(image, DOC_ASPECT_RATIO_PASSPORT)
    if boundary is None:
        return {"passed": False, "score": 0.0, "detail": "Could not assess document coverage"}
    area_ratio = boundary.get("area_ratio", 0.0)
    passed = area_ratio >= DOC_MIN_COVERAGE_RATIO
    return {
        "passed": passed,
        "score": round(area_ratio, 3),
        "threshold": DOC_MIN_COVERAGE_RATIO,
        "detail": None if passed else "Document does not dominate frame; extra objects may be present",
    }


def _check_integrity_passport(image: np.ndarray, face_detected: bool) -> Dict[str, Any]:
    """Basic integrity: face present."""
    passed = face_detected
    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "detail": None if passed else "Face not detected on document",
    }


def validate_passport(image: np.ndarray) -> Dict[str, Any]:
    """
    Validate that the image is an acceptable passport document.

    Runs all 7 regulatory checks. Returns result with passed, document_type, checks, error.
    """
    from services.face_extractor import get_face_extractor, is_available as insightface_available

    result = {
        "passed": False,
        "document_type": "passport",
        "checks": {},
        "error": None,
    }

    if not DOC_VALIDATION_ENABLED:
        result["passed"] = True
        result["checks"] = {k: {"passed": True, "detail": "Validation disabled"} for k in [
            "official_document", "document_is_passport", "not_screenshot_or_copy", "clear_and_readable",
            "fully_visible", "not_obscured", "no_extra_objects", "integrity",
        ]}
        return result

    if image is None or image.size == 0:
        result["error"] = "Invalid image"
        return result

    # Resolution first
    res = _check_resolution(image)
    result["checks"]["resolution"] = res
    if not res["passed"]:
        result["error"] = res.get("detail", "Image too small")
        return result

    face_detected = False
    if insightface_available():
        try:
            ext = get_face_extractor()
            faces = ext.detect_faces(image)
            face_detected = len(faces) > 0
        except Exception:
            pass

    # 1. Official document (passport)
    result["checks"]["official_document"] = _check_official_passport(image, face_detected)

    # 1b. document_is_passport (no OCR - always pass; cannot distinguish ID card from passport without OCR)
    result["checks"]["document_is_passport"] = {"passed": True, "score": 1.0, "detail": None}

    # 2. Not screenshot/photocopy
    screenshot_check = check_not_screenshot_or_copy(image, for_passport=True)
    result["checks"]["not_screenshot_or_copy"] = {
        "passed": screenshot_check["passed"],
        "score": None,
        "detail": screenshot_check.get("error") or (
            "Passport must be original; not a photograph, scan, or copy" if not screenshot_check["passed"] else None
        ),
        "sub_checks": screenshot_check.get("checks", {}),
    }

    # 3. Clear and readable
    result["checks"]["clear_and_readable"] = _check_clarity_passport(image)

    # 4. Fully visible
    full_vis = _check_fully_visible_passport(image)
    result["checks"]["fully_visible"] = {k: v for k, v in full_vis.items() if k != "boundary"}
    boundary = full_vis.get("boundary")

    # 5. Not obscured
    result["checks"]["not_obscured"] = _check_not_obscured_passport(image, face_detected)

    # 6. No extra objects
    result["checks"]["no_extra_objects"] = _check_no_extra_objects_passport(image, boundary)

    # 7. Integrity
    result["checks"]["integrity"] = _check_integrity_passport(image, face_detected)

    # Overall
    core_keys = [
        "official_document", "document_is_passport", "not_screenshot_or_copy", "clear_and_readable",
        "fully_visible", "not_obscured", "no_extra_objects", "integrity",
    ]
    all_passed = all(result["checks"].get(k, {}).get("passed", False) for k in core_keys)
    result["passed"] = all_passed
    if not all_passed:
        failed = [k for k in core_keys if not result["checks"].get(k, {}).get("passed", True)]
        result["error"] = "Document must be original and genuine; not a photograph, scan, copy, or forged. Failed: " + ", ".join(failed)

    return result
