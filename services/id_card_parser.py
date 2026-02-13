"""
ID Card Parser Service

Extracts structured data from Yemen ID cards including:
- Name (Arabic and English)
- Date of Birth
- Gender
- Address
- Nationality
- Issuance Date
- Expiry Date
- ID Number
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from services.translation_service import translate_text

logger = logging.getLogger(__name__)
from utils.date_utils import format_date


def extract_dates_from_texts(texts: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract issuance and expiry dates from OCR texts (BACK CARD ONLY).
    Logic: Issuance date typically comes before expiry date on the card.
    
    Args:
        texts: List of OCR extracted texts
        
    Returns:
        Tuple of (issuance_date, expiry_date) in YYYY-MM-DD format
    """
    # Common date patterns
    date_patterns = [
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY-MM-DD or YYYY/MM/DD
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # DD-MM-YYYY or DD/MM/YYYY
        r'(\d{4})(\d{2})(\d{2})',              # YYYYMMDD
    ]
    
    found_dates = []
    current_year = datetime.now().year
    
    for text in texts:
        # Skip if text looks like an ID number (too long, mostly digits)
        if len(text) > 10 and sum(c.isdigit() for c in text) / len(text) > 0.8:
            continue
            
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    # Try to parse the date
                    if len(match[0]) == 4:  # YYYY-MM-DD format
                        year, month, day = match
                    else:  # DD-MM-YYYY format
                        day, month, year = match
                    
                    year_int = int(year)
                    
                    # Filter unreasonable years for issuance/expiry dates
                    # Issuance: should be between 1990 and current year
                    # Expiry: should be between current year and current year + 50
                    if year_int < 1990 or year_int > current_year + 50:
                        continue
                    
                    # Validate date
                    date_obj = datetime(year_int, int(month), int(day))
                    
                    # Dates should not be too far in the past (no issuance before 1990)
                    if date_obj.year < 1990:
                        continue
                        
                    formatted_date = format_date(date_obj)
                    found_dates.append((formatted_date, date_obj))
                except (ValueError, IndexError):
                    continue
    
    # Sort dates chronologically
    found_dates.sort(key=lambda x: x[1])
    
    if len(found_dates) >= 2:
        # First date is likely issuance, second is likely expiry
        return found_dates[0][0], found_dates[1][0]
    elif len(found_dates) == 1:
        # Only one date found - could be either
        return found_dates[0][0], None
    
    return None, None


def extract_name_from_texts(texts: List[str], text_results: List[Dict]) -> Tuple[Optional[str], Optional[str], float, float]:
    """
    Extract name from OCR results using NER with heuristic fallback.
    
    Args:
        texts: List of all extracted texts
        text_results: Detailed text results with language detection
        
    Returns:
        Tuple of (arabic_name, english_name, arabic_confidence, english_confidence)
    """
    
    arabic_name = None
    english_name = None
    arabic_conf = 0.0
    english_conf = 0.0
    
    # Fallback to heuristic-based extraction
    # Look for Arabic name (usually longer text blocks in Arabic)
    arabic_items = [
        item for item in text_results 
        if item.get('detected_language') == 'ar' and len(item['text']) > 5
    ]
    
    # Look for English name (usually longer text blocks in English)
    english_items = [
        item for item in text_results 
        if item.get('detected_language') == 'en' and len(item['text']) > 5
    ]
    
    # Filter out texts that look like labels or IDs
    def is_likely_name(text: str) -> bool:
        # Names usually have multiple words or are reasonably long
        word_count = len(text.split())
        # Avoid texts that are mostly numbers
        digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)
        # Avoid common label keywords (including field labels from ID cards)
        label_keywords = [
            'name', 'الاسم', 'address', 'العنوان', 'id', 'رقم',
            'مكان', 'تاريخ', 'الميلاد', 'وتاريخ', 'ونريخ',  # Place/Date/Birth labels
            'date', 'birth', 'place', 'gender', 'الجنس'
        ]
        has_label = any(kw in text.lower() for kw in label_keywords)
        
        return (word_count >= 2 or (len(text) > 5 and digit_ratio < 0.3)) and not has_label
    
    # Get the most likely Arabic name with confidence
    if arabic_items:
        likely_items = [item for item in arabic_items if is_likely_name(item['text'])]
        if likely_items:
            # Prefer longer names (more complete)
            best_item = max(likely_items, key=lambda x: len(x['text']))
            arabic_name = best_item['text']
            arabic_conf = float(best_item.get('score', 0.0))
    
    # Get the most likely English name with confidence
    if english_items:
        likely_items = [item for item in english_items if is_likely_name(item['text'])]
        if likely_items:
            best_item = max(likely_items, key=lambda x: len(x['text']))
            english_name = best_item['text']
            english_conf = float(best_item.get('score', 0.0))
    
    # If we have Arabic but not English, translate
    if arabic_name and not english_name:
        try:
            english_name = translate_text(arabic_name, source="ar", target="en")
            # Inherit Arabic confidence for translation
            english_conf = arabic_conf * 0.9  # Slight reduction for translation uncertainty
            
            # Validate translation quality
            # If translation is too short or contains weird characters, it might have failed
            if english_name and (len(english_name) < 3 or english_name.count(',') > 2):
                logger.warning(f"Poor translation quality for '{arabic_name}' -> '{english_name}'")
                # Keep the translation anyway, but log it
        except Exception as e:
            logger.warning(f"Translation failed for '{arabic_name}': {e}")
            english_name = None
            english_conf = 0.0
    
    return arabic_name, english_name, arabic_conf, english_conf



