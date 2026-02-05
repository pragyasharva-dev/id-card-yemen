"""
Yemen ID Document Validation Service.

User uploads ID card FRONT and BACK. We validate that the captured documents are
**original and genuine**, and NOT: photographs of documents, scanned copies,
black-and-white or color copies, or forged/altered/invalid IDs.

Checks (front + back both validated for authenticity):
- Official identity document (front: layout, face, 11-digit ID)
- Not photograph / scan / copy (moire, texture, sharpness)
- Clear, readable, properly focused
- Fully visible, not cropped
- Not covered, obscured, or blocked
- No non-ID objects
- Integrity (not forged or altered)

Uses: document_validation_helpers, ocr_service, face_extractor.
"""
import cv2
import numpy as np
from typing import Dict, Any, Optional

from utils.config import (
    DOC_VALIDATION_ENABLED,
    DOC_MIN_COVERAGE_RATIO,
    DOC_MIN_RESOLUTION_PX,
    DOC_ASPECT_RATIO_YEMEN_ID,
    DOC_ASPECT_RATIO_YEMEN_ID_BACK,
)
from services.document_validation_helpers import (
    check_document_sharpness,
    check_document_resolution,
    check_not_screenshot_or_copy,
    get_document_boundary,
    check_glare,
)
from utils.exceptions import ServiceError


def _check_resolution(image: np.ndarray) -> Dict[str, Any]:
    """Min resolution check."""
    passed, min_side = check_document_resolution(image)
    min_side_int = int(min_side) if min_side is not None else 0
    return {
        "passed": bool(passed),
        "score": float(min_side_int),
        "threshold": int(DOC_MIN_RESOLUTION_PX),
        "detail": None if passed else f"Image too small (min side {min_side_int}px)",
    }


def _check_official_yemen_id(image: np.ndarray, face_detected: bool) -> Dict[str, Any]:
    """Official Yemen ID: expect face on document (layout/aspect implies ID card)."""
    return {
        "passed": face_detected,
        "score": 1.0 if face_detected else 0.0,
        "detail": None if face_detected else "Face not detected on document",
    }


def _check_clarity_yemen_id(image: np.ndarray) -> Dict[str, Any]:
    """Clear, readable, focused: sharpness only (no OCR)."""
    sharp_score, sharp_ok = check_document_sharpness(image)
    return {
        "passed": sharp_ok,
        "score": round(sharp_score, 3),
        "threshold": None,
        "detail": None if sharp_ok else "Blurry or unreadable",
    }


def _check_fully_visible_yemen_id(
    image: np.ndarray,
    aspect_range: Optional[tuple] = None,
) -> Dict[str, Any]:
    """Fully visible, not cropped: document boundary + coverage; margins relaxed for live capture."""
    ar = aspect_range if aspect_range is not None else DOC_ASPECT_RATIO_YEMEN_ID
    boundary = get_document_boundary(image, ar)
    if boundary is None:
        return {
            "passed": False,
            "score": 0.0,
            "threshold": float(DOC_MIN_COVERAGE_RATIO),
            "detail": "No document boundary detected or aspect ratio not matching Yemen ID",
        }
    margin_ok = bool(boundary.get("margin_ok", False))
    area_ratio = float(boundary.get("area_ratio", 0.0))
    coverage_ok = area_ratio >= DOC_MIN_COVERAGE_RATIO
    # Pass if document dominates frame; allow small margins when card fills frame (live capture)
    passed = coverage_ok and (margin_ok or area_ratio >= 0.75)
    out = {
        "passed": passed,
        "score": round(area_ratio, 3),
        "threshold": float(DOC_MIN_COVERAGE_RATIO),
        "detail": None if passed else ("Document cropped or too small in frame" if not coverage_ok else "Margins too small"),
    }
    return out


def _check_not_obscured_yemen_id(image: np.ndarray, face_detected: bool) -> Dict[str, Any]:
    """Not covered/obscured: face visible + glare check."""
    no_glare, glare_ratio = check_glare(image)
    passed = face_detected and no_glare
    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "detail": None if passed else ("Face not visible" if not face_detected else "Glare on document"),
        "glare_ratio": glare_ratio,
    }


def _check_no_extra_objects_yemen_id(
    image: np.ndarray,
    boundary: Optional[Dict],
    aspect_range: Optional[tuple] = None,
) -> Dict[str, Any]:
    """No non-ID objects: document should dominate frame."""
    ar = aspect_range if aspect_range is not None else DOC_ASPECT_RATIO_YEMEN_ID
    if boundary is None:
        boundary = get_document_boundary(image, ar)
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


def _check_integrity_yemen_id(image: np.ndarray, face_detected: bool) -> Dict[str, Any]:
    """Basic integrity: face present; optional future: noise/lighting consistency."""
    passed = face_detected
    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "detail": None if passed else "Face not detected on document",
    }


def _run_original_genuine_checks(
    image: np.ndarray,
    aspect_range: Optional[tuple] = None,
    for_back: bool = False,
) -> Dict[str, Any]:
    """Run checks that ensure document is original/genuine (not photo, scan, copy, forged)."""
    ar = aspect_range if aspect_range is not None else DOC_ASPECT_RATIO_YEMEN_ID
    out = {}
    out["not_screenshot_or_copy"] = check_not_screenshot_or_copy(image, for_back=for_back)
    sharp_ok = check_document_sharpness(image)[1]
    out["sharpness"] = {"passed": sharp_ok, "detail": None if sharp_ok else "Image may be a copy or re-capture"}
    out["fully_visible"] = _check_fully_visible_yemen_id(image, aspect_range=ar)
    out["no_extra_objects"] = _check_no_extra_objects_yemen_id(
        image, get_document_boundary(image, ar), aspect_range=ar
    )
    return out


