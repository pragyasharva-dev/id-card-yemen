"""
Field Comparison Service for OCR-to-Form Data Matching

Compares OCR-extracted data with manually entered form data using
configurable severity levels and field-specific thresholds per SOW requirements.

Features:
- Exact matching for critical fields (ID number, DOB, gender)
- Fuzzy matching for names (uses name_matching_service)
- Token-based matching for place of birth (uses place_of_birth_service)
- Gender fraud detection (validates against 4th digit of ID)
- Severity-based decision logic (high/medium/low)
- Configurable thresholds per field
- Weighted scoring by severity
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from services.name_matching_service import validate_name_match_simple
from services.place_of_birth_service import validate_place_of_birth
from utils.config import (
    FIELD_CONFIGURATIONS, 
    DATE_TOLERANCE_DAYS, 
    SEVERITY_WEIGHTS
)
from utils.date_utils import parse_date


def compare_exact(ocr_value: Optional[str], user_value: Optional[str]) -> Dict:
    """
    Exact string comparison for critical fields.
    Case-insensitive for ID numbers.
    
    Args:
        ocr_value: Value extracted from OCR
        user_value: Value entered by user
        
    Returns:
        {"match": bool, "score": float}
    """
    # Handle None values
    if ocr_value is None and user_value is None:
        return {"match": True, "score": 1.0}
    
    if ocr_value is None or user_value is None:
        return {"match": False, "score": 0.0}
    
    # Normalize and compare (case-insensitive)
    ocr_normalized = str(ocr_value).strip().upper()
    user_normalized = str(user_value).strip().upper()
    
    match = ocr_normalized == user_normalized
    score = 1.0 if match else 0.0
    
    return {"match": match, "score": score}


def compare_dates_with_tolerance(
    ocr_date: Optional[str],
    user_date: Optional[str],
    tolerance_days: int = DATE_TOLERANCE_DAYS
) -> Dict:
    """
    Compare dates with optional tolerance for OCR errors.
    
    Args:
        ocr_date: Date from OCR (YYYY-MM-DD)
        user_date: Date from user (YYYY-MM-DD)
        tolerance_days: Days tolerance for OCR errors
        
    Returns:
        {"match": bool, "score": float, "days_diff": int}
    """
    # Handle None values
    if ocr_date is None and user_date is None:
        return {"match": True, "score": 1.0, "days_diff": 0}
    
    if ocr_date is None or user_date is None:
        return {"match": False, "score": 0.0, "days_diff": None}
    
    try:
        ocr_dt = parse_date(ocr_date)
        user_dt = parse_date(user_date)
        
        if ocr_dt is None or user_dt is None:
            return {"match": False, "score": 0.0, "days_diff": None}
        
        days_diff = abs((ocr_dt - user_dt).days)
        
        if days_diff == 0:
            return {"match": True, "score": 1.0, "days_diff": 0}
        elif days_diff <= tolerance_days:
            # Within tolerance - partial score
            score = 1.0 - (days_diff / (tolerance_days + 1))
            return {"match": True, "score": score, "days_diff": days_diff}
        else:
            return {"match": False, "score": 0.0, "days_diff": days_diff}
            
    except ValueError:
        # Invalid date format
        return {"match": False, "score": 0.0, "days_diff": None}


def compare_gender_with_fraud_check(
    ocr_gender: Optional[str],
    user_gender: Optional[str],
    id_number: str,
    id_type: str = "yemen_national_id"
) -> Dict:
    """
    Compare gender with fraud detection based on 4th digit of ID number.
    
    Yemen National ID logic:
    - 4th digit = 0 → Female
    - 4th digit = 1 → Male
    
    Yemen Passport logic:
    - Simple gender comparison (no 4th digit check)
    
    Fraud detection (National ID only):
    - If OCR gender doesn't match 4th digit → fraud alert
    - If user gender doesn't match 4th digit → fraud alert
    
    Args:
        ocr_gender: Gender from OCR
        user_gender: Gender from user input
        id_number: National ID or Passport number
        id_type: Type of ID (yemen_national_id or yemen_passport)
        
    Returns:
        {
            "match": bool,
            "score": float,
            "fraud_detected": bool,
            "fraud_reason": str,
            "expected_gender": str
        }
    """
    result = {
        "match": False,
        "score": 0.0,
        "fraud_detected": False,
        "fraud_reason": None,
        "expected_gender": None
    }
    
    # For passports: simple comparison (no 4th digit check)
    if id_type == "yemen_passport":
        if ocr_gender and user_gender:
            result["match"] = (ocr_gender == user_gender)
            result["score"] = 1.0 if result["match"] else 0.0
        elif ocr_gender or user_gender:
            # One missing - can't validate
            result["match"] = False
            result["score"] = 0.0
        else:
            # Both missing
            result["match"] = True
            result["score"] = 1.0
        return result
    
    # For National ID: derive expected gender from 4th digit
    if id_number and len(id_number) >= 4:
        try:
            fourth_digit = int(id_number[3])
            if fourth_digit == 0:
                expected_gender = "Female"
            elif fourth_digit == 1:
                expected_gender = "Male"
            else:
                # Invalid 4th digit
                result["fraud_detected"] = True
                result["fraud_reason"] = f"Invalid 4th digit in ID: {fourth_digit} (must be 0 or 1)"
                return result
                
            result["expected_gender"] = expected_gender
            
            # Check if OCR matches expected
            if ocr_gender and ocr_gender != expected_gender:
                result["fraud_detected"] = True
                result["fraud_reason"] = f"OCR gender '{ocr_gender}' doesn't match 4th digit (expected '{expected_gender}')"
                return result
            
            # Check if user input matches expected
            if user_gender and user_gender != expected_gender:
                result["fraud_detected"] = True
                result["fraud_reason"] = f"User gender '{user_gender}' doesn't match 4th digit (expected '{expected_gender}')"
                return result
            
            # Check if OCR matches user input
            if ocr_gender and user_gender:
                result["match"] = (ocr_gender == user_gender)
                result["score"] = 1.0 if result["match"] else 0.0
            else:
                # One is missing - use expected gender
                result["match"] = True
                result["score"] = 1.0
                
        except (ValueError, IndexError):
            result["fraud_detected"] = True
            result["fraud_reason"] = "Invalid ID number format for gender validation"
    
    return result


def compare_field(
    field_name: str,
    ocr_value: any,
    user_value: any,
    ocr_confidence: float,
    id_number: Optional[str] = None,
    id_type: str = "yemen_national_id"  # NEW: ID type for gender validation
) -> Dict:
    """
    Compare a single field using appropriate matching strategy.
    
    Args:
        field_name: Name of the field to compare
        ocr_value: Value from OCR
        user_value: Value from user input
        ocr_confidence: Overall OCR confidence
        id_number: ID number (required for gender fraud check)
        id_type: Type of ID (yemen_national_id or yemen_passport)
        
    Returns:
        {
            "field_name": str,
            "severity": str,
            "matching_type": str,
            "match": bool,
            "score": float,
            "ocr_value": any,
            "user_value": any,
            "decision": "pass" | "manual_review" | "reject",
            "reason": str
        }
    """
    # Get field configuration
    field_config = FIELD_CONFIGURATIONS.get(field_name)
    
    if not field_config:
        # Field not configured - skip
        return None
    
    if not field_config.get("enabled", True):
        # Field disabled - skip
        return None
    
    severity = field_config["severity"]
    matching_type = field_config["matching_type"]
    pass_threshold = field_config["pass_threshold"]
    manual_threshold = field_config["manual_threshold"]
    
    result = {
        "field_name": field_name,
        "severity": severity,
        "matching_type": matching_type,
        "match": False,
        "score": 0.0,
        "ocr_value": ocr_value,
        "user_value": user_value,
        "decision": "manual_review",
        "reason": ""
    }
    
    # Handle missing values based on severity
    if ocr_value is None and user_value is None:
        if severity == "high":
            result["decision"] = "reject"
            result["reason"] = f"High severity field '{field_name}' missing in both OCR and user input"
            result["score"] = 0.0
            return result
        else:
            # Medium/Low severity: manual review with null score
            result["decision"] = "manual_review"
            result["reason"] = f"{severity.capitalize()} severity field '{field_name}' missing in both sources"
            result["score"] = 0.0
            return result
    
    # Perform matching based on type
    if matching_type == "exact":
        if field_name == "gender":
            # Special handling for gender with fraud check
            gender_result = compare_gender_with_fraud_check(
                ocr_value, user_value, id_number, id_type
            )
            result["match"] = gender_result["match"]
            result["score"] = gender_result["score"]
            result["fraud_detected"] = gender_result.get("fraud_detected", False)
            result["fraud_reason"] = gender_result.get("fraud_reason")
            result["expected_gender"] = gender_result.get("expected_gender")
        elif field_name == "date_of_birth":
            # DOB: EXACT match ONLY - NO tolerance (high severity per SOW)
            exact_result = compare_exact(ocr_value, user_value)
            result["match"] = exact_result["match"]
            result["score"] = exact_result["score"]
        elif field_name in ["issuance_date", "expiry_date"]:
            # Issuance/Expiry: Allow tolerance (medium severity)
            date_result = compare_dates_with_tolerance(ocr_value, user_value)
            result["match"] = date_result["match"]
            result["score"] = date_result["score"]
            result["days_diff"] = date_result.get("days_diff")
        else:
            # Standard exact match for other fields
            exact_result = compare_exact(ocr_value, user_value)
            result["match"] = exact_result["match"]
            result["score"] = exact_result["score"]
    
    elif matching_type == "fuzzy":
        # Use name matching service with error handling
        if field_name == "name_arabic":
            language = "arabic"
        elif field_name == "name_english":
            language = "english"
        else:
            language = "arabic"  # default
        
        if ocr_value and user_value:
            try:
                name_result = validate_name_match_simple(
                    ocr_name=ocr_value,
                    user_name=user_value,
                    language=language,
                    ocr_confidence=ocr_confidence,
                    pass_threshold=pass_threshold,
                    manual_threshold=manual_threshold
                )
                result["match"] = (name_result["final_score"] >= pass_threshold)
                result["score"] = name_result["final_score"]
                result["comparison_details"] = name_result["comparison"]
            except Exception as e:
                # Service error: fallback to manual review
                result["score"] = 0.0
                result["decision"] = "manual_review"
                result["reason"] = f"Name matching service error: {str(e)}"
                return result
        else:
            result["score"] = 0.0
    
    elif matching_type == "token":
        # Use place of birth service with error handling
        if ocr_value or user_value:
            try:
                pob_result = validate_place_of_birth(
                    ocr_raw=ocr_value,
                    user_input=user_value,
                    ocr_confidence=ocr_confidence
                )
                result["match"] = (pob_result["matching_score"] >= pass_threshold)
                result["score"] = pob_result["matching_score"]
                result["pob_details"] = {
                    "normalized": pob_result["normalized"],
                    "decision": pob_result["decision"],
                    "reason": pob_result["reason"]
                }
            except Exception as e:
                # Service error: fallback to manual review
                result["score"] = 0.0
                result["decision"] = "manual_review"
                result["reason"] = f"Place of birth service error: {str(e)}"
                return result
        else:
            result["score"] = 0.0
    
    # Determine decision based on severity and score
    if result.get("fraud_detected"):
        result["decision"] = "reject"
        result["reason"] = result.get("fraud_reason", "Fraud detected")
    elif result["score"] >= pass_threshold:
        result["decision"] = "pass"
        result["reason"] = f"Score {result['score']:.2f} meets pass threshold"
    elif severity == "high" and result["score"] < manual_threshold:
        result["decision"] = "reject"
        result["reason"] = f"High severity field score {result['score']:.2f} below threshold {manual_threshold}"
    else:
        result["decision"] = "manual_review"
        result["reason"] = f"Score {result['score']:.2f} requires manual review"
    
    return result


def validate_form_vs_ocr(
    manual_data: Dict,
    ocr_data: Dict,
    ocr_confidence: float = 1.0
) -> Dict:
    """
    Main orchestrator: Compare all fields between manual and OCR data.
    
    Uses configurable weighted scoring where high-severity fields contribute
    more to overall score than low-severity fields.
    
    Args:
        manual_data: Manually entered form data
        ocr_data: OCR extracted data
        ocr_confidence: Overall OCR confidence score
        
    Returns:
        {
            "overall_decision": "approved" | "manual_review" | "rejected",
            "overall_score": float,
            "field_comparisons": [FieldComparisonResult],
            "summary": {
                "total_fields": int,
                "passed_fields": int,
                "review_fields": int,
                "failed_fields": int
            },
            "recommendations": [str]
        }
    """
    field_comparisons = []
    
    # Detect ID type
    id_number = manual_data.get("id_number")
    passport_number = manual_data.get("passport_number")
    
    if passport_number:
        id_type = "yemen_passport"
        id_value = passport_number
    elif id_number:
        id_type = "yemen_national_id"
        id_value = id_number
    else:
        id_type = "yemen_national_id"  # default
        id_value = None
    
    # Define which fields to skip based on ID type
    skip_fields = {
        "yemen_national_id": ["passport_number"],  # Skip passport_number for National ID
        "yemen_passport": ["id_number"]  # Skip id_number for Passport
    }
    fields_to_skip = skip_fields.get(id_type, [])
    
    # Fields that are optional (skip if user didn't provide, even if OCR found something)
    # These are fields that may have OCR noise but user intentionally left blank
    optional_if_empty = {
        "yemen_national_id": ["name_english"],  # English name not always on Yemen National ID
        "yemen_passport": []
    }
    optional_fields = optional_if_empty.get(id_type, [])
    
    # Compare each configured field
    for field_name in FIELD_CONFIGURATIONS.keys():
        
        # Skip fields not relevant for this ID type
        if field_name in fields_to_skip:
            continue
        
        ocr_value = ocr_data.get(field_name)
        user_value = manual_data.get(field_name)
        
        # Skip optional fields if user didn't provide a value (OCR may have garbage)
        if field_name in optional_fields and user_value is None:
            continue
        
        # Skip comparison if user didn't provide a value AND it's not a required field
        # (Only compare fields user actually filled in, unless they're high severity)
        field_config = FIELD_CONFIGURATIONS.get(field_name, {})
        is_high_severity = field_config.get("severity") == "high"
        
        # Skip non-high-severity fields that user didn't fill
        if user_value is None and ocr_value is not None:
            if not is_high_severity:
                continue  # Skip optional fields user didn't fill
        
        field_result = compare_field(
            field_name=field_name,
            ocr_value=ocr_value,
            user_value=user_value,
            ocr_confidence=ocr_confidence,
            id_number=id_value,
            id_type=id_type
        )
        
        if field_result:
            field_comparisons.append(field_result)
    
    # Calculate summary
    total_fields = len(field_comparisons)
    passed_fields = sum(1 for f in field_comparisons if f["decision"] == "pass")
    failed_fields = sum(1 for f in field_comparisons if f["decision"] == "reject")
    review_fields = sum(1 for f in field_comparisons if f["decision"] == "manual_review")
    
    # Calculate WEIGHTED overall score (for reporting/analytics only)
    severity_totals = {"high": 0.0, "medium": 0.0, "low": 0.0}
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    
    for field in field_comparisons:
        severity = field["severity"]
        severity_totals[severity] += field["score"]
        severity_counts[severity] += 1
    
    # Calculate weighted average
    weighted_score = 0.0
    for severity, weight in SEVERITY_WEIGHTS.items():
        if severity_counts[severity] > 0:
            avg_severity_score = severity_totals[severity] / severity_counts[severity]
            weighted_score += avg_severity_score * weight
    
    overall_score = weighted_score
    
    # ========================================
    # SOW-COMPLIANT DECISION LOGIC
    # ========================================
    # Decisions are made PURELY based on field-level statuses
    # NOT on overall score thresholds
    
    overall_decision = "approved"
    recommendations = []
    
    # RULE 1: REJECTED - Critical/high-severity fields fail beyond tolerance
    # "Rejected (critical/high-severity fields fail beyond allowed tolerance)"
    high_severity_failed = [
        f for f in field_comparisons 
        if f["severity"] == "high" and f["decision"] == "reject"
    ]
    
    if high_severity_failed:
        overall_decision = "rejected"
        failed_names = [f["field_name"] for f in high_severity_failed]
        recommendations.append(f"High-severity fields failed: {', '.join(failed_names)}")
        
        # Add fraud warnings if applicable
        fraud_fields = [f for f in high_severity_failed if f.get("fraud_detected")]
        if fraud_fields:
            fraud_names = [f["field_name"] for f in fraud_fields]
            recommendations.append(f"⚠️ FRAUD ALERT: {', '.join(fraud_names)}")
    
    # RULE 2: MANUAL REVIEW - Medium/low severity mismatches OR any field needs review
    # "Flagged for manual review (medium or low-severity mismatches, or borderline cases)"
    elif review_fields > 0:
        overall_decision = "manual_review"
        
        # Categorize review fields by severity
        high_review = [f["field_name"] for f in field_comparisons 
                      if f["severity"] == "high" and f["decision"] == "manual_review"]
        medium_review = [f["field_name"] for f in field_comparisons 
                        if f["severity"] == "medium" and f["decision"] == "manual_review"]
        low_review = [f["field_name"] for f in field_comparisons 
                     if f["severity"] == "low" and f["decision"] == "manual_review"]
        
        if high_review:
            recommendations.append(f"High-severity borderline: {', '.join(high_review)}")
        if medium_review:
            recommendations.append(f"Medium-severity mismatches: {', '.join(medium_review)}")
        if low_review:
            recommendations.append(f"Low-severity mismatches: {', '.join(low_review)}")
    
    # RULE 3: APPROVED - All required fields meet defined thresholds
    # "Approved (all required fields meet defined thresholds)"
    else:
        overall_decision = "approved"
        recommendations.append("All fields meet defined thresholds")
    
    # Add weighted score to recommendations for reference
    recommendations.append(f"Weighted matching score: {overall_score:.2%}")
    
    return {
        "overall_decision": overall_decision,
        "overall_score": overall_score,  # For reporting/analytics only
        "field_comparisons": field_comparisons,
        "summary": {
            "total_fields": total_fields,
            "passed_fields": passed_fields,
            "review_fields": review_fields,
            "failed_fields": failed_fields
        },
        "recommendations": recommendations
    }

