"""
Configuration and Threshold Tests

Tests for configuration settings and threshold validation.
Run with: pytest tests/test_config.py -v
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import (
    FIELD_CONFIGURATIONS,
    ID_PATTERNS,
    NAME_MATCHING_PASS_THRESHOLD,
    NAME_MATCHING_MANUAL_THRESHOLD,
    DATE_TOLERANCE_DAYS,
    SEVERITY_WEIGHTS
)


class TestFieldConfigurations:
    """Test field configuration validity."""
    
    def test_required_fields_configured(self):
        """All required fields should be configured."""
        required_fields = [
            "id_number", "passport_number", "date_of_birth",
            "name_arabic", "name_english", "gender"
        ]
        for field in required_fields:
            assert field in FIELD_CONFIGURATIONS, f"Missing config for {field}"
    
    def test_all_fields_have_required_keys(self):
        """Each field config should have all required keys."""
        required_keys = ["severity", "enabled", "pass_threshold", "manual_threshold", "matching_type"]
        
        for field_name, config in FIELD_CONFIGURATIONS.items():
            for key in required_keys:
                assert key in config, f"Field '{field_name}' missing key '{key}'"
    
    def test_threshold_values_valid(self):
        """Thresholds should be between 0 and 1."""
        for field_name, config in FIELD_CONFIGURATIONS.items():
            assert 0 <= config["pass_threshold"] <= 1, f"Invalid pass_threshold for {field_name}"
            assert 0 <= config["manual_threshold"] <= 1, f"Invalid manual_threshold for {field_name}"
    
    def test_pass_threshold_gte_manual(self):
        """Pass threshold should be >= manual threshold."""
        for field_name, config in FIELD_CONFIGURATIONS.items():
            assert config["pass_threshold"] >= config["manual_threshold"], \
                f"pass_threshold < manual_threshold for {field_name}"
    
    def test_severity_levels_valid(self):
        """Severity should be high, medium, or low."""
        valid_severities = {"high", "medium", "low"}
        for field_name, config in FIELD_CONFIGURATIONS.items():
            assert config["severity"] in valid_severities, \
                f"Invalid severity '{config['severity']}' for {field_name}"


class TestIDPatterns:
    """Test ID pattern configurations."""
    
    def test_yemen_id_pattern(self):
        """Yemen ID pattern should match 11 digits."""
        import re
        pattern = ID_PATTERNS["yemen_id"]["pattern"]
        
        # Valid Yemen IDs
        assert re.match(pattern, "02000005039")
        assert re.match(pattern, "12345678901")
        
        # Invalid
        assert not re.match(pattern, "1234567890")  # 10 digits
        assert not re.match(pattern, "123456789012")  # 12 digits
        assert not re.match(pattern, "0200000503A")  # Contains letter
    
    def test_yemen_passport_pattern(self):
        """Yemen passport pattern should match 8 digits."""
        import re
        pattern = ID_PATTERNS["yemen_passport"]["pattern"]
        
        # Valid
        assert re.match(pattern, "12345678")
        
        # Invalid
        assert not re.match(pattern, "1234567")  # 7 digits
        assert not re.match(pattern, "123456789")  # 9 digits


class TestSeverityWeights:
    """Test severity weight configuration."""
    
    def test_all_severities_have_weights(self):
        """All severity levels should have weights."""
        assert "high" in SEVERITY_WEIGHTS
        assert "medium" in SEVERITY_WEIGHTS
        assert "low" in SEVERITY_WEIGHTS
    
    def test_high_severity_highest_weight(self):
        """High severity should have highest weight."""
        assert SEVERITY_WEIGHTS["high"] > SEVERITY_WEIGHTS["medium"]
        assert SEVERITY_WEIGHTS["medium"] > SEVERITY_WEIGHTS["low"]


class TestThresholdConstants:
    """Test global threshold constants."""
    
    def test_name_matching_thresholds(self):
        """Name matching thresholds should be valid."""
        assert 0 < NAME_MATCHING_PASS_THRESHOLD <= 1
        assert 0 < NAME_MATCHING_MANUAL_THRESHOLD <= 1
        assert NAME_MATCHING_PASS_THRESHOLD >= NAME_MATCHING_MANUAL_THRESHOLD
    
    def test_date_tolerance(self):
        """Date tolerance should be reasonable."""
        assert DATE_TOLERANCE_DAYS >= 0
        assert DATE_TOLERANCE_DAYS <= 7  # Not too lenient


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
