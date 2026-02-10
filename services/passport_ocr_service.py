"""
Passport OCR Service

Extracts data from Yemen passports using:
1. YOLO Layout Detection - For detecting all field regions
2. PaddleOCR - For reading text from detected regions
3. MRZ Parser - For parsing machine readable zone data

YOLO Classes (from classes-yemen-passport.txt):
- MRZ, passport_no, DOB, POB, expiry_date, Issue_date
- GivenName_arabic, GivenName_eng, surname_arabic, surname_eng
- Profession_arabic, Profession_eng
- Issuing_authority_arabic, Issuing_authority_eng
- country_code, type, id

Strategy:
- Use YOLO to detect ALL field regions
- OCR each detected region
- Parse MRZ for high-accuracy core fields
- Return everything detected (caller decides what to use)
"""

import cv2
import logging
import numpy as np
from typing import Dict, List, Optional

from services.ocr_service import get_ocr_service
from services.passport_mrz_parser import parse_passport_mrz, extract_mrz_from_text
from utils.image_manager import load_image
from utils.ocr_utils import ocr_image_with_padding, ocr_to_single_string, ocr_mrz_line
from utils.exceptions import ServiceError

logger = logging.getLogger(__name__)


# Passport YOLO class names (must match classes-yemen-passport.txt)
PASSPORT_CLASSES = [
    "DOB",
    "GivenName_arabic",
    "GivenName_eng",
    "Issue_date",
    "Issuing_authority_arabic",
    "Issuing_authority_eng",
    "MRZ",
    "POB",
    "Profession_arabic",
    "Profession_eng",
    "country_code",
    "expiry_date",
    "id",
    "passport_no",
    "surname_arabic",
    "surname_eng",
    "type",
]


def extract_all_fields_yolo(image: np.ndarray) -> Dict[str, any]:
    """
    Extract ALL passport fields using YOLO layout detection.
    
    Detects and OCRs every field the model can find.
    Returns a dictionary with all detected field values and per-field confidence scores.
    
    Args:
        image: Passport image (numpy array, BGR format)
        
    Returns:
        Dictionary with all detected fields, field_confidences, and metadata
    """
    from services.layout_service import get_layout_service
    
    result = {
        # Initialize all possible fields as None
        "passport_no": None,
        "given_name_arabic": None,
        "given_name_english": None,
        "surname_arabic": None,
        "surname_english": None,
        "dob": None,
        "pob": None,
        "expiry_date": None,
        "issue_date": None,
        "profession_arabic": None,
        "profession_english": None,
        "issuing_authority_arabic": None,
        "issuing_authority_english": None,
        "country_code": None,
        "doc_type": None,
        # MRZ handled separately
        "mrz_fields": [],
        "detected_labels": [],
        # Per-field confidence scores
        "field_confidences": {},
    }
    
    service = get_layout_service()
    if not service.is_available("yemen_passport"):
        logger.warning("YOLO passport model not available")
        return result
    
    # Get all detections (return_all=True for multiple MRZ lines)
    fields = service.detect_layout(image, "yemen_passport", return_all=True)
    
    if not fields:
        logger.debug("No fields detected by YOLO")
        return result
    
    result["detected_labels"] = list(fields.keys())
    logger.info(f"YOLO detected labels: {result['detected_labels']}")
    
    ocr = get_ocr_service()
    
    # Map YOLO class names to our result keys and OCR language
    # Format: "yolo_class": ("result_key", "ocr_lang")
    class_to_key = {
        "passport_no": ("passport_no", "en"),
        "GivenName_arabic": ("given_name_arabic", "ar"),
        "GivenName_eng": ("given_name_english", "en"),
        "surname_arabic": ("surname_arabic", "ar"),
        "surname_eng": ("surname_english", "en"),
        "DOB": ("dob", "en"),
        "POB": ("pob", "ar"),  # Place of birth often in Arabic
        "expiry_date": ("expiry_date", "en"),
        "Issue_date": ("issue_date", "en"),
        "Profession_arabic": ("profession_arabic", "ar"),
        "Profession_eng": ("profession_english", "en"),
        "Issuing_authority_arabic": ("issuing_authority_arabic", "ar"),
        "Issuing_authority_eng": ("issuing_authority_english", "en"),
        "country_code": ("country_code", "en"),
        "type": ("doc_type", "en"),
    }
    
    # Process each detected field
    for label, detected_list in fields.items():
        # Handle MRZ separately (needs special processing)
        if label == "MRZ":
            if isinstance(detected_list, list):
                result["mrz_fields"] = detected_list
            else:
                result["mrz_fields"] = [detected_list]
            continue
        
        # Skip unknown labels
        if label not in class_to_key:
            continue
        
        key, lang = class_to_key[label]
        
        # Handle list of detections: pick the one with highest YOLO confidence
        if isinstance(detected_list, list) and len(detected_list) > 0:
            # Sort by confidence and take the best one
            detection = max(detected_list, key=lambda d: d.confidence)
        else:
            detection = detected_list
        
        # OCR the cropped region with correct language
        try:
            text, confidence = ocr_to_single_string(detection.crop, ocr, lang=lang)
            if text:
                result[key] = text
                result["field_confidences"][key] = float(confidence)
        except Exception as e:
            logger.warning(f"OCR failed for {label}: {e}")
    
    return result



