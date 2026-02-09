"""
API 1: Document OCR & Data Consistency Check

This endpoint performs:
1. OCR text extraction from ID card images
2. Arabic-to-English name translation
3. Field-by-field comparison with user-provided data
4. Document authenticity assessment
"""
import logging
import json
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from fastapi.concurrency import run_in_threadpool

from models.v1_schemas import (
    OCRCheckResponse,
    OCRCheckMetadata,
    OCRCheckUserData,
    OCRData,
    OCRFieldData,
    DataComparisonItem,
    DocumentAuthenticity,
    ImageQuality,
    ImageQualityItem,
)
from services.ocr_service import extract_id_from_image
from services.field_comparison_service import validate_form_vs_ocr
from services.translation_service import hybrid_name_convert
from services.image_quality_service import check_id_quality
from utils.image_manager import load_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr-check", tags=["OCR Check"])


def _parse_json_form(json_str: str, model_class, field_name: str):
    """Parse JSON string into Pydantic model."""
    try:
        data = json.loads(json_str)
        return model_class(**data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in {field_name}: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse {field_name}: {str(e)}")


def _determine_match_result(user_val: Optional[str], ocr_val: Optional[str], is_match: bool) -> str:
    """Determine match result per contract: MATCH | MISMATCH | NOT_AVAILABLE."""
    if user_val is None or ocr_val is None:
        return "NOT_AVAILABLE"
    return "MATCH" if is_match else "MISMATCH"


def _determine_authenticity_status(score: float) -> str:
    """Determine authenticity status from score."""
    if score >= 0.7:
        return "VALID"
    elif score >= 0.4:
        return "SUSPICIOUS"
    return "INVALID"


@router.post("", response_model=OCRCheckResponse)
async def ocr_check_endpoint(
    request: Request,
    metadata: str = Form(..., alias="metadata", description="JSON: transactionId, documentType, countryCode"),
    user_data: str = Form(..., alias="userData", description="JSON: User-entered KYC data"),
    id_front_image: UploadFile = File(..., alias="idFrontImage", description="ID card front image"),
    id_back_image: Optional[UploadFile] = File(None, alias="idBackImage", description="ID card back image"),
):
    """
    Document OCR & Data Consistency Check (API 1 Contract)
    
    Performs OCR on ID card images, translates Arabic names,
    and compares extracted data against user-provided form data.
    """
    errors = []
    
    # Parse metadata
    meta = _parse_json_form(metadata, OCRCheckMetadata, "metadata")
    transaction_id = meta.transaction_id
    
    # Parse user data
    user = _parse_json_form(user_data, OCRCheckUserData, "userData")
    
    try:
        # Load front image
        front_bytes = await id_front_image.read()
        try:
            front_image = load_image(front_bytes)
        except ValueError:
            return OCRCheckResponse(
                transaction_id=transaction_id,
                ocr_data=OCRData(),
                document_authenticity=DocumentAuthenticity(score=0.0, status="INVALID"),
                image_quality=ImageQuality(front_image=ImageQualityItem(score=0.0, failure_reasons=["Could not decode image"])),
                errors=["Failed to load front image"]
            )
        
        # Load back image if provided
        back_image = None
        if id_back_image:
            back_bytes = await id_back_image.read()
            try:
                back_image = load_image(back_bytes)
            except ValueError:
                errors.append("Failed to load back image")
        
        # Run OCR (CPU-bound, use threadpool)
        ocr_result = await run_in_threadpool(extract_id_from_image, front_image)
        
        if "error" in ocr_result:
            errors.append(f"OCR Error: {ocr_result['error']}")
        
        # Get OCR confidence (average)
        avg_confidence = ocr_result.get("confidence", 0.8)
        
        # Build OCRData with field-level confidence
        ocr_data = OCRData(
            first_name=OCRFieldData(value=ocr_result.get("name_english", "").split()[0] if ocr_result.get("name_english") else None, confidence=avg_confidence) if ocr_result.get("name_english") else None,
            full_name=OCRFieldData(value=ocr_result.get("full_name") or ocr_result.get("name_english"), confidence=avg_confidence),
            document_number=OCRFieldData(value=ocr_result.get("extracted_id"), confidence=avg_confidence) if ocr_result.get("extracted_id") else None,
            document_issue_date=OCRFieldData(value=ocr_result.get("issue_date") or ocr_result.get("issuance_date"), confidence=avg_confidence) if ocr_result.get("issue_date") or ocr_result.get("issuance_date") else None,
            document_expiry_date=OCRFieldData(value=ocr_result.get("expiry_date"), confidence=avg_confidence) if ocr_result.get("expiry_date") else None,
            date_of_birth=OCRFieldData(value=ocr_result.get("date_of_birth"), confidence=avg_confidence) if ocr_result.get("date_of_birth") else None,
            gender=OCRFieldData(value=ocr_result.get("gender"), confidence=avg_confidence) if ocr_result.get("gender") else None,
        )
        
        # Transliterate Arabic names
        transliterated_first = None
        transliterated_second = None
        transliterated_third = None
        transliterated_family = None
        transliterated_full = None
        
        arabic_name = ocr_result.get("name_arabic")
        if arabic_name:
            try:
                translation_result = await run_in_threadpool(hybrid_name_convert, arabic_name)
                transliterated_full = translation_result.get("english", "")
                
                # Split transliterated name into parts
                name_parts = transliterated_full.split() if transliterated_full else []
                if len(name_parts) >= 1:
                    transliterated_first = name_parts[0]
                if len(name_parts) >= 2:
                    transliterated_second = name_parts[1]
                if len(name_parts) >= 3:
                    transliterated_third = name_parts[2]
                if len(name_parts) >= 4:
                    transliterated_family = name_parts[-1]  # Last name is family
            except Exception as e:
                errors.append(f"Translation error: {str(e)}")
        
        # Run field comparison
        manual_data = {
            "id_number": user.document_number,
            "full_name": user.full_name,
            "date_of_birth": user.date_of_birth,
            "gender": user.gender,
            "issue_date": user.document_issue_date,
            "expiry_date": user.document_expiry_date,
        }
        
        ocr_data_for_comparison = {
            "id_number": ocr_result.get("extracted_id"),
            "full_name": ocr_result.get("full_name") or ocr_result.get("name_english"),
            "date_of_birth": ocr_result.get("date_of_birth"),
            "gender": ocr_result.get("gender"),
            "issue_date": ocr_result.get("issue_date") or ocr_result.get("issuance_date"),
            "expiry_date": ocr_result.get("expiry_date"),
        }
        
        comparison_result = await run_in_threadpool(
            validate_form_vs_ocr,
            manual_data,
            ocr_data_for_comparison,
            avg_confidence
        )
        
        # Build dataComparison list
        data_comparison = []
        for field_result in comparison_result.get("field_results", []):
            user_val = field_result.get("user_value")
            ocr_val = field_result.get("ocr_value")
            is_match = field_result.get("match", False)
            
            data_comparison.append(DataComparisonItem(
                field_name=field_result.get("field", "unknown"),
                user_entered_value=user_val,
                ocr_extracted_value=ocr_val,
                match_result=_determine_match_result(user_val, ocr_val, is_match)
            ))
        
        # Assess document quality / authenticity
        quality_result = await run_in_threadpool(check_id_quality, front_image)
        quality_score = quality_result.get("overall_quality", 0.0)
        
        document_authenticity = DocumentAuthenticity(
            score=quality_score,
            status=_determine_authenticity_status(quality_score)
        )
        
        # Image quality
        front_quality = ImageQualityItem(
            score=quality_score,
            failure_reasons=quality_result.get("issues", [])
        )
        back_quality = None
        if back_image:
            back_result = await run_in_threadpool(check_id_quality, back_image)
            back_quality = ImageQualityItem(
                score=back_result.get("overall_quality", 0.0),
                failure_reasons=back_result.get("issues", [])
            )
        
        image_quality = ImageQuality(
            front_image=front_quality,
            back_image=back_quality
        )
        
        return OCRCheckResponse(
            transaction_id=transaction_id,
            transliterated_first_name=transliterated_first,
            transliterated_second_name=transliterated_second,
            transliterated_third_name=transliterated_third,
            transliterated_family_name=transliterated_family,
            transliterated_full_name=transliterated_full,
            ocr_data=ocr_data,
            data_comparison=data_comparison,
            document_authenticity=document_authenticity,
            image_quality=image_quality,
            errors=errors
        )
        
    except Exception as e:
        logger.exception(f"OCR Check failed: {e}")
        return OCRCheckResponse(
            transaction_id=transaction_id,
            ocr_data=OCRData(),
            document_authenticity=DocumentAuthenticity(score=0.0, status="INVALID"),
            image_quality=ImageQuality(),
            errors=[f"Unexpected error: {str(e)}"]
        )
