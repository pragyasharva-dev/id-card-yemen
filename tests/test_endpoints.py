"""
API Endpoint Tests

Tests for all FastAPI endpoints using pytest and httpx.
Run with: pytest tests/test_endpoints.py -v
"""
import pytest
import sys
from pathlib import Path
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


class TestHealthEndpoint:
    """Test /health endpoint."""
    
    def test_health_check(self):
        """Health endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "ocr_ready" in data
        assert "face_recognition_ready" in data


class TestAPIInfo:
    """Test /api endpoint."""
    
    def test_api_info(self):
        """API info should return metadata."""
        response = client.get("/api")
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "e-KYC Verification API"
        assert "version" in data


class TestExtractIDEndpoint:
    """Test /extract-id endpoint."""
    
    def test_extract_id_no_image(self):
        """Should return 422 without image."""
        response = client.post("/extract-id")
        assert response.status_code == 422  # Validation error
    
    def test_extract_id_invalid_image(self):
        """Should handle invalid image gracefully."""
        # Create fake file
        fake_file = BytesIO(b"not an image")
        response = client.post(
            "/extract-id",
            files={"image": ("test.jpg", fake_file, "image/jpeg")}
        )
        # API may return 200 with error in body, or 400/500
        assert response.status_code in [200, 400, 500]


class TestParseIDEndpoint:
    """Test /parse-id endpoint."""
    
    def test_parse_id_no_image(self):
        """Should return 422 without image."""
        response = client.post("/parse-id")
        assert response.status_code == 422


class TestCompareFacesEndpoint:
    """Test /compare-faces endpoint."""
    
    def test_compare_faces_missing_images(self):
        """Should return 422 without both images."""
        response = client.post("/compare-faces")
        assert response.status_code == 422
    
    def test_compare_faces_one_image(self):
        """Should return 422 with only one image."""
        fake_file = BytesIO(b"fake image data")
        response = client.post(
            "/compare-faces",
            files={"image1": ("test1.jpg", fake_file, "image/jpeg")}
        )
        assert response.status_code == 422


class TestTranslateEndpoint:
    """Test /translate endpoint."""
    
    def test_translate_arabic_text(self):
        """Should translate Arabic to English."""
        response = client.post(
            "/translate",
            json={"texts": ["مرحبا"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "translations" in data
        assert len(data["translations"]) == 1
    
    def test_translate_empty_list(self):
        """Should handle empty text list."""
        response = client.post(
            "/translate",
            json={"texts": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["translations"] == []


class TestValidateIDEndpoint:
    """Test /validate-id endpoint."""
    
    def test_validate_id_missing_required_fields(self):
        """Should return 422 without required fields."""
        response = client.post("/validate-id")
        assert response.status_code == 422
    
    def test_validate_id_invalid_id_type(self):
        """Should handle invalid ID type gracefully."""
        fake_file = BytesIO(b"fake image")
        response = client.post(
            "/validate-id",
            data={
                "id_type": "invalid_type",
                "id_number": "12345"
            },
            files={"image_front": ("front.jpg", fake_file, "image/jpeg")}
        )
        # Should return 200 with error in response or 400
        assert response.status_code in [200, 400, 500]


class TestCompareFormOCREndpoint:
    """Test /compare-form-ocr endpoint."""
    
    def test_compare_form_ocr_basic(self):
        """Should compare form data with OCR data."""
        response = client.post(
            "/compare-form-ocr",
            json={
                "manual_data": {
                    "id_number": "02000005039"
                },
                "ocr_data": {
                    "id_number": "02000005039"
                },
                "ocr_confidence": 0.95
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "overall_decision" in data
        assert "field_comparisons" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
