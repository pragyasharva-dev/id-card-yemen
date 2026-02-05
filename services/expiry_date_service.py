"""
Expiry Date Check Service

Validates ID card/passport expiry dates and determines document validity status.
Provides detailed information about:
- Whether the document is expired
- Days until expiry or days since expiry
- Expiry status (valid, expiring_soon, expired)
- Grace period handling
"""
from datetime import datetime, date
from typing import Optional, Tuple, Literal
from dataclasses import dataclass
from enum import Enum

from utils.date_utils import parse_date, format_date


class ExpiryStatus(str, Enum):
    """Document expiry status."""
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class ExpiryCheckResult:
    """Result of expiry date validation."""
    is_expired: bool
    status: ExpiryStatus
    expiry_date: Optional[str]  # YYYY-MM-DD format
    days_until_expiry: Optional[int]  # Negative if expired
    days_since_expiry: Optional[int]  # Only set if expired
    is_within_grace_period: bool
    message: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "is_expired": self.is_expired,
            "status": self.status.value,
            "expiry_date": self.expiry_date,
            "days_until_expiry": self.days_until_expiry,
            "days_since_expiry": self.days_since_expiry,
            "is_within_grace_period": self.is_within_grace_period,
            "message": self.message
        }


# Default configuration
DEFAULT_EXPIRING_SOON_DAYS = 90  # Warn if expiring within 90 days
DEFAULT_GRACE_PERIOD_DAYS = 30  # Grace period after expiry


def parse_date_string(date_str: str) -> Optional[date]:
    """
    Parse a date string using centralized utilities.
    Returns date object for internal calculations.
    """
    dt = parse_date(date_str)
    return dt.date() if dt else None


def check_expiry_date(
    expiry_date_str: Optional[str],
    reference_date: Optional[date] = None,
    expiring_soon_days: int = DEFAULT_EXPIRING_SOON_DAYS,
    grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
) -> ExpiryCheckResult:
    """
    Check if a document's expiry date is valid.
    
    Args:
        expiry_date_str: Expiry date string in YYYY-MM-DD or similar format
        reference_date: Date to check against (defaults to today)
        expiring_soon_days: Number of days before expiry to trigger "expiring_soon" status
        grace_period_days: Number of days after expiry for grace period
        
    Returns:
        ExpiryCheckResult with detailed validation information
    """
    # Handle missing expiry date
    if not expiry_date_str:
        return ExpiryCheckResult(
            is_expired=False,
            status=ExpiryStatus.UNKNOWN,
            expiry_date=None,
            days_until_expiry=None,
            days_since_expiry=None,
            is_within_grace_period=False,
            message="Expiry date not provided or could not be extracted"
        )
    
    # Parse the expiry date
    expiry_date = parse_date_string(expiry_date_str)
    if not expiry_date:
        return ExpiryCheckResult(
            is_expired=False,
            status=ExpiryStatus.UNKNOWN,
            expiry_date=expiry_date_str,
            days_until_expiry=None,
            days_since_expiry=None,
            is_within_grace_period=False,
            message=f"Could not parse expiry date: {expiry_date_str}"
        )
    
    # Use today if no reference date provided
    if reference_date is None:
        reference_date = date.today()
    
    # Calculate days difference
    days_diff = (expiry_date - reference_date).days
    formatted_expiry = format_date(datetime.combine(expiry_date, datetime.min.time()))
    
    # Document is expired
    if days_diff < 0:
        days_since_expiry = abs(days_diff)
        is_within_grace = days_since_expiry <= grace_period_days
        
        if is_within_grace:
            message = f"Document expired {days_since_expiry} day(s) ago, but within {grace_period_days}-day grace period"
        else:
            message = f"Document expired {days_since_expiry} day(s) ago"
        
        return ExpiryCheckResult(
            is_expired=True,
            status=ExpiryStatus.EXPIRED,
            expiry_date=formatted_expiry,
            days_until_expiry=days_diff,  # Negative value
            days_since_expiry=days_since_expiry,
            is_within_grace_period=is_within_grace,
            message=message
        )
    
    # Document expires today
    if days_diff == 0:
        return ExpiryCheckResult(
            is_expired=False,
            status=ExpiryStatus.EXPIRING_SOON,
            expiry_date=formatted_expiry,
            days_until_expiry=0,
            days_since_expiry=None,
            is_within_grace_period=False,
            message="Document expires today"
        )
    
    # Document is expiring soon
    if days_diff <= expiring_soon_days:
        return ExpiryCheckResult(
            is_expired=False,
            status=ExpiryStatus.EXPIRING_SOON,
            expiry_date=formatted_expiry,
            days_until_expiry=days_diff,
            days_since_expiry=None,
            is_within_grace_period=False,
            message=f"Document will expire in {days_diff} day(s)"
        )
    
    # Document is valid
    return ExpiryCheckResult(
        is_expired=False,
        status=ExpiryStatus.VALID,
        expiry_date=formatted_expiry,
        days_until_expiry=days_diff,
        days_since_expiry=None,
        is_within_grace_period=False,
        message=f"Document is valid for {days_diff} more day(s)"
    )


