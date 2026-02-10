"""
Unit tests for scoring service logic.
"""
import os
import sys
import unittest
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.scoring_service import (
    calculate_document_verification_score,
    calculate_data_match_score,
    calculate_face_liveness_score
)
from models.v1_schemas import DataComparisonItem
from utils.config import SCORING_WEIGHTS

class TestScoringService(unittest.TestCase):
    
    def test_document_verification_score_perfect(self):
        """Test perfect document verification score."""
        # Setup perfect conditions
        quality_score = 1.0
        field_confidences = {"name": 0.99, "dob": 0.98} # High confidence
        is_national_id = True
        has_back_image = True
        
        score = calculate_document_verification_score(
            quality_score, field_confidences, is_national_id, has_back_image
        )
        
        # Expect max score (35.0)
        # Auth (10) + Quality (10) + OCR (10) + Front/Back (5) = 35
        self.assertEqual(score.authenticity, 10.0)
        self.assertEqual(score.quality, 10.0)
        # OCR might be slightly less than 10 if avg conf < 1.0
        self.assertAlmostEqual(score.ocr_confidence, 9.85, delta=0.1)
        self.assertEqual(score.front_back_match, 5.0)
        self.assertAlmostEqual(score.total, 34.85, delta=0.1)

    def test_document_verification_score_low_quality(self):
        """Test low quality document verification score."""
        quality_score = 0.5
        field_confidences = {"name": 0.4, "dob": 0.6} # Avg 0.5
        is_national_id = True
        has_back_image = False # Missing back image -> 0 pts
        
        score = calculate_document_verification_score(
            quality_score, field_confidences, is_national_id, has_back_image
        )
        
        # Auth (5.0) + Quality (5.0) + OCR (5.0) + Front/Back (0) = 15.0
        self.assertEqual(score.authenticity, 5.0)
        self.assertEqual(score.quality, 5.0)
        self.assertAlmostEqual(score.ocr_confidence, 5.0, delta=0.1)
        self.assertEqual(score.front_back_match, 0.0)
        self.assertAlmostEqual(score.total, 15.0, delta=0.1)

    def test_data_match_score_perfect(self):
        """Test perfect data match score."""
        comparison_items = [
            DataComparisonItem(fieldName="id_number", matchResult="MATCH"),
            DataComparisonItem(fieldName="full_name", matchResult="MATCH")
        ]
        
        score = calculate_data_match_score(comparison_items)
        
        # ID (20) + Name (10) = 30
        self.assertEqual(score.id_number, 20.0)
        self.assertEqual(score.name_match, 10.0)
        self.assertEqual(score.total, 30.0)

    def test_data_match_score_partial(self):
        """Test partial data match score."""
        comparison_items = [
            DataComparisonItem(fieldName="id_number", matchResult="MISMATCH"),
            DataComparisonItem(fieldName="full_name", matchResult="MATCH")
        ]
        
        score = calculate_data_match_score(comparison_items)
        
        # ID (0) + Name (10) = 10
        self.assertEqual(score.id_number, 0.0)
        self.assertEqual(score.name_match, 10.0)
        self.assertEqual(score.total, 10.0)

    def test_face_liveness_score_perfect(self):
        """Test perfect face and liveness score."""
        face_score = 100.0
        liveness_conf = 100.0
        is_live = True
        
        score = calculate_face_liveness_score(face_score, liveness_conf, is_live)
        
        # Face (20) + Liveness (15) = 35
        self.assertEqual(score.face_match, 20.0)
        self.assertEqual(score.liveness, 15.0)
        self.assertEqual(score.total, 35.0)

    def test_face_liveness_score_spoof(self):
        """Test face match but spoof detected."""
        face_score = 90.0
        liveness_conf = 20.0 # Low confidence
        is_live = False # Spoof detected
        
        score = calculate_face_liveness_score(face_score, liveness_conf, is_live)
        
        # Face (18.0) + Liveness (0.0) = 18.0
        self.assertEqual(score.face_match, 18.0)
        self.assertEqual(score.liveness, 0.0)
        self.assertEqual(score.total, 18.0)

    @patch.dict(SCORING_WEIGHTS["DOCUMENT_VERIFICATION"], {"AUTHENTICITY": 20.0, "QUALITY": 20.0, "MAX_SCORE": 50.0})
    def test_configurable_weights(self):
        """Test that changing weights affects the score."""
        # Mocked weights: Auth=20, Quality=20, Max=50
        quality_score = 0.5
        field_confidences = {"test": 0.0} # Ignore OCR
        
        score = calculate_document_verification_score(
            quality_score, field_confidences, False, False
        )
        
        # Auth (0.5 * 20 = 10) + Quality (0.5 * 20 = 10) = 20.0
        self.assertEqual(score.authenticity, 10.0)
        self.assertEqual(score.quality, 10.0)
        self.assertEqual(score.total, 20.0)

if __name__ == '__main__':
    unittest.main()