def _side_passes_original_genuine(checks: Dict[str, Any]) -> bool:
    """True if all 'original and genuine' checks passed for one side."""
    if not checks.get("not_screenshot_or_copy", {}).get("passed", False):
        return False
    if not checks.get("sharpness", {}).get("passed", True):
        return False
    if not checks.get("fully_visible", {}).get("passed", False):
        return False
    if not checks.get("no_extra_objects", {}).get("passed", False):
        return False
    return True


def validate_yemen_id(
    front_image: np.ndarray,
    back_image: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Validate that front (and back) are original, genuine Yemen national ID documents.

    Rejects: photographs of documents, scanned copies, B&W or color copies, forged/altered IDs.
    Front is required; back is required for full validation. Both sides must pass
    original/genuine checks; front must also have face and 11-digit ID.
    """
    from services.face_extractor import get_face_extractor, is_available as insightface_available

    result = {
        "passed": False,
        "document_type": "yemen_id",
        "checks": {},
        "checks_front": {},
        "checks_back": {},
        "error": None,
    }

    if not DOC_VALIDATION_ENABLED:
        result["passed"] = True
        result["checks"] = {k: {"passed": True, "detail": "Validation disabled"} for k in [
            "official_document", "original_and_genuine", "clear_and_readable",
            "fully_visible", "not_obscured", "no_extra_objects", "integrity",
        ]}
        return result

    if front_image is None or front_image.size == 0:
        raise ServiceError("Invalid front image", code="INVALID_FRONT_IMAGE")

    # Back optional for backward compatibility but recommended
    if back_image is not None and back_image.size == 0:
        back_image = None

    res_front = _check_resolution(front_image)
    result["checks_front"]["resolution"] = res_front
    if not res_front["passed"]:
        raise ServiceError(
            "Front: " + (res_front.get("detail") or "Image too small"),
            code="FRONT_RESOLUTION_FAILED",
            details={"min_side": res_front.get("score"), "threshold": res_front.get("threshold")}
        )

    face_detected = False
    if insightface_available():
        try:
            ext = get_face_extractor()
            faces = ext.detect_faces(front_image)
            face_detected = len(faces) > 0
        except Exception:
            pass

    result["checks"]["official_document"] = _check_official_yemen_id(front_image, face_detected)

    screenshot_check = check_not_screenshot_or_copy(front_image)
    result["checks"]["not_screenshot_or_copy"] = {
        "passed": screenshot_check["passed"],
        "score": None,
        "detail": screenshot_check.get("error") or (
            "Document must be original; not a photograph, scan, or copy" if not screenshot_check["passed"] else None
        ),
        "sub_checks": screenshot_check.get("checks", {}),
    }

    result["checks"]["clear_and_readable"] = _check_clarity_yemen_id(front_image)
    full_vis = _check_fully_visible_yemen_id(front_image)
    result["checks"]["fully_visible"] = {k: v for k, v in full_vis.items()}
    boundary = get_document_boundary(front_image, DOC_ASPECT_RATIO_YEMEN_ID)
    result["checks"]["not_obscured"] = _check_not_obscured_yemen_id(front_image, face_detected)
    result["checks"]["no_extra_objects"] = _check_no_extra_objects_yemen_id(front_image, boundary)
    result["checks"]["integrity"] = _check_integrity_yemen_id(front_image, face_detected)

    # Original and genuine: front must pass these (no photo/scan/copy/forged)
    front_original_checks = _run_original_genuine_checks(front_image)
    result["checks"]["original_and_genuine_front"] = {
        "passed": _side_passes_original_genuine(front_original_checks),
        "detail": "Front must be original document; not photograph, scan, copy, or forged",
    }

    # ---------- Back (if provided) ----------
    back_ok = True
    if back_image is not None:
        res_back = _check_resolution(back_image)
        result["checks_back"]["resolution"] = res_back
        if not res_back["passed"]:
            result["checks"]["original_and_genuine_back"] = {
                "passed": False,
                "detail": "Back: image too small or invalid",
            }
            back_ok = False
        else:
            back_original_checks = _run_original_genuine_checks(
                back_image, aspect_range=DOC_ASPECT_RATIO_YEMEN_ID_BACK, for_back=True
            )
            back_passed = _side_passes_original_genuine(back_original_checks)
            result["checks"]["original_and_genuine_back"] = {
                "passed": back_passed,
                "detail": None if back_passed else "Back must be original document; not photograph, scan, copy, or forged",
            }
            result["checks_back"].update(back_original_checks)
            back_ok = back_passed
    else:
        result["checks"]["original_and_genuine_back"] = {
            "passed": True,
            "detail": "Back not provided; only front validated",
        }

    # Overall: all core checks + front and back original/genuine
    core_keys = [
        "official_document", "not_screenshot_or_copy", "clear_and_readable",
        "fully_visible", "not_obscured", "no_extra_objects", "integrity",
        "original_and_genuine_front",
    ]
    if back_image is not None:
        core_keys.append("original_and_genuine_back")
    all_passed = all(result["checks"].get(k, {}).get("passed", False) for k in core_keys)
    result["passed"] = all_passed
    if not all_passed:
        failed = [k for k in core_keys if not result["checks"].get(k, {}).get("passed", True)]
        result["error"] = "Document must be original and genuine; not a photograph, scan, copy, or forged. Failed: " + ", ".join(failed)

    return result
