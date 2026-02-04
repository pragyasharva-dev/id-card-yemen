"""
Pytest Configuration and Fixtures

Shared fixtures for all tests in the e-KYC test suite.
Run with: pytest -v
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_yemen_id():
    """Sample Yemen National ID data for testing."""
    return {
        "id_number": "02000005039",
        "name_arabic": "مرام رائد عبدالمولى السقاف",
        "name_english": None,
        "date_of_birth": "2000-01-05",
        "gender": "Female",
        "place_of_birth": "امانة العاصمة - معين",
        "issuance_date": "2017-05-24",
        "expiry_date": "2027-05-23",
        "issuing_authority": "مركز-1-صنعاء"
    }


@pytest.fixture
def sample_yemen_passport():
    """Sample Yemen Passport data for testing."""
    return {
        "passport_number": "12345678",
        "surname": "AL-SAQAF",
        "given_names": "MARAM RAED",
        "nationality": "YEM",
        "date_of_birth": "2000-01-05",
        "expiry_date": "2030-01-05",
        "gender": "Female"
    }


@pytest.fixture
def ocr_service():
    """Get OCR service instance."""
    from services.ocr_service import get_ocr_service
    return get_ocr_service()


@pytest.fixture
def field_comparator():
    """Get field comparison service."""
    from services.field_comparison_service import validate_form_vs_ocr
    return validate_form_vs_ocr


@pytest.fixture
def temp_image_file(tmp_path):
    """Create a temporary dummy image file for testing."""
    image_path = tmp_path / "test_image.jpg"
    
    # Create a minimal valid JPEG file (1x1 black pixel)
    # This ensures image loading functions don't crash
    valid_jpeg = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00'
        b'\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f'
        b'\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11'
        b'\x08\x00\x01\x00\x01\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\bf\xa2\x8a\x28\x00\xff\xd9'
    )
    image_path.write_bytes(valid_jpeg)
    return str(image_path)


@pytest.fixture
def id_card_path(temp_image_file):
    """Fixture for ID card image path."""
    return temp_image_file


@pytest.fixture
def image_path(temp_image_file):
    """Fixture for generic image path."""
    return temp_image_file


@pytest.fixture
def selfie_path(temp_image_file):
    """Fixture for selfie image path."""
    return temp_image_file


@pytest.fixture
def id_card_front_path(temp_image_file):
    """Fixture for front ID card path."""
    return temp_image_file


@pytest.fixture
def id_card_back_path(temp_image_file):
    """Fixture for back ID card path."""
    return temp_image_file


@pytest.fixture
def image(temp_image_file):
    """Fixture for 'image' argument used in some tests."""
    return temp_image_file