def extract_mrz_from_fields(mrz_fields: List, ocr) -> Optional[Dict]:
    """
    Extract and parse MRZ from detected MRZ field regions.
    
    Expects exactly 2 MRZ detections (one per line), sorted by Y coordinate.
    
    Args:
        mrz_fields: List of LayoutField objects for MRZ detections (expects 2)
        ocr: OCR service instance
        
    Returns:
        Parsed MRZ data or None
    """
    if not mrz_fields or len(mrz_fields) < 2:
        logger.warning(f"MRZ extraction requires 2 detections, got {len(mrz_fields) if mrz_fields else 0}")
        return None
    
    # Sort by Y-coordinate (top to bottom)
    mrz_fields_sorted = sorted(mrz_fields, key=lambda f: f.box[1])
    
    line1_field = mrz_fields_sorted[0]  # Top = Line 1
    line2_field = mrz_fields_sorted[1]  # Bottom = Line 2
    
    mrz_lines = []
    
    # OCR Line 1 (with MRZ-specific preprocessing: upscale + binarization)
    txt1, conf1 = ocr_mrz_line(line1_field.crop, ocr)
    txt1 = txt1.upper()
    logger.debug(f"MRZ Line 1 OCR: '{txt1}' (conf: {conf1:.2f})")
    if txt1:
        mrz_lines.append(txt1)
    
    # OCR Line 2 (with MRZ-specific preprocessing: upscale + binarization)
    txt2, conf2 = ocr_mrz_line(line2_field.crop, ocr)
    txt2 = txt2.upper()
    logger.debug(f"MRZ Line 2 OCR: '{txt2}' (conf: {conf2:.2f})")
    if txt2:
        mrz_lines.append(txt2)
    
    # Need both lines
    if len(mrz_lines) != 2:
        logger.warning(f"MRZ OCR failed: got {len(mrz_lines)} lines, expected 2")
        return None
    
    # Clean: ensure exactly 44 characters per line
    cleaned_mrz = []
    for line in mrz_lines:
        if len(line) < 44:
            line = line + '<' * (44 - len(line))
        elif len(line) > 44:
            line = line[:44]
        cleaned_mrz.append(line)
    
    # Parse MRZ
    mrz_data = parse_passport_mrz(cleaned_mrz)
    if mrz_data.get("success"):
        mrz_data["mrz_line1"] = cleaned_mrz[0]
        mrz_data["mrz_line2"] = cleaned_mrz[1]
        return mrz_data
    
    return None


