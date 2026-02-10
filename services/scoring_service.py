"""
Service for calculating verification scores based on configured weights.
"""
from typing import Dict, List, Optional, Union
from models.v1_schemas import (
    DocumentVerificationScore,
    DataMatchScore,
    FaceAndLivenessScore,
    DataComparisonItem
)
from utils.config import SCORING_WEIGHTS

def calculate_document_verification_score(
    quality_score: float,
    field_confidences: Dict[str, float],
    is_national_id: bool,
    has_back_image: bool
) -> DocumentVerificationScore:
    """
    Calculate Document Verification Score (max 35).
    
    Args:
        quality_score: Overall image quality score (0.0 to 1.0)
        field_confidences: Dictionary of per-field OCR confidence scores
        is_national_id: True if document type is NATIONAL_ID
        has_back_image: True if back image was provided/processed
        
    Returns:
        DocumentVerificationScore object
    """
    doc_weights = SCORING_WEIGHTS["DOCUMENT_VERIFICATION"]
    max_doc_score = doc_weights["MAX_SCORE"]
    
    # Authenticity (0-10) -> Scale quality_score (0-1) to weight
    auth_weight = doc_weights["AUTHENTICITY"]
    auth_score = min(auth_weight, quality_score * auth_weight)
    
    # Quality (0-10) -> Scale quality_score (0-1) to weight
    quality_weight = doc_weights["QUALITY"]
    quality_pts = min(quality_weight, quality_score * quality_weight)
    
    # OCR Confidence (0-10) -> Scale avg_conf (0-1) to weight
    ocr_weight = doc_weights["OCR_CONFIDENCE"]
    # Filter out 0.0 confidences (missing fields) to avoid skewing average
    valid_confs = [v for v in field_confidences.values() if v > 0]
    avg_ocr_conf = sum(valid_confs) / len(valid_confs) if valid_confs else 0.0
    ocr_conf_pts = min(ocr_weight, avg_ocr_conf * ocr_weight)
    
    # Front/Back Match (0-5)
    front_back_weight = doc_weights["FRONT_BACK_MATCH"]
    # Only applicable for National IDs (Passports are single-sided for main data page usually)
    front_back_pts = front_back_weight if has_back_image and is_national_id else 0.0
    
    doc_verification_total = auth_score + quality_pts + ocr_conf_pts + front_back_pts
    
    return DocumentVerificationScore(
        authenticity=round(auth_score, 2),
        quality=round(quality_pts, 2),
        ocr_confidence=round(ocr_conf_pts, 2),
        front_back_match=round(front_back_pts, 2),
        total=round(min(max_doc_score, doc_verification_total), 2)
    )


def calculate_data_match_score(
    data_comparison: List[DataComparisonItem]
) -> DataMatchScore:
    """
    Calculate Data Match Score (max 30).
    
    Args:
        data_comparison: List of field comparison results
        
    Returns:
        DataMatchScore object
    """
    data_weights = SCORING_WEIGHTS["DATA_MATCHING"]
    max_data_score = data_weights["MAX_SCORE"]
    
    id_match_weight = data_weights["ID_NUMBER"]
    name_match_weight = data_weights["NAME_MATCH"]
    
    id_match_pts = 0.0
    name_match_pts = 0.0
    
    for item in data_comparison:
        # Check for ID Number match
        if item.field_name == "id_number" and item.match_result == "MATCH":
            id_match_pts = id_match_weight
            
        # Check for Name match
        elif item.field_name == "full_name" and item.match_result == "MATCH":
            name_match_pts = name_match_weight
    
    data_match_total = id_match_pts + name_match_pts
    
    return DataMatchScore(
        id_number=round(id_match_pts, 2),
        name_match=round(name_match_pts, 2),
        total=round(min(max_data_score, data_match_total), 2)
    )


def calculate_face_liveness_score(
    face_match_score: float,  # Normalized 0-100
    liveness_confidence: float, # Normalized 0-100
    is_live: bool
) -> FaceAndLivenessScore:
    """
    Calculate Face and Liveness Score (max 35).
    
    Args:
        face_match_score: Face match score (0-100)
        liveness_confidence: Liveness confidence score (0-100)
        is_live: Boolean indicating if liveness check passed
        
    Returns:
        FaceAndLivenessScore object
    """
    face_liveness_weights = SCORING_WEIGHTS["FACE_LIVENESS"]
    max_face_score = face_liveness_weights["MAX_SCORE"]
    
    # Face Match (0-20) -> Scale normalized score (0-100) to weight
    face_match_weight = face_liveness_weights["FACE_MATCH"]
    # Normalize 0-100 to 0-1, then multiply by weight
    face_match_pts = min(face_match_weight, (face_match_score / 100.0) * face_match_weight)
    
    # Liveness (0-15) -> Scale liveness confidence (0-100) to weight
    liveness_weight = face_liveness_weights["LIVENESS"]
    if is_live:
        liveness_pts = min(liveness_weight, (liveness_confidence / 100.0) * liveness_weight)
    else:
        liveness_pts = 0.0
    
    face_liveness_total = face_match_pts + liveness_pts
    
    return FaceAndLivenessScore(
        face_match=round(face_match_pts, 2),
        liveness=round(liveness_pts, 2),
        total=round(min(max_face_score, face_liveness_total), 2)
    )