def extract_gender_from_texts(texts: List[str], text_results: List[Dict]) -> Optional[str]:
    """
    Extract gender from OCR texts.
    
    Args:
        texts: List of all extracted texts
        text_results: Detailed text results
        
    Returns:
        Gender ('Male' or 'Female') or None
    """
    # Common gender indicators in English and Arabic
    male_indicators = ['male', 'ذكر', 'M']
    female_indicators = ['female', 'أنثى', 'F']
    
    for text in texts:
        text_lower = text.lower().strip()
        
        # Check for male indicators
        for indicator in male_indicators:
            if indicator.lower() in text_lower:
                return "Male"
        
        # Check for female indicators
        for indicator in female_indicators:
            if indicator.lower() in text_lower:
                return "Female"
    
    return None


def extract_place_of_birth(texts: List[str]) -> Optional[str]:
    """
    Extract Place of Birth from FRONT card OCR texts.
    Logic: Look for text on the same line as the Date of Birth (YYYY/MM/DD).
           The text might be AFTER the date (standard) or BEFORE (if OCR flips RTL).
    
    Args:
        texts: List of OCR extracted texts
        
    Returns:
        Place of Birth in English (translated)
    """
    # Pattern for DOB: YYYY/MM/DD or YYYY-MM-DD or YYYY.MM.DD (allow spaces)
    date_pattern = r'(\d{4}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2})'
    
    logger.debug("Starting Place of Birth extraction...")
    
    # Helper to validate Arabic text quality
    def is_valid_arabic_text(text: str) -> bool:
        # Must contain valid Arabic content
        if not text:
            return False
            
        # Count total Arabic characters
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        
        # If we have at least 3 Arabic characters total, it's likely valid
        # even if they are spaced out (e.g. "ص ن ع ا ء")
        if arabic_chars >= 2:
            return True
            
        return False

    for i, text in enumerate(texts):
        # clean cleanup the text
        clean_text = text.strip()
        match = re.search(date_pattern, clean_text)
        
        if match:
            logger.debug(f"Found DOB pattern in line: '{clean_text}'")
            
            # Strategy 1: Check text AFTER date (Standard user description)
            date_end_index = match.end()
            remainder_after = clean_text[date_end_index:].strip()
            cleaned_after = re.sub(r'^[-_.\s،,]+', '', remainder_after).strip()
            
            if len(cleaned_after) > 2:
                if is_valid_arabic_text(cleaned_after):
                    logger.debug(f"Found place AFTER date: '{cleaned_after}'")
                    return translate_text(cleaned_after, source="ar", target="en")
                else:
                    logger.debug(f"Rejected text AFTER date (invalid Arabic): '{cleaned_after}'")
            
            # Strategy 2: Check text BEFORE date (Fallback for RTL/OCR issues)
            date_start_index = match.start()
            remainder_before = clean_text[:date_start_index].strip()
            cleaned_before = re.sub(r'[-_.\s،,]+$', '', remainder_before).strip()
            
            if len(cleaned_before) > 2:
                if is_valid_arabic_text(cleaned_before):
                    logger.debug(f"Found place BEFORE date: '{cleaned_before}'")
                    return translate_text(cleaned_before, source="ar", target="en")
                else:
                    logger.debug(f"Rejected text BEFORE date (invalid Arabic): '{cleaned_before}'")

            # Strategy 3: Check immediate next line (Split line case)
            if i + 1 < len(texts):
                next_text = texts[i+1].strip()
                cleaned_next = re.sub(r'^[-_.\s،,]+', '', next_text).strip()
                
                # Verify it's not another date or noise
                if len(cleaned_next) > 2 and not re.search(date_pattern, cleaned_next):
                    if is_valid_arabic_text(cleaned_next):
                        logger.debug(f"Found place on NEXT line: '{cleaned_next}'")
                        return translate_text(cleaned_next, source="ar", target="en")
                    else:
                        logger.debug(f"Ignored next line content (invalid Arabic): '{cleaned_next}'")
                
    logger.debug("No Place of Birth found.")
    return None


