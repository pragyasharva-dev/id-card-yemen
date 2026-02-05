"""Document validation endpoints (Yemen ID, Passport)."""
import logging
from fastapi import APIRouter, UploadFile, File

from models.schemas import DocumentValidationResult
from utils.image_manager import load_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Document Validation"])


def _sanitize_checks_for_json(checks: dict) -> dict:
    """Convert numpy/types so response is JSON-serializable; ensure 'passed' is bool."""
    out = {}
    for k, v in checks.items():
        if isinstance(v, dict):
            out[k] = _sanitize_checks_for_json(v)
        elif k == "passed" and v in (0, 1, True, False):
            out[k] = bool(v)
        elif hasattr(v, "item"):  # numpy scalar
            out[k] = float(v) if hasattr(v, "item") else v
        elif isinstance(v, (list, tuple)) and v and hasattr(v[0], "item"):
            out[k] = [float(x) if hasattr(x, "item") else x for x in v]
        else:
            out[k] = v
    return out


@router.post("/validate-yemen-id", response_model=DocumentValidationResult)
async def validate_yemen_id_endpoint(
    id_card_front: UploadFile = File(..., description="Yemen ID card front side"),
    id_card_back: UploadFile = File(None, description="Yemen ID card back side (recommended; both sides validated for original/genuine)"),
):
    """
    Validate that the captured ID card (front and back) is **original and genuine**.

    User must upload **front**; **back** is recommended. Rejects: photographs of documents,
    scanned copies, B&W or color copies, forged/altered/invalid IDs.
    """
    try:
        from services.yemen_id_validation_service import validate_yemen_id
        front_bytes = await id_card_front.read()
        if not front_bytes:
            return DocumentValidationResult(
                passed=False,
                document_type="yemen_id",
                checks={},
                error="Empty front image"
            )
        front_img = load_image(front_bytes)
        back_img = None
        if id_card_back:
            back_bytes = await id_card_back.read()
            if back_bytes:
                back_img = load_image(back_bytes)
        result = validate_yemen_id(front_img, back_img)
        checks = _sanitize_checks_for_json(result.get("checks") or {})
        checks_back = None
        if result.get("checks_back"):
            checks_back = _sanitize_checks_for_json(result["checks_back"])
        return DocumentValidationResult(
            passed=bool(result.get("passed", False)),
            document_type=str(result.get("document_type", "yemen_id")),
            checks=checks,
            checks_back=checks_back,
            error=result.get("error")
        )
    except Exception as e:
        logger.exception("validate-yemen-id failed")
        return DocumentValidationResult(
            passed=False,
            document_type="yemen_id",
            checks={},
            error=str(e)
        )


@router.post("/validate-passport", response_model=DocumentValidationResult)
async def validate_passport_endpoint(
    image: UploadFile = File(..., description="Passport document image")
):
    """
    Validate that the captured image is an acceptable passport document.

    Runs all 7 regulatory checks: original passport, not screenshot/photocopy,
    clear and readable, fully visible, not obscured, no extra objects, integrity.
    """
    try:
        from services.passport_validation_service import validate_passport
        image_bytes = await image.read()
        if not image_bytes:
            return DocumentValidationResult(
                passed=False,
                document_type="passport",
                checks={},
                error="Empty image file"
            )
        img = load_image(image_bytes)
        result = validate_passport(img)
        checks = _sanitize_checks_for_json(result.get("checks") or {})
        return DocumentValidationResult(
            passed=bool(result.get("passed", False)),
            document_type=str(result.get("document_type", "passport")),
            checks=checks,
            error=result.get("error")
        )
    except Exception as e:
        logger.exception("validate-passport failed")
        return DocumentValidationResult(
            passed=False,
            document_type="passport",
            checks={},
            error=str(e)
        )
