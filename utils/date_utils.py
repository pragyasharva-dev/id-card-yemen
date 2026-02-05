"""
Date Utilities for Yemen ID Cards and Passports.

Provides centralized date formatting and parsing to enforce a single
standard date format (YYYY-MM-DD) across the application.

Usage:
    from utils.date_utils import format_date, parse_date, normalize_date_string
    
    # Convert datetime to string
    date_str = format_date(datetime_obj)  # -> "2024-01-15"
    
    # Parse any common format to datetime
    dt = parse_date("15/01/2024")  # -> datetime(2024, 1, 15)
    
    # Normalize any date string to standard format
    normalized = normalize_date_string("15-01-2024")  # -> "2024-01-15"
"""
from datetime import datetime
from typing import Optional


# =============================================================================
# STANDARD FORMAT CONSTANT
# =============================================================================
STANDARD_DATE_FORMAT = "%Y-%m-%d"

# Common input formats to try when parsing user input
# Order matters: more specific formats first to avoid ambiguity
INPUT_FORMATS = [
    "%Y-%m-%d",   # 2024-01-15 (ISO standard, our output format)
    "%Y/%m/%d",   # 2024/01/15
    "%Y.%m.%d",   # 2024.01.15
    "%d-%m-%Y",   # 15-01-2024 (European)
    "%d/%m/%Y",   # 15/01/2024 (European)
    "%d.%m.%Y",   # 15.01.2024 (European)
    "%Y%m%d",     # 20240115 (compact)
]


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def format_date(date_obj: datetime) -> str:
    """
    Convert a datetime object to the application-wide standard string format.
    
    This is the ONLY function that should be used for date-to-string conversion
    throughout the application to ensure consistency.
    
    Args:
        date_obj: A datetime object
        
    Returns:
        Date string in YYYY-MM-DD format
        
    Example:
        >>> format_date(datetime(2024, 1, 15))
        '2024-01-15'
    """
    return date_obj.strftime(STANDARD_DATE_FORMAT)


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Robustly parse a date string from various common formats.
    
    Tries multiple date formats commonly used in Yemen ID cards, passports,
    and user input. Returns None if no format matches.
    
    Args:
        date_str: Date string in any supported format
        
    Returns:
        datetime object or None if parsing fails
        
    Example:
        >>> parse_date("15/01/2024")
        datetime(2024, 1, 15, 0, 0)
        >>> parse_date("2024-01-15")
        datetime(2024, 1, 15, 0, 0)
    """
    if not date_str:
        return None
    
    # Strip whitespace
    date_str = date_str.strip()
    
    for fmt in INPUT_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def normalize_date_string(date_str: str) -> Optional[str]:
    """
    Take ANY supported date string and return it in YYYY-MM-DD format.
    
    This is useful for normalizing user input before validation or storage.
    Combines parse_date() and format_date() for convenience.
    
    Args:
        date_str: Date string in any supported format
        
    Returns:
        Date string in YYYY-MM-DD format, or None if parsing fails
        
    Example:
        >>> normalize_date_string("15-01-2024")
        '2024-01-15'
        >>> normalize_date_string("2024/01/15")
        '2024-01-15'
    """
    dt = parse_date(date_str)
    if dt:
        return format_date(dt)
    return None
