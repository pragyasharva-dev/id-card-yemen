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
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from services.translation_service import translate_text


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
                        
                    formatted_date = date_obj.strftime("%Y-%m-%d")
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
    from services.ner_extractor import get_ner_extractor, is_ner_available
    
    arabic_name = None
    english_name = None
    
    # Try NER-based extraction first
    if is_ner_available():
        try:
            ner = get_ner_extractor()
            arabic_name, english_name = ner.extract_person_names(text_results)
            
            # If NER found results, return them
            if arabic_name or english_name:
                return arabic_name, english_name
        except Exception as e:
            print(f"NER extraction failed: {e}, falling back to heuristics")
    
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
        # Avoid common label keywords
        label_keywords = ['name', 'الاسم', 'address', 'العنوان', 'id', 'رقم']
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
                print(f"Warning: Poor translation quality for '{arabic_name}' -> '{english_name}'")
                # Keep the translation anyway, but log it
        except Exception as e:
            print(f"Translation failed for '{arabic_name}': {e}")
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


def extract_address_from_texts(texts: List[str], text_results: List[Dict]) -> Optional[str]:
    """
    Extract address from OCR texts using NER with keyword-based fallback.
    
    Args:
        texts: List of all extracted texts
        text_results: Detailed text results
        
    Returns:
        Address in English (translated from Arabic if needed)
    """
    from services.ner_extractor import get_ner_extractor, is_ner_available
    
    # Try NER-based extraction first
    if is_ner_available():
        try:
            ner = get_ner_extractor()
            address = ner.extract_locations(text_results)
            
            if address:
                return address
        except Exception as e:
            print(f"NER address extraction failed: {e}, falling back to keywords")
    
    # Fallback to keyword-based extraction
    # Look for address-related keywords in Arabic
    address_keywords = ['عنوان', 'محافظة', 'مديرية', 'address']
    
    # Find texts that might contain address
    address_candidates = []
    
    for i, text in enumerate(texts):
        text_lower = text.lower()
        
        # Check if this text contains address keyword
        for keyword in address_keywords:
            if keyword in text_lower:
                # The address might be in the next text or the same text
                if i + 1 < len(texts):
                    address_candidates.append(texts[i + 1])
                # Check if address is in the same text after the keyword
                parts = text.split()
                for j, part in enumerate(parts):
                    if keyword in part.lower() and j + 1 < len(parts):
                        address_candidates.append(' '.join(parts[j+1:]))
    
    # Also look for longer Arabic texts that might be addresses
    for item in text_results:
        if item.get('detected_language') == 'ar':
            text = item['text']
            # Addresses are usually longer and contain specific characters
            if len(text) > 10 and any(char in text for char in ['،', ',', '.']):
                address_candidates.append(text)
    
    # Return the first candidate, translated to English
    if address_candidates:
        arabic_address = address_candidates[0]
        return translate_text(arabic_address, source="ar", target="en")
    
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
                                    return date_obj.strftime("%Y-%m-%d")
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
        return found_dates[0][0].strftime("%Y-%m-%d")
    
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
    
    # Initialize back card fields
    address = None
    issuance_date = None
    expiry_date = None
    
    # Extract from BACK card if provided
    if back_ocr_result:
        back_texts = back_ocr_result.get("all_texts", [])
        back_text_results = back_ocr_result.get("text_results", [])
        
        # Extract fields from BACK
        address = extract_address_from_texts(back_texts, back_text_results)
        issuance_date, expiry_date = extract_dates_from_texts(back_texts)
    
    return {
        "name_arabic": arabic_name,
        "name_english": english_name,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "address": address,
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
    # Keywords that indicate organization/government names
    org_keywords = [
        'مصلحة', 'الأحوال', 'المدنية', 'السجل', 'المدني',
        'الجمهورية', 'اليمنية', 'وزارة', 'ministry',
        'authority', 'republic', 'civil', 'registry',
        'government', 'حكومة', 'دولة'
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
