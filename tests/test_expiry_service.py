"""
Test script for expiry date check service.
"""
from services.expiry_date_service import (
    check_expiry_date, 
    validate_document_dates, 
    get_expiry_severity,
    is_document_expired
)

def run_tests():
    print("=" * 60)
    print("EXPIRY DATE SERVICE TESTS")
    print("=" * 60)
    
    # Test 1: Future date (valid document)
    print("\nTest 1 - Future date (2027-12-31):")
    result = check_expiry_date('2027-12-31')
    print(f"  Status: {result.status.value}")
    print(f"  Is Expired: {result.is_expired}")
    print(f"  Days Until Expiry: {result.days_until_expiry}")
    print(f"  Message: {result.message}")
    print(f"  Severity: {get_expiry_severity(result)}")
    
    # Test 2: Past date (expired document)
    print("\nTest 2 - Past date (2024-01-01):")
    result2 = check_expiry_date('2024-01-01')
    print(f"  Status: {result2.status.value}")
    print(f"  Is Expired: {result2.is_expired}")
    print(f"  Days Since Expiry: {result2.days_since_expiry}")
    print(f"  Is Within Grace: {result2.is_within_grace_period}")
    print(f"  Message: {result2.message}")
    print(f"  Severity: {get_expiry_severity(result2)}")
    
    # Test 3: Expiring soon (within 90 days)
    print("\nTest 3 - Expiring soon (2026-04-01):")
    result3 = check_expiry_date('2026-04-01')
    print(f"  Status: {result3.status.value}")
    print(f"  Is Expired: {result3.is_expired}")
    print(f"  Days Until Expiry: {result3.days_until_expiry}")
    print(f"  Message: {result3.message}")
    print(f"  Severity: {get_expiry_severity(result3)}")
    
    # Test 4: Full document date validation
    print("\nTest 4 - Full validation (DOB: 1990-05-20, Issue: 2020-01-15, Expiry: 2030-01-15):")
    is_valid, msg, details = validate_document_dates(
        issuance_date_str='2020-01-15', 
        expiry_date_str='2030-01-15', 
        date_of_birth_str='1990-05-20'
    )
    print(f"  Valid: {is_valid}")
    print(f"  Message: {msg}")
    print(f"  Date Sequence Valid: {details.get('date_sequence_valid')}")
    print(f"  Validity Period Years: {details.get('validity_period_years')}")
    print(f"  Warnings: {details.get('warnings')}")
    
    # Test 5: Invalid date sequence (issuance before DOB)
    print("\nTest 5 - Invalid date sequence (DOB: 2000-01-01, Issue: 1999-01-01):")
    is_valid, msg, details = validate_document_dates(
        issuance_date_str='1999-01-01', 
        expiry_date_str='2030-01-15', 
        date_of_birth_str='2000-01-01'
    )
    print(f"  Valid: {is_valid}")
    print(f"  Message: {msg}")
    print(f"  Warnings: {details.get('warnings')}")
    
    # Test 6: Quick check utility
    print("\nTest 6 - Quick expired check:")
    print(f"  is_document_expired('2020-01-01'): {is_document_expired('2020-01-01')}")
    print(f"  is_document_expired('2030-01-01'): {is_document_expired('2030-01-01')}")
    
    # Test 7: Different date formats
    print("\nTest 7 - Different date formats:")
    formats = [
        '2027-12-31',    # YYYY-MM-DD
        '2027/12/31',    # YYYY/MM/DD
        '31-12-2027',    # DD-MM-YYYY
        '31/12/2027',    # DD/MM/YYYY
    ]
    for fmt in formats:
        result = check_expiry_date(fmt)
        print(f"  '{fmt}' -> {result.expiry_date} (status: {result.status.value})")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