def extract_nationality_from_texts(texts: List[str], text_results: List[Dict]) -> Optional[str]:
    """
    Extract nationality from OCR texts.
    
    Args:
        texts: List of all extracted texts
        text_results: Detailed text results
        
    Returns:
        Nationality in English
    """
    # For Yemen ID cards, nationality is typically "Yemeni"
    nationality_keywords = {
        'يمني': 'Yemeni',
        'يمنية': 'Yemeni',
        'yemeni': 'Yemeni',
        'yemen': 'Yemeni'
    }
    
    for text in texts:
        text_lower = text.lower().strip()
        for keyword, nationality in nationality_keywords.items():
            if keyword in text_lower:
                return nationality
    
    # Default to Yemeni for Yemen ID cards if not found
    return "Yemeni"


def extract_date_of_birth(texts: List[str]) -> Optional[str]:
    """
    Extract date of birth from OCR texts.
    Improved: Extracts ALL dates from front card and identifies DOB by age range.
    
    Args:
        texts: List of all extracted texts
        
    Returns:
        Date of birth in YYYY-MM-DD format
    """
    # Birth date keywords (try keyword-based first)
    birth_keywords = ['birth', 'dob', 'date of birth', 'تاريخ الميلاد', 'ميلاد', 'المولد']
    
    date_patterns = [
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY-MM-DD
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # DD-MM-YYYY
        r'(\d{4})(\d{2})(\d{2})',              # YYYYMMDD
    ]
    
    found_dates = []
    
    # Method 1: Try keyword-based extraction
    for i, text in enumerate(texts):
        text_lower = text.lower()
        
        # Check if this text contains birth keyword
        for keyword in birth_keywords:
            if keyword in text_lower:
                # Look in the same text and next few texts
                search_texts = texts[i:i+3]
                
                for search_text in search_texts:
                    for pattern in date_patterns:
                        matches = re.findall(pattern, search_text)
                        for match in matches:
                            try:
                                if len(match[0]) == 4:
                                    year, month, day = match
                                else:
                                    day, month, year = match
                                
                                date_obj = datetime(int(year), int(month), int(day))
                                # Birth dates should be in the past and reasonable (age 0-100)
                                age = (datetime.now() - date_obj).days / 365.25
                                if 0 < age <= 100:
                                    return format_date(date_obj)
                            except (ValueError, IndexError):
                                continue
    
    # Method 2: If no keyword found, extract ALL dates and find the one that looks like DOB
    # DOB is usually between 1920 and current year minus 1
    for text in texts:
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    if len(match[0]) == 4:
                        year, month, day = match
                    else:
                        day, month, year = match
                    
                    date_obj = datetime(int(year), int(month), int(day))
                    
                    # Calculate age
                    age = (datetime.now() - date_obj).days / 365.25
                    
                    # Birth date should represent age 0-100
                    # Issuance/Expiry dates are usually recent (last 30 years)
                    if 0 < age <= 100 and date_obj < datetime.now():
                        found_dates.append((date_obj, age))
                except (ValueError, IndexError):
                    continue
    
    # If we found dates, pick the one that represents the oldest person (most likely DOB)
    if found_dates:
        # Sort by age (oldest first)
        found_dates.sort(key=lambda x: x[1], reverse=True)
        # Return the oldest date (most likely the birth date, not issuance/expiry)
        return format_date(found_dates[0][0])
    
    return None


