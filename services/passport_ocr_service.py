"""
Passport OCR Service

Extracts data from Yemen passports using two methods:
1. MRZ (Machine Readable Zone) - Primary, 99% accuracy (using PassportEye)
2. Visual OCR (Bilingual English + Arabic) - Backup for non-MRZ fields

Strategy:
- Extract MRZ using PassportEye (robust detection)
- Use OCR for fields not in MRZ (place of birth, occupation, address)
- Cross-validate and merge results with MRZ priority
"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
import os
import tempfile

from services.ocr_service import get_ocr_service
from services.passport_mrz_parser import parse_passport_mrz, extract_mrz_from_text
from utils.image_manager import load_image


def extract_mrz_with_passporteye(image: np.ndarray) -> Optional[Dict]:
    """
    Extract MRZ using PassportEye library.
    
    PassportEye provides robust MRZ detection that handles:
    - Rotated/skewed images
    - Various lighting conditions
    - Different passport types
    
    Args:
        image: Passport image (numpy array)
        
    Returns:
        Dictionary with MRZ data or None if not found
    """
    try:
        from passporteye import read_mrz
        
        # Save image to temp file (PassportEye requires file path)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            cv2.imwrite(tmp.name, image)
            tmp_path = tmp.name
        
        try:
            # Use PassportEye to detect and read MRZ
            mrz = read_mrz(tmp_path)
            
            if mrz is None:
                return None
            
            # Convert to our format
            mrz_data = mrz.to_dict()
            
            # Build MRZ lines for our parser
            mrz_string = mrz.aux.get('raw_text', '')
            mrz_lines = [line for line in mrz_string.split('\n') if len(line) >= 40]
            
            return {
                "success": True,
                "passport_number": mrz_data.get('number'),
                "surname": mrz_data.get('surname'),
                "given_names": mrz_data.get('names'),
                "full_name_english": f"{mrz_data.get('names', '')} {mrz_data.get('surname', '')}".strip(),
                "nationality": mrz_data.get('nationality'),
                "issuing_country": mrz_data.get('country'),
                "date_of_birth": format_mrz_date(mrz_data.get('date_of_birth')),
                "expiry_date": format_mrz_date(mrz_data.get('expiration_date')),
                "gender": 'Male' if mrz_data.get('sex') == 'M' else 'Female' if mrz_data.get('sex') == 'F' else None,
                "mrz_valid": mrz_data.get('valid_score', 0) > 50,
                "confidence": min(mrz_data.get('valid_score', 0) / 100, 0.99),
                "mrz_line1": mrz_lines[0] if len(mrz_lines) > 0 else None,
                "mrz_line2": mrz_lines[1] if len(mrz_lines) > 1 else None,
                "method": "passporteye"
            }
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except ImportError:
        # PassportEye not installed, return None to use fallback
        return None
    except Exception as e:
        # PassportEye failed, return None to use fallback
        print(f"PassportEye error: {e}")
        return None


def format_mrz_date(date_str: str) -> Optional[str]:
    """
    Format MRZ date (YYMMDD) to ISO format (YYYY-MM-DD).
    
    Args:
        date_str: Date in YYMMDD format
        
    Returns:
        Date in YYYY-MM-DD format or None
    """
    if not date_str or len(date_str) != 6:
        return None
    
    try:
        yy = int(date_str[0:2])
        mm = date_str[2:4]
        dd = date_str[4:6]
        
        # Determine century
        yyyy = 2000 + yy if yy <= 40 else 1900 + yy
        
        return f"{yyyy}-{mm}-{dd}"
    except (ValueError, IndexError):
        return None


def extract_mrz_region_fallback(image: np.ndarray) -> Optional[Tuple[np.ndarray, List[str]]]:
    """
    Fallback: Extract MRZ region using pixel-based method.
    
    Used when PassportEye is not available or fails.
    MRZ is typically in bottom 25% of passport.
    
    Args:
        image: Passport image (numpy array)
        
    Returns:
        Tuple of (mrz_image, mrz_lines) or None if not found
    """
    height, width = image.shape[:2]
    
    # Extract bottom portion where MRZ is located
    mrz_start = int(height * 0.75)  # Bottom 25%
    mrz_region = image[mrz_start:height, :]
    
    # Preprocess MRZ region for better OCR
    gray = cv2.cvtColor(mrz_region, cv2.COLOR_BGR2GRAY) if len(mrz_region.shape) == 3 else mrz_region
    
    # Apply threshold to enhance contrast
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Perform OCR on MRZ region
    ocr = get_ocr_service()
    result = ocr.ocr(thresh, cls=False)
    
    if not result or not result[0]:
        return None
    
    # Extract text lines
    mrz_lines = []
    for line in result[0]:
        if line[1][0]:  # If text exists
            text = line[1][0].strip().upper()
            # MRZ lines are exactly 44 characters
            if len(text) >= 40:  # Allow some OCR error margin
                mrz_lines.append(text)
    
    return (mrz_region, mrz_lines) if mrz_lines else None



def extract_passport_fields_ocr(image: np.ndarray) -> Dict:
    """
    Extract passport fields using visual OCR.
    
    Extracts non-MRZ fields:
    - Place of Birth (مكان الولادة / PLACE OF BIRTH)
    - Profession/Occupation (المهنة / PROFESSION)
    - Issue Date (تاريخ الإصدار / DATE OF ISSUE)
    - Issuing Authority (جهة الإصدار / ISSUING AUTHORITY)
    
    Args:
        image: Passport image
        
    Returns:
        Dictionary of extracted fields
    """
    import re
    
    ocr = get_ocr_service()
    result = ocr.ocr(image, cls=True)
    
    # Extract all text with position info
    all_text = []
    text_with_pos = []
    if result and result[0]:
        for line in result[0]:
            if line[1][0]:
                text = line[1][0].strip()
                all_text.append(text)
                # Store with bounding box for spatial analysis
                text_with_pos.append({
                    "text": text,
                    "box": line[0],
                    "confidence": line[1][1] if len(line[1]) > 1 else 0.9
                })
    
    # Initialize fields
    ocr_data = {
        "place_of_birth": None,
        "place_of_birth_arabic": None,
        "profession": None,
        "profession_arabic": None,
        "issuance_date": None,
        "issuing_authority": None,
        "issuing_authority_arabic": None,
        "raw_text": all_text
    }
    
    # Keywords for field detection (English and Arabic)
    keywords = {
        "place_of_birth": [
            "place of birth", "birthplace", "مكان الولادة", "مكان الميلاد",
            "محل الولادة", "مكان"
        ],
        "profession": [
            "profession", "occupation", "المهنة", "مهنة", "الوظيفة"
        ],
        "issuance_date": [
            "date of issue", "issue date", "تاريخ الإصدار", "تاريخ الاصدار",
            "تاريخ المنح", "date issue"
        ],
        "issuing_authority": [
            "issuing authority", "authority", "جهة الإصدار", "سلطة الإصدار",
            "مكان الإصدار", "جهة"
        ]
    }
    
    # Date pattern for extracting dates
    date_pattern = r'\d{2}[/\-\.]\d{2}[/\-\.]\d{4}|\d{4}[/\-\.]\d{2}[/\-\.]\d{2}'
    
    # Known Yemen cities/governorates (issuing authorities)
    yemen_authorities = [
        "ADEN", "SANA'A", "SANAA", "TAIZ", "HODEIDAH", "MUKALLA",
        "عدن", "صنعاء", "تعز", "الحديدة", "المكلا", "حضرموت"
    ]
    
    # Process text to find fields
    for i, text in enumerate(all_text):
        text_lower = text.lower()
        text_normalized = text_lower.replace("'", "").replace("'", "")
        
        # Get next text item if available
        next_text = all_text[i + 1] if i + 1 < len(all_text) else None
        
        # ============ PLACE OF BIRTH ============
        if not ocr_data["place_of_birth"]:
            for keyword in keywords["place_of_birth"]:
                if keyword.lower() in text_lower or keyword in text:
                    # Check if value is on same line (after keyword)
                    parts = text.split(keyword if keyword in text else keyword.upper())
                    if len(parts) > 1 and parts[1].strip():
                        value = parts[1].strip().strip('-:').strip()
                        if value and len(value) > 1:
                            ocr_data["place_of_birth"] = value
                            break
                    # Check next line
                    elif next_text and len(next_text) > 1:
                        # Skip if next text is another field label
                        if not any(kw in next_text.lower() for kws in keywords.values() for kw in kws):
                            ocr_data["place_of_birth"] = next_text
                            break
        
        # ============ PROFESSION ============
        if not ocr_data["profession"]:
            for keyword in keywords["profession"]:
                if keyword.lower() in text_lower or keyword in text:
                    parts = text.split(keyword if keyword in text else keyword.upper())
                    if len(parts) > 1 and parts[1].strip():
                        value = parts[1].strip().strip('-:').strip()
                        if value and len(value) > 1:
                            ocr_data["profession"] = value
                            break
                    elif next_text and len(next_text) > 1:
                        if not any(kw in next_text.lower() for kws in keywords.values() for kw in kws):
                            ocr_data["profession"] = next_text
                            break
        
        # ============ ISSUANCE DATE ============
        if not ocr_data["issuance_date"]:
            for keyword in keywords["issuance_date"]:
                if keyword.lower() in text_lower or keyword in text:
                    # Look for date in same line
                    date_match = re.search(date_pattern, text)
                    if date_match:
                        ocr_data["issuance_date"] = date_match.group()
                        break
                    # Look for date in next line
                    elif next_text:
                        date_match = re.search(date_pattern, next_text)
                        if date_match:
                            ocr_data["issuance_date"] = date_match.group()
                            break
        
        # ============ ISSUING AUTHORITY ============
        if not ocr_data["issuing_authority"]:
            # Check for known authority names
            for authority in yemen_authorities:
                if authority.lower() in text_lower or authority in text:
                    ocr_data["issuing_authority"] = authority.upper() if authority.isascii() else authority
                    break
            
            # Also check via keywords
            if not ocr_data["issuing_authority"]:
                for keyword in keywords["issuing_authority"]:
                    if keyword.lower() in text_lower or keyword in text:
                        parts = text.split(keyword if keyword in text else keyword.upper())
                        if len(parts) > 1 and parts[1].strip():
                            value = parts[1].strip().strip('-:').strip()
                            if value and len(value) > 1:
                                ocr_data["issuing_authority"] = value
                                break
                        elif next_text:
                            # Check if next text is a known authority
                            for auth in yemen_authorities:
                                if auth.lower() in next_text.lower() or auth in next_text:
                                    ocr_data["issuing_authority"] = auth.upper() if auth.isascii() else auth
                                    break
    
    return ocr_data



def merge_mrz_and_ocr_data(mrz_data: Dict, ocr_data: Dict) -> Dict:
    """
    Merge MRZ and OCR data with priority to MRZ.
    
    MRZ provides: passport_number, name, DOB, gender, expiry, nationality
    OCR provides: place_of_birth, profession, issuance_date, issuing_authority
    
    Args:
        mrz_data: Data from MRZ parser
        ocr_data: Data from visual OCR
        
    Returns:
        Merged passport data
    """
    merged = {
        # Document type
        "id_type": "yemen_passport",
        
        # MRZ fields (high confidence - 99%)
        "passport_number": mrz_data.get("passport_number"),
        "surname": mrz_data.get("surname"),
        "given_names": mrz_data.get("given_names"),
        "name_english": mrz_data.get("full_name_english"),
        "date_of_birth": mrz_data.get("date_of_birth"),
        "gender": mrz_data.get("gender"),
        "expiry_date": mrz_data.get("expiry_date"),
        "nationality": mrz_data.get("nationality"),
        "country_code": mrz_data.get("issuing_country"),
        
        # OCR fields (medium confidence - 85%)
        "place_of_birth": ocr_data.get("place_of_birth"),
        "profession": ocr_data.get("profession"),
        "issuance_date": ocr_data.get("issuance_date"),
        "issuing_authority": ocr_data.get("issuing_authority"),
        
        # Metadata
        "extraction_method": "MRZ_PRIMARY",
        "mrz_valid": mrz_data.get("mrz_valid", False),
        "mrz_confidence": mrz_data.get("confidence", 0.0),
        "ocr_confidence": 0.85,
        
        # Raw data for debugging
        "mrz_raw": {
            "line1": mrz_data.get("mrz_line1"),
            "line2": mrz_data.get("mrz_line2")
        },
        "ocr_raw_text": ocr_data.get("raw_text", [])
    }
    
    return merged


def extract_passport_data(image_path: str) -> Dict:
    """
    Main function: Extract all data from Yemen passport.
    
    Process:
    1. Load image
    2. Try PassportEye for MRZ detection (robust, handles rotation/skew)
    3. Fallback to pixel-based MRZ extraction if PassportEye fails
    4. Perform visual OCR (supplementary data)
    5. Merge results with MRZ priority
    
    Args:
        image_path: Path to passport image file
        
    Returns:
        Complete passport data dictionary
    """
    try:
        # Load image
        image = load_image(image_path)
        if image is None:
            return {
                "success": False,
                "error": "Failed to load image",
                "id_type": "yemen_passport"
            }
        
        mrz_data = None
        
        # Step 1: Try PassportEye first (robust MRZ detection)
        passporteye_result = extract_mrz_with_passporteye(image)
        
        if passporteye_result and passporteye_result.get("success"):
            mrz_data = passporteye_result
            mrz_data["extraction_method"] = "PASSPORTEYE"
        else:
            # Step 2: Fallback to pixel-based extraction
            mrz_result = extract_mrz_region_fallback(image)
            
            if mrz_result:
                mrz_image, mrz_lines = mrz_result
                
                # Clean up MRZ lines (ensure exactly 44 chars)
                cleaned_mrz = []
                for line in mrz_lines[:2]:  # Only need first 2 lines
                    # Pad or trim to 44 characters
                    if len(line) < 44:
                        line = line + '<' * (44 - len(line))
                    elif len(line) > 44:
                        line = line[:44]
                    cleaned_mrz.append(line)
                
                if len(cleaned_mrz) == 2:
                    # Parse MRZ using our parser
                    mrz_data = parse_passport_mrz(cleaned_mrz)
                    if mrz_data.get("success"):
                        mrz_data["extraction_method"] = "PIXEL_FALLBACK"
        
        # Step 3: If MRZ extraction succeeded
        if mrz_data and mrz_data.get("success"):
            # Visual OCR for supplementary fields
            ocr_data = extract_passport_fields_ocr(image)
            
            # Merge data
            final_data = merge_mrz_and_ocr_data(mrz_data, ocr_data)
            final_data["success"] = True
            final_data["extraction_method"] = mrz_data.get("extraction_method", "MRZ_PRIMARY")
            
            return final_data
        
        # No MRZ found by either method
        return {
            "success": False,
            "error": "MRZ not detected in image",
            "id_type": "yemen_passport",
            "suggestion": "Ensure passport is flat and MRZ at bottom is clearly visible"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Passport extraction failed: {str(e)}",
            "id_type": "yemen_passport"
        }


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
