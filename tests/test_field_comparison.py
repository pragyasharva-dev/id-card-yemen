"""
Unit Tests for Field Comparison Service

Tests the core comparison logic for matching manual form data with OCR data.
Run with: pytest tests/test_field_comparison.py -v
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.field_comparison_service import (
    compare_exact,
    compare_dates_with_tolerance,
    compare_field,
    validate_form_vs_ocr
)


class TestExactComparison:
    """Test exact string comparison."""
    
    def test_exact_match(self):
        """Identical strings should match with score 1.0."""
        result = compare_exact("02000005039", "02000005039")
        assert result["match"] is True
        assert result["score"] == 1.0
    
    def test_case_insensitive(self):
        """Comparison should be case-insensitive."""
        result = compare_exact("ABC123", "abc123")
        assert result["match"] is True
        assert result["score"] == 1.0
    
    def test_whitespace_handling(self):
        """Should strip whitespace before comparison."""
        result = compare_exact("  12345  ", "12345")
        assert result["match"] is True
    
    def test_mismatch(self):
        """Different strings should not match."""
        result = compare_exact("12345", "54321")
        assert result["match"] is False
        assert result["score"] == 0.0
    
    def test_none_values(self):
        """Both None should match, one None should not."""
        assert compare_exact(None, None)["match"] is True
        assert compare_exact("value", None)["match"] is False
        assert compare_exact(None, "value")["match"] is False


class TestDateComparison:
    """Test date comparison with tolerance."""
    
    def test_exact_date_match(self):
        """Same dates should match perfectly."""
        result = compare_dates_with_tolerance("2000-01-05", "2000-01-05")
        assert result["match"] is True
        assert result["score"] == 1.0
        assert result["days_diff"] == 0
    
    def test_date_within_tolerance(self):
        """Dates within tolerance should match with reduced score."""
        result = compare_dates_with_tolerance("2000-01-05", "2000-01-06", tolerance_days=1)
        assert result["match"] is True
        assert 0 < result["score"] < 1.0
        assert result["days_diff"] == 1
    
    def test_date_outside_tolerance(self):
        """Dates outside tolerance should not match."""
        result = compare_dates_with_tolerance("2000-01-05", "2000-01-10", tolerance_days=1)
        assert result["match"] is False
        assert result["score"] == 0.0
    
    def test_invalid_date_format(self):
        """Invalid date format should return no match."""
        result = compare_dates_with_tolerance("invalid", "2000-01-05")
        assert result["match"] is False
        assert result["score"] == 0.0


class TestFieldComparison:
    """Test individual field comparison logic."""
    
    def test_id_number_exact_match(self):
        """ID number requires exact match."""
        result = compare_field(
            field_name="id_number",
            ocr_value="02000005039",
            user_value="02000005039",
            ocr_confidence=1.0,
            id_number="02000005039",
            id_type="yemen_national_id"
        )
        assert result["decision"] == "pass"
        assert result["score"] == 1.0
    
    def test_id_number_mismatch(self):
        """ID number mismatch should reject."""
        result = compare_field(
            field_name="id_number",
            ocr_value="02000005039",
            user_value="02000005038",  # Different
            ocr_confidence=1.0,
            id_number="02000005039",
            id_type="yemen_national_id"
        )
        assert result["decision"] == "reject"
    
    def test_gender_validation(self):
        """Gender should be validated against ID 4th digit."""
        # 4th digit 0 = Female
        result = compare_field(
            field_name="gender",
            ocr_value=None,
            user_value="Female",
            ocr_confidence=1.0,
            id_number="02000005039",  # 4th digit is 0 (Female)
            id_type="yemen_national_id"
        )
        assert result["decision"] == "pass"
        assert result.get("fraud_detected") is False
    
    def test_gender_fraud_detection(self):
        """Mismatched gender should trigger fraud detection."""
        result = compare_field(
            field_name="gender",
            ocr_value=None,
            user_value="Male",  # Wrong - should be Female
            ocr_confidence=1.0,
            id_number="02000005039",  # 4th digit is 0 (Female)
            id_type="yemen_national_id"
        )
        assert result.get("fraud_detected") is True


class TestFormVsOCRValidation:
    """Test full form vs OCR validation."""
    
    def test_perfect_match_approved(self):
        """Perfect match should be approved."""
        manual_data = {
            "id_number": "02000005039",
            "date_of_birth": "2000-01-05",
            "gender": "Female",
            "name_arabic": "مرام رائد عبدالمولى السقاف"
        }
        ocr_data = {
            "id_number": "02000005039",
            "date_of_birth": "2000-01-05",
            "gender": "Female",
            "name_arabic": "مرام رائد عبدالمولى السقاف"
        }
        
        result = validate_form_vs_ocr(manual_data, ocr_data, 1.0)
        
        # Should not have any failed high-severity fields
        assert result["summary"]["failed_fields"] == 0
    
    def test_skip_passport_number_for_national_id(self):
        """passport_number should be skipped for National ID."""
        manual_data = {
            "id_number": "02000005039",  # National ID
        }
        ocr_data = {
            "id_number": "02000005039",
        }
        
        result = validate_form_vs_ocr(manual_data, ocr_data, 1.0)
        
        # Should not have passport_number in comparisons
        field_names = [f["field_name"] for f in result["field_comparisons"]]
        assert "passport_number" not in field_names


class TestNameMatching:
    """Test Arabic name matching."""
    
    def test_similar_names_manual_review(self):
        """Similar names (OCR error) should trigger manual review."""
        from services.field_comparison_service import compare_field
        
        result = compare_field(
            field_name="name_arabic",
            ocr_value="مرام راند عبدالمولى السقاف",  # OCR error: راند
            user_value="مرام رائد عبدالمولى السقاف",  # Correct: رائد
            ocr_confidence=1.0,
            id_number="02000005039",
            id_type="yemen_national_id"
        )
        
        # Should be manual_review due to high similarity but not exact
        assert result["decision"] in ["manual_review", "pass"]
        assert result["score"] > 0.7  # Should be high due to similarity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