def parse_yemen_id_card(
    front_ocr_result: Dict,
    back_ocr_result: Optional[Dict] = None
) -> Dict:
    """
    Parse structured data from Yemen ID card OCR results with separate front/back processing.
    
    CARD LAYOUT:
    - FRONT: Name, DOB, Gender, Photo, ID Number
    - BACK: Issuance Date, Expiry Date, Address
    
    Args:
        front_ocr_result: OCR result from FRONT of ID card
        back_ocr_result: OCR result from BACK of ID card (optional)
        
    Returns:
        Dictionary with structured ID card data including field_confidences
    """
    # =====================================================================
    # YOLO fast path: extract directly from layout_fields when available
    # =====================================================================
    layout_fields = front_ocr_result.get("layout_fields", {})
    extraction_method = front_ocr_result.get("extraction_method", "fallback")
    
    if extraction_method == "yolo" and layout_fields:
        # Map YOLO labels → structured fields
        name_text = layout_fields.get("name", {}).get("text", "")
        dob_text = layout_fields.get("DOB", {}).get("text", "")
        pob_text = layout_fields.get("POB", {}).get("text", "")
        id_text = layout_fields.get("unique_id", {}).get("text", "")
        issue_text = layout_fields.get("issue_date", {}).get("text", "")
        expiry_text = layout_fields.get("expiry_data", {}).get("text", "")
        
        # Confidences from YOLO detection
        name_conf = float(layout_fields.get("name", {}).get("confidence", 0.0))
        dob_conf = float(layout_fields.get("DOB", {}).get("confidence", 0.0))
        pob_conf = float(layout_fields.get("POB", {}).get("confidence", 0.0))
        id_conf = float(layout_fields.get("unique_id", {}).get("confidence", 0.0))
        issue_conf = float(layout_fields.get("issue_date", {}).get("confidence", 0.0))
        expiry_conf = float(layout_fields.get("expiry_data", {}).get("confidence", 0.0))
        
        # Name: the YOLO name field is Arabic
        # NOTE: english_name is NOT translated here — the route layer uses
        # hybrid_name_convert for a superior local transliteration instead.
        arabic_name = name_text.strip() if name_text.strip() else None
        english_name = None
        
        # DOB: normalise to YYYY-MM-DD
        date_of_birth = None
        if dob_text.strip():
            try:
                # Handle YYYY/MM/DD or YYYY-MM-DD
                cleaned = dob_text.strip().replace("/", "-")
                parts = cleaned.split("-")
                if len(parts) == 3:
                    date_of_birth = format_date(
                        datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                    )
            except (ValueError, IndexError):
                date_of_birth = dob_text.strip()
        
        # Place of birth: translate Arabic → English
        place_of_birth = None
        if pob_text.strip():
            try:
                place_of_birth = translate_text(pob_text.strip(), source="ar", target="en")
            except Exception as e:
                logger.warning(f"POB translation failed: {e}")
                place_of_birth = pob_text.strip()
        
        # Gender: derive from ID number (Yemen national IDs encode gender)
        gender = None
        id_number = id_text.strip() if id_text.strip() else front_ocr_result.get("extracted_id")
        
        # Logic from YemenNationalIDForm: 4th digit (index 3) indicates gender
        # 1 = Male, 0 = Female
        if id_number and len(id_number) >= 4 and id_number.isdigit():
            try:
                fourth_digit = int(id_number[3])
                if fourth_digit == 1:
                    gender = "Male"
                elif fourth_digit == 0:
                    gender = "Female"
            except (ValueError, IndexError):
                pass  # Keep as None if parsing fails
        
        # Issue / Expiry dates (may come from back card YOLO)
        issuance_date = None
        if issue_text.strip():
            try:
                cleaned = issue_text.strip().replace("/", "-")
                parts = cleaned.split("-")
                if len(parts) == 3:
                    issuance_date = format_date(
                        datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                    )
            except (ValueError, IndexError):
                issuance_date = issue_text.strip()
        
        expiry_date = None
        if expiry_text.strip():
            try:
                cleaned = expiry_text.strip().replace("/", "-")
                parts = cleaned.split("-")
                if len(parts) == 3:
                    expiry_date = format_date(
                        datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                    )
            except (ValueError, IndexError):
                expiry_date = expiry_text.strip()
        
        # Also check back card layout_fields if provided
        if back_ocr_result and back_ocr_result.get("extraction_method") == "yolo":
            back_layout = back_ocr_result.get("layout_fields", {})
            if not issuance_date:
                back_issue = back_layout.get("issue_date", {}).get("text", "").strip()
                if back_issue:
                    try:
                        cleaned = back_issue.replace("/", "-")
                        parts = cleaned.split("-")
                        if len(parts) == 3:
                            issuance_date = format_date(
                                datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                            )
                    except (ValueError, IndexError):
                        issuance_date = back_issue
                    issue_conf = float(back_layout.get("issue_date", {}).get("confidence", 0.0))
            if not expiry_date:
                back_expiry = back_layout.get("expiry_data", {}).get("text", "").strip()
                if back_expiry:
                    try:
                        cleaned = back_expiry.replace("/", "-")
                        parts = cleaned.split("-")
                        if len(parts) == 3:
                            expiry_date = format_date(
                                datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                            )
                    except (ValueError, IndexError):
                        expiry_date = back_expiry
                    expiry_conf = float(back_layout.get("expiry_data", {}).get("confidence", 0.0))
        elif back_ocr_result:
            # Back card used fallback OCR — use heuristic date extraction
            back_texts = back_ocr_result.get("all_texts", [])
            if back_texts:
                fb_issue, fb_expiry = extract_dates_from_texts(back_texts)
                if not issuance_date and fb_issue:
                    issuance_date = fb_issue
                if not expiry_date and fb_expiry:
                    expiry_date = fb_expiry
        
        field_confidences = {
            "name_arabic": name_conf if arabic_name else 0.0,
            "name_english": (name_conf * 0.9) if english_name else 0.0,
            "date_of_birth": dob_conf if date_of_birth else 0.0,
            "gender": 0.0,
            "place_of_birth": pob_conf if place_of_birth else 0.0,
            "issuance_date": issue_conf if issuance_date else 0.0,
            "expiry_date": expiry_conf if expiry_date else 0.0,
            "id_number": id_conf if id_number else 0.0,
        }
        
        return {
            "name_arabic": arabic_name,
            "name_english": english_name,
            "date_of_birth": date_of_birth,
            "gender": gender,
            "place_of_birth": place_of_birth,
            "issuance_date": issuance_date,
            "expiry_date": expiry_date,
            "id_number": id_number or front_ocr_result.get("extracted_id"),
            "id_type": front_ocr_result.get("id_type"),
            "field_confidences": field_confidences,
        }
    
    # =====================================================================
    # Fallback path: NO HEURISTICS (as requested)
    # =====================================================================
    # If YOLO failed or didn't run, we do NOT attempt to parse raw text.
    # We just return the ID number if it was extracted by the regex fallback in OCR service.
    
    # Initialize variables that would have been set by the fallback
    if 'arabic_name' not in locals(): arabic_name = None
    if 'english_name' not in locals(): english_name = None
    if 'date_of_birth' not in locals(): date_of_birth = None
    if 'gender' not in locals(): gender = None
    if 'place_of_birth' not in locals(): place_of_birth = None
    if 'issuance_date' not in locals(): issuance_date = None
    if 'expiry_date' not in locals(): expiry_date = None
    if 'id_number' not in locals(): id_number = front_ocr_result.get("extracted_id")
    
    # Default confidences
    field_confidences = {
        "name_arabic": 0.0,
        "name_english": 0.0,
        "date_of_birth": 0.0,
        "gender": 0.0,
        "place_of_birth": 0.0,
        "issuance_date": 0.0,
        "expiry_date": 0.0,
        "id_number": float(front_ocr_result.get("confidence", 0.0)) if id_number else 0.0,
    }
    
    return {
        "name_arabic": arabic_name,
        "name_english": english_name,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "place_of_birth": place_of_birth,
        "issuance_date": issuance_date,
        "expiry_date": expiry_date,
        "id_number": id_number,
        "id_type": front_ocr_result.get("id_type"),
        "field_confidences": field_confidences,
    }



