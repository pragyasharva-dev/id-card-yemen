import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from services.expiry_date_service import (
    check_expiry_date,
    validate_document_dates,
    is_document_expired,
    get_expiry_severity,
    DEFAULT_EXPIRING_SOON_DAYS,
    DEFAULT_GRACE_PERIOD_DAYS
)
from utils.date_utils import format_date

def print_section(title):
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")

def run_expiry_check_test(case_name, expiry_date, expected_status=None):
    print(f"\n--- {case_name} ---")
    print(f"Checking date: {expiry_date}")
    
    result = check_expiry_date(expiry_date)
    
    print(f"Status: {result.status.value}")
    print(f"Is Expired: {result.is_expired}")
    print(f"Message: {result.message}")
    print(f"Days Until Expiry: {result.days_until_expiry}")
    print(f"Severity: {get_expiry_severity(result)}")
    
    if expected_status:
        assert result.status.value == expected_status, f"Expected {expected_status}, got {result.status.value}"
        print("[OK] Status validation passed")

def run_full_validation_test(case_name, issuance, expiry, dob):
    print(f"\n--- {case_name} ---")
    print(f"Input: DOB={dob}, Issued={issuance}, Expires={expiry}")
    
    is_valid, message, details = validate_document_dates(issuance, expiry, dob)
    
    print(f"Overall Valid: {is_valid}")
    print(f"Message: {message}")
    if details['warnings']:
        print("Warnings:", details['warnings'])
    else:
        print("Warnings: None")
    print(f"Date Sequence Valid: {details['date_sequence_valid']}")

def main():
    today = datetime.now()
    
    # ---------------------------------------------------------
    # 1. EXPIRY STATUS TESTS
    # ---------------------------------------------------------
    print_section("TESTING EXPIRY STATUS LOGIC")
    
    # Case 1: Valid Date (Future)
    valid_date = format_date(today + timedelta(days=365))
    run_expiry_check_test("Valid Document (Next Year)", valid_date, "valid")
    
    # Case 2: Expiring Soon (Within 90 days)
    soon_date = format_date(today + timedelta(days=30))
    run_expiry_check_test("Expiring Soon (30 days)", soon_date, "expiring_soon")
    
    # Case 3: Expired (Within Grace Period - 10 days ago)
    grace_date = format_date(today - timedelta(days=10))
    run_expiry_check_test("Expired (Grace Period)", grace_date, "expired")
    
    # Case 4: Expired (Critical - 100 days ago)
    expired_date = format_date(today - timedelta(days=100))
    run_expiry_check_test("Expired (Critical)", expired_date, "expired")
    
    # Case 5: Different Date Formats (Testing Integration)
    # Using format DD-MM-YYYY
    next_year = today.year + 1
    mixed_format = f"15-01-{next_year}"
    print(f"\n--- Testing Mixed Format ({mixed_format}) ---")
    result = check_expiry_date(mixed_format)
    print(f"Parsed & Status: {result.status.value} (Should be valid)")

    # ---------------------------------------------------------
    # 2. LOGICAL VALIDATION TESTS
    # ---------------------------------------------------------
    print_section("TESTING LOGICAL CONSISTENCY")
    
    # Case A: Perfect Sequence
    # DOB: 1990, Issued: 2020, Expires: 2025
    run_full_validation_test(
        "Perfect Sequence",
        issuance="2020-01-01",
        expiry=format_date(today + timedelta(days=365)), # Valid expiry
        dob="1990-01-01"
    )
    
    # Case B: Time Travel (Issued before DOB)
    run_full_validation_test(
        "Invalid: Issued before DOB",
        issuance="1980-01-01",
        expiry="2025-01-01",
        dob="1990-01-01"
    )
    
    # Case C: Valid but already expired
    run_full_validation_test(
        "Valid Dates but Expired",
        issuance="2010-01-01",
        expiry="2020-01-01",
        dob="1980-01-01"
    )
    
    # Case D: Anomaly (Validity > 20 years)
    run_full_validation_test(
        "Anomaly: Long Validity",
        issuance="2020-01-01",
        expiry="2050-01-01",
        dob="1990-01-01"
    )

if __name__ == "__main__":
    main()
