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


def extract_name_from_texts(texts: List[str], text_results: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract name from OCR results using NER with heuristic fallback.
    
    Args:
        texts: List of all extracted texts
        text_results: Detailed text results with language detection
        
    Returns:
        Tuple of (arabic_name, english_name)
    """
    
    arabic_name = None
    english_name = None
    
    # Fallback to heuristic-based extraction
    # Look for Arabic name (usually longer text blocks in Arabic)
    arabic_texts = [
        item['text'] for item in text_results 
        if item.get('detected_language') == 'ar' and len(item['text']) > 5
    ]
    
    # Look for English name (usually longer text blocks in English)
    english_texts = [
        item['text'] for item in text_results 
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
    
    # Get the most likely Arabic name
    if arabic_texts:
        likely_names = [t for t in arabic_texts if is_likely_name(t)]
        if likely_names:
            # Prefer longer names (more complete)
            arabic_name = max(likely_names, key=len)
    
    # Get the most likely English name
    if english_texts:
        likely_names = [t for t in english_texts if is_likely_name(t)]
        if likely_names:
            english_name = max(likely_names, key=len)
    
    # If we have Arabic but not English, translate
    if arabic_name and not english_name:
        try:
            english_name = translate_text(arabic_name, source="ar", target="en")
            
            # Validate translation quality
            # If translation is too short or contains weird characters, it might have failed
            if english_name and (len(english_name) < 3 or english_name.count(',') > 2):
                logger.warning(f"Poor translation quality for '{arabic_name}' -> '{english_name}'")
                # Keep the translation anyway, but log it
        except Exception as e:
            logger.warning(f"Translation failed for '{arabic_name}': {e}")
            english_name = None
    
    return arabic_name, english_name


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
        Dictionary with structured ID card data
    """
    # Extract from FRONT card
    front_texts = front_ocr_result.get("all_texts", [])
    front_text_results = front_ocr_result.get("text_results", [])
    
    # Filter out organization/government names from front
    filtered_front_results = filter_organization_names(front_text_results)
    
    # Extract fields from FRONT
    arabic_name, english_name = extract_name_from_texts(front_texts, filtered_front_results)
    date_of_birth = extract_date_of_birth(front_texts)
    gender = extract_gender_from_texts(front_texts, front_text_results)
    place_of_birth = extract_place_of_birth(front_texts)
    
    # Initialize back card fields
    issuance_date = None
    expiry_date = None
    
    # Extract from BACK card if provided
    if back_ocr_result:
        back_texts = back_ocr_result.get("all_texts", [])
        
        # Extract fields from BACK
        issuance_date, expiry_date = extract_dates_from_texts(back_texts)
    
    return {
        "name_arabic": arabic_name,
        "name_english": english_name,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "place_of_birth": place_of_birth,
        "issuance_date": issuance_date,
        "expiry_date": expiry_date,
        "id_number": front_ocr_result.get("extracted_id"),
        "id_type": front_ocr_result.get("id_type")
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
