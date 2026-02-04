# Tests Directory

This directory contains all test scripts for the Yemen e-KYC system.

## Test Files

- **`test.py`** - Basic OCR and face recognition tests
- **`test_api.py`** - API endpoint tests
- **`test_verify_enhanced.py`** - Enhanced verification flow tests
- **`test_place_of_birth.py`** - Place of Birth extraction and validation tests

## Running Tests

### Place of Birth Tests
```bash
# Test OCR extraction from an ID card image
python tests/test_place_of_birth.py --image path/to/id_card.jpg

# Test validation logic
python tests/test_place_of_birth.py --test-validation

# Run all tests
python tests/test_place_of_birth.py --all
```

### API Tests
```bash
python tests/test_api.py
```

### Verification Tests
```bash
python tests/test_verify_enhanced.py
```

### Basic Tests
```bash
python tests/test.py
```
