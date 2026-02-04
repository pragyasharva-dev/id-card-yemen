"""
Test Script for Manual Form Submission API

Tests the /submit-id-form endpoint with various scenarios.

Usage:
    python tests/test_manual_form.py
"""

import requests
import json

API_URL = "http://localhost:8000"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_valid_national_id():
    """Test valid Yemen National ID form submission."""
    print_section("Test 1: Valid Yemen National ID")
    
    payload = {
        "id_type": "yemen_national_id",
        "id_number": "12345678901",  # 4th digit = 4 (even) → Female
        "name_arabic": "أحمد محمد علي",
        "name_english": "Ahmed Mohammed Ali",
        "date_of_birth": "1990-05-15",
        # No gender - auto-derived from 4th digit
        "place_of_birth": "صنعاء",
        "issuance_date": "2020-01-10",
        "expiry_date": "2030-01-10"
    }
    
    print(f"\nRequest:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(f"{API_URL}/submit-id-form", json=payload)
        result = response.json()
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Success: {result.get('success')}")
        
        if result.get('validated_data'):
            print(f"\nValidated Data:")
            print(json.dumps(result['validated_data'], indent=2, ensure_ascii=False))
            print(f"\nAuto-derived Gender: {result['validated_data'].get('gender')}")
        
        if result.get('errors'):
            print(f"\nErrors:")
            for error in result['errors']:
                print(f"  - {error['field']}: {error['message']}")
        
        return result
        
    except Exception as e:
        print(f"\nError: {e}")
        return None


def test_valid_passport():
    """Test valid Yemen Passport form submission."""
    print_section("Test 2: Valid Yemen Passport")
    
    payload = {
        "id_type": "yemen_passport",
        "passport_number": "12345678",
        "name_arabic": "فاطمة أحمد",
        "name_english": "Fatima Ahmed",
        "date_of_birth": "1995-08-20",
        "gender": "Female",  # Required for passport
        "place_of_birth": "عدن",
        "issuance_date": "2021-03-15",
        "expiry_date": "2031-03-15"
    }
    
    print(f"\nRequest:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(f"{API_URL}/submit-id-form", json=payload)
        result = response.json()
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Success: {result.get('success')}")
        
        if result.get('validated_data'):
            print(f"\nValidated Data:")
            print(json.dumps(result['validated_data'], indent=2, ensure_ascii=False))
        
        if result.get('errors'):
            print(f"\nErrors:")
            for error in result['errors']:
                print(f"  - {error['field']}: {error['message']}")
        
        return result
        
    except Exception as e:
        print(f"\nError: {e}")
        return None


def test_invalid_id_number():
    """Test invalid ID number (wrong length)."""
    print_section("Test 3: Invalid ID Number (Too Short)")
    
    payload = {
        "id_type": "yemen_national_id",
        "id_number": "123456",  # Only 6 digits instead of 11
        "name_arabic": "محمد علي",
        "name_english": "Mohammed Ali",
        "date_of_birth": "1988-12-01",
        "place_of_birth": "تعز"
    }
    
    print(f"\nRequest:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(f"{API_URL}/submit-id-form", json=payload)
        result = response.json()
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Success: {result.get('success')}")
        
        if result.get('errors'):
            print(f"\nValidation Errors:")
            for error in result['errors']:
                print(f"  - {error['field']}: {error['message']}")
        
        return result
        
    except Exception as e:
        print(f"\nError: {e}")
        return None


def test_invalid_name():
    """Test invalid name (contains numbers)."""
    print_section("Test 4: Invalid Name (Contains Numbers)")
    
    payload = {
        "id_type": "yemen_national_id",
        "id_number": "12345678901",
        "name_arabic": "أحمد123",  # Invalid: contains numbers
        "name_english": "Ahmed Mohammed",
        "date_of_birth": "1992-06-10"
    }
    
    print(f"\nRequest:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(f"{API_URL}/submit-id-form", json=payload)
        result = response.json()
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Success: {result.get('success')}")
        
        if result.get('errors'):
            print(f"\nValidation Errors:")
            for error in result['errors']:
                print(f"  - {error['field']}: {error['message']}")
        
        return result
        
    except Exception as e:
        print(f"\nError: {e}")
        return None


def test_gender_for_national_id():
    """Test that gender should NOT be provided for National ID."""
    print_section("Test 5: Gender Provided for National ID (Should Fail)")
    
    payload = {
        "id_type": "yemen_national_id",
        "id_number": "12345678901",
        "name_arabic": "سعيد أحمد",
        "name_english": "Saeed Ahmed",
        "date_of_birth": "1985-03-22",
        "gender": "Male",  # Should NOT be provided - auto-derived
        "place_of_birth": "الحديدة"
    }
    
    print(f"\nRequest:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(f"{API_URL}/submit-id-form", json=payload)
        result = response.json()
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Success: {result.get('success')}")
        
        if result.get('errors'):
            print(f"\nValidation Errors:")
            for error in result['errors']:
                print(f"  - {error['field']}: {error['message']}")
        
        return result
        
    except Exception as e:
        print(f"\nError: {e}")
        return None


def test_missing_gender_for_passport():
    """Test that gender is required for Passport."""
    print_section("Test 6: Missing Gender for Passport (Should Fail)")
    
    payload = {
        "id_type": "yemen_passport",
        "passport_number": "87654321",
        "name_arabic": "ليلى حسن",
        "name_english": "Layla Hassan",
        "date_of_birth": "1998-11-05",
        # Missing gender - required for passport
        "place_of_birth": "إب"
    }
    
    print(f"\nRequest:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(f"{API_URL}/submit-id-form", json=payload)
        result = response.json()
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Success: {result.get('success')}")
        
        if result.get('errors'):
            print(f"\nValidation Errors:")
            for error in result['errors']:
                print(f"  - {error['field']}: {error['message']}")
        
        return result
        
    except Exception as e:
        print(f"\nError: {e}")
        return None


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  Manual Form Submission API Test Suite")
    print("=" * 80)
    
    # Test server connectivity
    print("\nChecking API server...")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ API server is running")
        else:
            print("✗ API server responded with error")
            return
    except:
        print("✗ Could not connect to API server")
        print("  Please start the server with: uvicorn main:app --reload")
        return
    
    # Run tests
    test_valid_national_id()
    test_valid_passport()
    test_invalid_id_number()
    test_invalid_name()
    test_gender_for_national_id()
    test_missing_gender_for_passport()
    
    print("\n" + "=" * 80)
    print("  Test Suite Complete")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