def validate_document_dates(
    issuance_date_str: Optional[str] = None,
    expiry_date_str: Optional[str] = None,
    date_of_birth_str: Optional[str] = None
) -> Tuple[bool, str, dict]:
    """
    Perform comprehensive date validation for a document.
    
    Checks:
    1. Expiry date validity
    2. Issuance date is before expiry date
    3. Issuance date is after date of birth
    4. Reasonable validity period (e.g., ID cards typically valid 5-15 years)
    
    Args:
        issuance_date_str: Document issuance date
        expiry_date_str: Document expiry date
        date_of_birth_str: Holder's date of birth
        
    Returns:
        Tuple of (is_valid, message, details_dict)
    """
    details = {
        "expiry_check": None,
        "date_sequence_valid": True,
        "validity_period_days": None,
        "warnings": []
    }
    
    # Check expiry date
    expiry_result = check_expiry_date(expiry_date_str)
    details["expiry_check"] = expiry_result.to_dict()
    
    # Parse all dates
    issuance_date = parse_date_string(issuance_date_str) if issuance_date_str else None
    expiry_date = parse_date_string(expiry_date_str) if expiry_date_str else None
    dob = parse_date_string(date_of_birth_str) if date_of_birth_str else None
    
    # Check date sequence: DOB < Issuance < Expiry
    if dob and issuance_date:
        if issuance_date <= dob:
            details["date_sequence_valid"] = False
            details["warnings"].append("Issuance date cannot be before or on date of birth")
    
    if issuance_date and expiry_date:
        if expiry_date <= issuance_date:
            details["date_sequence_valid"] = False
            details["warnings"].append("Expiry date must be after issuance date")
        else:
            # Calculate validity period
            validity_days = (expiry_date - issuance_date).days
            details["validity_period_days"] = validity_days
            details["validity_period_years"] = round(validity_days / 365.25, 1)
            
            # Warn about unusual validity periods
            validity_years = validity_days / 365.25
            if validity_years < 1:
                details["warnings"].append(f"Unusually short validity period: {validity_days} days")
            elif validity_years > 20:
                details["warnings"].append(f"Unusually long validity period: {round(validity_years, 1)} years")
    
    # Determine overall validity
    is_valid = (
        not expiry_result.is_expired and 
        details["date_sequence_valid"] and
        len(details["warnings"]) == 0
    )
    
    if expiry_result.is_expired:
        message = f"Document is expired: {expiry_result.message}"
    elif not details["date_sequence_valid"]:
        message = "Invalid date sequence detected"
    elif details["warnings"]:
        message = "Document dates valid with warnings"
    else:
        message = "All document dates are valid"
    
    return is_valid, message, details


def get_expiry_severity(expiry_result: ExpiryCheckResult) -> Literal["critical", "warning", "info", "none"]:
    """
    Get severity level for an expiry check result.
    
    Used for UI display and decision-making.
    
    Args:
        expiry_result: Result from check_expiry_date
        
    Returns:
        Severity level string
    """
    if expiry_result.status == ExpiryStatus.EXPIRED:
        if expiry_result.is_within_grace_period:
            return "warning"
        return "critical"
    elif expiry_result.status == ExpiryStatus.EXPIRING_SOON:
        if expiry_result.days_until_expiry is not None and expiry_result.days_until_expiry <= 30:
            return "warning"
        return "info"
    elif expiry_result.status == ExpiryStatus.UNKNOWN:
        return "warning"
    return "none"


# Convenience function for quick checks
def is_document_expired(expiry_date_str: Optional[str]) -> bool:
    """
    Quick check if a document is expired.
    
    Args:
        expiry_date_str: Expiry date string
        
    Returns:
        True if expired, False otherwise (including if date cannot be parsed)
    """
    result = check_expiry_date(expiry_date_str)
    return result.is_expired
