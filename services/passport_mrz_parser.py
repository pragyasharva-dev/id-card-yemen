"""
Passport MRZ (Machine Readable Zone) Parser

Parses passport MRZ according to ICAO 9303 TD-3 standard (2-line format).
Provides high-accuracy extraction of passport data from standardized MRZ.

MRZ Format (44 characters per line):
Line 1: P<YEMALARABI<<FAWAZ<HADI<MOHAMMED<<<<<<<<<<<<
Line 2: 10381272<6YEM8801018M2708218<<<<<<<<<<<<<<08

Accuracy: ~99% (much higher than OCR visual text)
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import re

from utils.date_utils import format_date
from utils.exceptions import ServiceError


def calculate_check_digit(data: str) -> str:
    """
    Calculate MRZ check digit according to ICAO 9303.
    
    Weighting: 7, 3, 1, 7, 3, 1, ...
    Character values: 0-9 = 0-9, A-Z = 10-35, < = 0
    
    Args:
        data: String to calculate check digit for
        
    Returns:
        Single digit check character (0-9)
    """
    weights = [7, 3, 1]
    char_values = {
        '<': 0,
        '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
        '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14,
        'F': 15, 'G': 16, 'H': 17, 'I': 18, 'J': 19,
        'K': 20, 'L': 21, 'M': 22, 'N': 23, 'O': 24,
        'P': 25, 'Q': 26, 'R': 27, 'S': 28, 'T': 29,
        'U': 30, 'V': 31, 'W': 32, 'X': 33, 'Y': 34, 'Z': 35
    }
    
    total = 0
    for i, char in enumerate(data.upper()):
        value = char_values.get(char, 0)
        weight = weights[i % 3]
        total += value * weight
    
    return str(total % 10)


def validate_check_digit(data: str, check_digit: str) -> bool:
    """
    Validate MRZ check digit.
    
    Args:
        data: Data string
        check_digit: Expected check digit
        
    Returns:
        True if valid, False otherwise
    """
    calculated = calculate_check_digit(data)
    return calculated == check_digit


def parse_date(date_str: str) -> Optional[str]:
    """
    Parse MRZ date format (YYMMDD) to ISO format (YYYY-MM-DD).
    
    Handles century: 00-40 = 2000s, 41-99 = 1900s
    
    Args:
        date_str: Date in YYMMDD format
        
    Returns:
        Date in YYYY-MM-DD format or None if invalid
    """
    if not date_str or len(date_str) != 6:
        return None
    
    try:
        yy = int(date_str[0:2])
        mm = int(date_str[2:4])
        dd = int(date_str[4:6])
        
        # Determine century
        if yy <= 40:
            yyyy = 2000 + yy
        else:
            yyyy = 1900 + yy
        
        # Validate date
        date_obj = datetime(yyyy, mm, dd)
        return format_date(date_obj)
        
    except (ValueError, IndexError):
        return None


def parse_mrz_line1(line: str) -> Dict:
    """
    Parse MRZ Line 1 (upper line).
    
    Format: P<YEMALARABI<<FAWAZ<HADI<MOHAMMED<<<<<<<<<<<<
    
    Positions:
    1: Document type (P = Passport)
    2: Filler (<)
    3-5: Issuing country (YEM)
    6-44: Surname << Given names (padded with <)
    
    Args:
        line: MRZ line 1 (44 characters)
        
    Returns:
        {
            "document_type": "P",
            "issuing_country": "YEM",
            "surname": "ALARABI",
            "given_names": "FAWAZ HADI MOHAMMED",
            "full_name": "FAWAZ HADI MOHAMMED ALARABI"
        }
    """
    if not line or len(line) != 44:
        raise ServiceError("Invalid MRZ line 1 length", code="MRZ_LINE1_INVALID")
    
    line = line.upper().strip()
    
    # Extract fields
    document_type = line[0]
    issuing_country = line[2:5]
    name_section = line[5:44]
    
    # Parse name (Surname << Given names)
    # Split by << to separate surname and given names
    name_parts = name_section.split('<<')
    
    surname = name_parts[0].replace('<', ' ').strip() if name_parts else ""
    given_names = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ""
    
    full_name = f"{given_names} {surname}".strip()
    
    return {
        "document_type": document_type,
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_names,
        "full_name_english": full_name
    }


def parse_mrz_line2(line: str) -> Dict:
    """
    Parse MRZ Line 2 (lower line).
    
    Format: 10381272<6YEM8801018M2708218<<<<<<<<<<<<<<08
    
    Positions:
    1-9: Passport number + check digit
    11-13: Nationality
    14-19: Date of birth (YYMMDD)
    20: DOB check digit
    21: Gender (M/F/<)
    22-27: Expiry date (YYMMDD)
    28: Expiry check digit
    29-42: Personal number (optional)
    43: Personal number check digit
    44: Composite check digit
    
    Args:
        line: MRZ line 2 (44 characters)
        
    Returns:
        {
            "passport_number": "10381272",
            "nationality": "YEM",
            "date_of_birth": "1988-01-01",
            "gender": "Male",
            "expiry_date": "2027-08-21",
            "valid_checksums": True
        }
    """
    if not line or len(line) != 44:
        raise ServiceError("Invalid MRZ line 2 length", code="MRZ_LINE2_INVALID")
    
    line = line.upper().strip()
    
    # Extract fields
    passport_number_raw = line[0:9]
    passport_number = passport_number_raw.replace('<', '').strip()
    passport_check = line[9]
    
    nationality = line[10:13]
    
    dob_raw = line[13:19]
    dob_check = line[19]
    
    gender_code = line[20]
    
    expiry_raw = line[21:27]
    expiry_check = line[27]
    
    personal_number = line[28:42].replace('<', '').strip()
    personal_check = line[42]
    composite_check = line[43]
    
    # Parse dates
    date_of_birth = parse_date(dob_raw)
    expiry_date = parse_date(expiry_raw)
    
    # Parse gender
    gender_map = {'M': 'Male', 'F': 'Female', '<': None}
    gender = gender_map.get(gender_code, None)
    
    # Validate checksums
    # Note: passport_number_raw is always 9 chars (8-digit numbers have '<' as 9th char)
    passport_valid = validate_check_digit(passport_number_raw, passport_check)
    dob_valid = validate_check_digit(dob_raw, dob_check)
    expiry_valid = validate_check_digit(expiry_raw, expiry_check)
    
    # Composite check validation (entire line 2 except last char)
    composite_data = line[0:10] + line[13:20] + line[21:43]
    composite_valid = validate_check_digit(composite_data, composite_check)
    
    all_valid = passport_valid and dob_valid and expiry_valid and composite_valid
    
    return {
        "passport_number": passport_number,
        "nationality": nationality,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "expiry_date": expiry_date,
        "personal_number": personal_number if personal_number else None,
        "checksums_valid": all_valid,
        "checksum_details": {
            "passport": passport_valid,
            "dob": dob_valid,
            "expiry": expiry_valid,
            "composite": composite_valid
        }
    }


def parse_passport_mrz(mrz_lines: List[str]) -> Dict:
    """
    Parse complete 2-line passport MRZ.
    
    Combines data from both lines and performs validation.
    
    Args:
        mrz_lines: List of 2 MRZ lines (44 chars each)
        
    Returns:
        Complete parsed passport data with validation status
    """
    if not mrz_lines or len(mrz_lines) != 2:
        raise ServiceError("Invalid MRZ format - expected 2 lines", code="MRZ_FORMAT_INVALID")
    
    # Parse both lines (exceptions propagate automatically)
    line1_data = parse_mrz_line1(mrz_lines[0])
    line2_data = parse_mrz_line2(mrz_lines[1])
    
    # Combine data
    result = {
        "success": True,
        "mrz_valid": line2_data.get("checksums_valid", False),
        
        # Identity
        "passport_number": line2_data["passport_number"],
        "surname": line1_data["surname"],
        "given_names": line1_data["given_names"],
        "full_name_english": line1_data["full_name_english"],
        
        # Dates
        "date_of_birth": line2_data["date_of_birth"],
        "expiry_date": line2_data["expiry_date"],
        
        # Other
        "gender": line2_data["gender"],
        "nationality": line2_data["nationality"],
        "issuing_country": line1_data["issuing_country"],
        "document_type": line1_data["document_type"],
        
        # Validation
        "checksum_details": line2_data.get("checksum_details", {}),
        "confidence": 0.99 if line2_data.get("checksums_valid") else 0.85,
        
        # Raw MRZ
        "mrz_line1": mrz_lines[0],
        "mrz_line2": mrz_lines[1]
    }
    
    return result


def extract_mrz_from_text(text_lines: List[str]) -> Optional[List[str]]:
    """
    Extract MRZ lines from OCR text output.
    
    Looks for 2 consecutive lines of 44 characters matching MRZ pattern.
    
    Args:
        text_lines: List of text lines from OCR
        
    Returns:
        List of 2 MRZ lines or None if not found
    """
    mrz_pattern = r'^[A-Z0-9<]{44}$'
    
    for i in range(len(text_lines) - 1):
        line1 = text_lines[i].strip().upper()
        line2 = text_lines[i + 1].strip().upper()
        
        # Check if both lines match MRZ pattern
        if re.match(mrz_pattern, line1) and re.match(mrz_pattern, line2):
            # Additional check: Line 1 should start with P< for passport
            if line1.startswith('P<'):
                return [line1, line2]
    
    return None