def extract_passport_data(image_input) -> Dict:
    """
    Main function: Extract all data from Yemen passport using YOLO.
    
    Process:
    1. Load image (if path provided)
    2. Use YOLO to detect ALL field regions (MRZ, names, dates, etc.)
    3. OCR each detected region
    4. Parse MRZ for high-accuracy core fields
    5. Merge YOLO fields with MRZ parsed data (MRZ takes priority)
    
    Args:
        image_input: Either a file path (str) or numpy array (BGR image)
        
    Returns:
        Complete passport data dictionary
    """
    try:
        # Handle both file path and numpy array input
        try:
            # Handle both file path and numpy array input
            if isinstance(image_input, np.ndarray):
                image = image_input
            else:
                image = load_image(image_input)
        except ValueError as e:
            raise ServiceError(f"Failed to load image: {str(e)}", code="IMAGE_LOAD_FAILED")

        if image is None:
            raise ServiceError("Failed to load image", code="IMAGE_LOAD_FAILED")
        
        # Extract ALL fields using YOLO
        yolo_fields = extract_all_fields_yolo(image)
        
        # Parse MRZ if detected
        ocr = get_ocr_service()
        mrz_data = None
        if yolo_fields.get("mrz_fields"):
            mrz_data = extract_mrz_from_fields(yolo_fields["mrz_fields"], ocr)
        
        # Build final response
        # Priority: MRZ parsed data > YOLO OCR fields
        final_data = {
            "success": True,
            "id_type": "yemen_passport",
            "extraction_method": "YOLO_FULL",
            
            # Core fields (MRZ priority if available)
            "passport_number": (mrz_data.get("passport_number") if mrz_data else None) or yolo_fields.get("passport_no"),
            "given_names": (mrz_data.get("given_names") if mrz_data else None) or yolo_fields.get("given_name_english"),
            "surname": (mrz_data.get("surname") if mrz_data else None) or yolo_fields.get("surname_english"),
            "name_english": None,  # Will be constructed below
            "date_of_birth": (mrz_data.get("date_of_birth") if mrz_data else None) or yolo_fields.get("dob"),
            "gender": mrz_data.get("gender") if mrz_data else None,
            "expiry_date": (mrz_data.get("expiry_date") if mrz_data else None) or yolo_fields.get("expiry_date"),
            "nationality": mrz_data.get("nationality") if mrz_data else None,
            "country_code": (mrz_data.get("issuing_country") if mrz_data else None) or yolo_fields.get("country_code"),
            
            # Arabic name fields (YOLO only - not in MRZ)
            "given_name_arabic": yolo_fields.get("given_name_arabic"),
            "surname_arabic": yolo_fields.get("surname_arabic"),
            
            # Supplementary fields (YOLO only - not in MRZ)
            "place_of_birth": yolo_fields.get("pob"),
            "issuance_date": yolo_fields.get("issue_date"),
            "issuing_authority": yolo_fields.get("issuing_authority_english"),
            "issuing_authority_arabic": yolo_fields.get("issuing_authority_arabic"),
            "profession": yolo_fields.get("profession_english"),
            "profession_arabic": yolo_fields.get("profession_arabic"),
            
            # MRZ metadata
            "mrz_valid": mrz_data.get("mrz_valid", False) if mrz_data else False,
            "mrz_confidence": mrz_data.get("confidence", 0.0) if mrz_data else 0.0,
            "mrz_raw": {
                "line1": mrz_data.get("mrz_line1") if mrz_data else None,
                "line2": mrz_data.get("mrz_line2") if mrz_data else None,
            },
            
            # Debug info
            "detected_labels": yolo_fields.get("detected_labels", []),
        }
        
        # Build field_confidences with API-compatible names
        yolo_conf = yolo_fields.get("field_confidences", {})
        mrz_conf = mrz_data.get("confidence", 0.95) if mrz_data else 0.0
        final_data["field_confidences"] = {
            "passport_number": mrz_conf if mrz_data else yolo_conf.get("passport_no", 0.0),
            "given_names": mrz_conf if mrz_data else yolo_conf.get("given_name_english", 0.0),
            "surname": mrz_conf if mrz_data else yolo_conf.get("surname_english", 0.0),
            "date_of_birth": mrz_conf if mrz_data else yolo_conf.get("dob", 0.0),
            "expiry_date": mrz_conf if mrz_data else yolo_conf.get("expiry_date", 0.0),
            "issuance_date": yolo_conf.get("issue_date", 0.0),
            "gender": mrz_conf if mrz_data else 0.0,
            "place_of_birth": yolo_conf.get("pob", 0.0),
            "name_arabic": max(yolo_conf.get("given_name_arabic", 0.0), yolo_conf.get("surname_arabic", 0.0)),
        }

        
        # Construct full English name
        given = final_data.get("given_names") or ""
        surname = final_data.get("surname") or ""
        final_data["name_english"] = f"{given} {surname}".strip() or None
        
        # Check if we got minimum required data
        if not final_data["passport_number"] and not mrz_data:
            raise ServiceError(
                "Could not extract passport data. No MRZ or passport number detected.",
                code="PASSPORT_DATA_MISSING",
                details={
                    "detected_labels": yolo_fields.get("detected_labels", []),
                    "suggestion": "Please retake the photo. Ensure passport is flat, well-lit, and all text is visible."
                }
            )
        
        return final_data
        
    except ServiceError:
        raise  # Re-raise our custom exceptions
    except Exception as e:
        logger.exception("Passport extraction failed")
        raise ServiceError(
            f"Passport extraction failed: {str(e)}",
            code="PASSPORT_EXTRACTION_FAILED"
        )


def validate_passport_data(passport_data: Dict) -> Dict:
    """
    Validate extracted passport data.
    
    Checks:
    - Required fields present
    - Date formats valid
    - MRZ checksums valid
    
    Args:
        passport_data: Extracted passport data
        
    Returns:
        Validation result with issues
    """
    issues = []
    
    # Check required fields
    required_fields = [
        "passport_number", "name_english", "date_of_birth",
        "gender", "expiry_date", "nationality"
    ]
    
    for field in required_fields:
        if not passport_data.get(field):
            issues.append(f"Missing required field: {field}")
    
    # Check MRZ validity
    if not passport_data.get("mrz_valid"):
        issues.append("MRZ checksum validation failed")
    
    # Check dates
    dob = passport_data.get("date_of_birth")
    expiry = passport_data.get("expiry_date")
    
    if dob and expiry:
        try:
            from datetime import datetime
            dob_date = datetime.strptime(dob, "%Y-%m-%d")
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
            
            if expiry_date <= datetime.now():
                issues.append("Passport is expired")
            
            if dob_date >= datetime.now():
                issues.append("Date of birth is in the future")
                
        except ValueError:
            issues.append("Invalid date format")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "confidence": passport_data.get("mrz_confidence", 0.0)
    }