def filter_organization_names(text_results: List[Dict]) -> List[Dict]:
    """
    Filter out government/organization names that shouldn't be treated as person names.
    
    Common Yemen ID card organization texts to filter:
    - مصلحة الأحوال المدنية (Civil Status Authority)
    - السجل المدني (Civil Registry)
    - الجمهورية اليمنية (Republic of Yemen)
    - وزارة (Ministry)
    
    Args:
        text_results: OCR text results
        
    Returns:
        Filtered text results without organization names
    """
    # Keywords that indicate organization/government names OR field labels
    org_keywords = [
        'مصلحة', 'الأحوال', 'المدنية', 'السجل', 'المدني',
        'الجمهورية', 'اليمنية', 'وزارة', 'ministry',
        'authority', 'republic', 'civil', 'registry',
        'government', 'حكومة', 'دولة',
        'مكان', 'تاريخ', 'الميلاد', 'وتاريخ', 'ونريخ',  # Field labels
        'date', 'birth', 'place'
    ]
    
    filtered_results = []
    
    for item in text_results:
        text = item.get('text', '').lower()
        
        # Check if text contains any organization keywords
        is_org = any(keyword in text for keyword in org_keywords)
        
        # Also filter if it's too long (organization names tend to be longer)
        is_too_long = len(text.split()) > 6
        
        if not is_org and not is_too_long:
            filtered_results.append(item)
    
    return filtered_results
