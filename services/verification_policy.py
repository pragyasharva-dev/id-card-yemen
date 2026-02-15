"""
Verification Policy Service — maps main1.py logic to real services.

Reads from flat kyc_config table (one row with all component columns).
Writes to flat kyc_data table (one row per verification with all scores).

Each component follows main1.py's pattern:
    MIN, MAX, STATUS → from kyc_config columns
    THRESHOLD = (MIN / MAX) * 100  (percentage)
    SCORE     = raw_service_score * 100  (percentage, 0-100)
    PASS      = SCORE >= THRESHOLD
    POINTS    = (SCORE / 100) * MAX
"""
import logging
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.sql_models import KycConfig, KycData

logger = logging.getLogger(__name__)


# ─── Component definitions ─────────────────────────────────────────────
# Each tuple: (prefix in DB columns, score_key from API, parent_category)
COMPONENTS = {
    "ekyc":                  {"score_key": None,               "parent": None},
    "document_verify":       {"score_key": None,               "parent": "ekyc"},
    "document_authenticity": {"score_key": "doc_authenticity",  "parent": "document_verify"},
    "document_quality":      {"score_key": "doc_quality",       "parent": "document_verify"},
    "ocr_confidence":        {"score_key": "ocr_confidence",    "parent": "document_verify"},
    "front_back_id_match":   {"score_key": "front_back_match",  "parent": "document_verify"},
    "face_liveness":         {"score_key": None,               "parent": "ekyc"},
    "face_matching":         {"score_key": "face_match",        "parent": "face_liveness"},
    "passive_photo":         {"score_key": "liveness",          "parent": "face_liveness"},
    "data_match":            {"score_key": None,               "parent": "ekyc"},
    "id_number":             {"score_key": "id_number_match",   "parent": "data_match"},
    "name_matching":         {"score_key": "name_match",        "parent": "data_match"},
    "dob":                   {"score_key": "dob_match",         "parent": "data_match"},
    "issuance_date":         {"score_key": "issuance_date_match","parent": "data_match"},
    "expiry_date":           {"score_key": "expiry_date_match", "parent": "data_match"},
    "gender":                {"score_key": "gender_match",      "parent": "data_match"},
    "device_risk":           {"score_key": None,               "parent": "ekyc"},
    "compliance":            {"score_key": None,               "parent": "ekyc"},
}

# Hierarchy: category → list of child prefixes
CATEGORY_CHILDREN = {
    "ekyc":            ["document_verify", "face_liveness", "data_match", "device_risk", "compliance"],
    "document_verify": ["document_authenticity", "document_quality", "ocr_confidence", "front_back_id_match"],
    "face_liveness":   ["face_matching", "passive_photo"],
    "data_match":      ["id_number", "name_matching", "dob", "issuance_date", "expiry_date", "gender"],
}

# Default config values (matches spreadsheet)
DEFAULT_CONFIG = {
    "ekyc":                  {"min": 0,  "max": 100, "status": True},
    "document_verify":       {"min": 30, "max": 35,  "status": True},
    "document_authenticity": {"min": 10, "max": 10,  "status": True},
    "document_quality":      {"min": 10, "max": 10,  "status": True},
    "ocr_confidence":        {"min": 9,  "max": 10,  "status": True},
    "front_back_id_match":   {"min": 5,  "max": 5,   "status": True},
    "face_liveness":         {"min": 30, "max": 35,  "status": True},
    "face_matching":         {"min": 15, "max": 20,  "status": True},
    "passive_photo":         {"min": 10, "max": 15,  "status": True},
    "data_match":            {"min": 28, "max": 30,  "status": True},
    "id_number":             {"min": 15, "max": 20,  "status": True},
    "name_matching":         {"min": 7,  "max": 10,  "status": True},
    "dob":                   {"min": 0,  "max": 0,   "status": False},
    "issuance_date":         {"min": 0,  "max": 0,   "status": False},
    "expiry_date":           {"min": 0,  "max": 0,   "status": False},
    "gender":                {"min": 0,  "max": 0,   "status": False},
    "device_risk":           {"min": 0,  "max": 0,   "status": False},
    "compliance":            {"min": 0,  "max": 0,   "status": False},
}


def _to_float(val) -> float:
    """Convert Decimal/None to float safely."""
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


# ─── Result dataclass ───────────────────────────────────────────────────

@dataclass
class ComponentResult:
    prefix: str
    min_val: float
    max_val: float
    status: bool
    threshold: float   # (min/max)*100
    score: float       # raw * 100
    score_obtained: float  # (score/100) * max = points
    passed: bool


@dataclass
class PolicyResult:
    decision: str       # APPROVED, MANUAL_REVIEW, REJECTED
    total_score: float
    max_possible_score: float
    components: Dict[str, ComponentResult] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.decision == "APPROVED"

    def to_dict(self):
        return {
            "decision": self.decision,
            "total_score": round(self.total_score, 2),
            "max_possible_score": round(self.max_possible_score, 2),
            "components": {
                k: {
                    "min": v.min_val, "max": v.max_val, "status": v.status,
                    "threshold": round(v.threshold, 2),
                    "score": round(v.score, 2),
                    "score_obtained": round(v.score_obtained, 2),
                    "passed": v.passed,
                } for k, v in self.components.items()
            },
            "reasons": self.reasons,
        }


# ─── Service ────────────────────────────────────────────────────────────

class VerificationPolicyService:

    @staticmethod
    def calculate_threshold_percentage(min_val: float, max_val: float) -> float:
        """(MIN / MAX) * 100 — directly from main1.py."""
        if max_val == 0:
            return 0.0
        return (min_val / max_val) * 100.0

    @staticmethod
    async def get_active_config(db: AsyncSession) -> Dict[str, Dict[str, Any]]:
        """
        Read the latest row from kyc_config.
        Returns dict keyed by component prefix with {min, max, status}.
        Falls back to DEFAULT_CONFIG when table is empty.
        """
        try:
            result = await db.execute(
                select(KycConfig).order_by(KycConfig.id.desc()).limit(1)
            )
            row = result.scalars().first()
        except Exception as e:
            logger.warning(f"Could not read kyc_config: {e}. Using defaults.")
            row = None

        if not row:
            logger.info("kyc_config empty — using default policy.")
            return dict(DEFAULT_CONFIG)

        # Read flat columns into component dict
        config = {}
        for prefix in COMPONENTS:
            min_val = _to_float(getattr(row, f"{prefix}_min", 0))
            max_val = _to_float(getattr(row, f"{prefix}_max", 0))
            status = getattr(row, f"{prefix}_status", True)
            if status is None:
                status = True
            config[prefix] = {"min": min_val, "max": max_val, "status": bool(status)}

        return config

    @staticmethod
    async def evaluate_verification(
        db: AsyncSession,
        scores: Dict[str, float],
    ) -> PolicyResult:
        """
        Evaluate verification scores following main1.py logic.

        Args:
            db: Database session.
            scores: Raw system scores (0.0-1.0). Keys match COMPONENTS[x]["score_key"].

        Returns:
            PolicyResult with decision, scores, and per-component breakdowns.
        """
        config = await VerificationPolicyService.get_active_config(db)
        calc = VerificationPolicyService.calculate_threshold_percentage

        all_results: Dict[str, ComponentResult] = {}
        reasons: List[str] = []

        # ── Helper: evaluate a leaf component ────────────────────────
        def eval_leaf(prefix: str) -> ComponentResult:
            cfg = config.get(prefix, DEFAULT_CONFIG.get(prefix, {"min": 0, "max": 0, "status": False}))
            min_v = cfg["min"]
            max_v = cfg["max"]
            status = cfg["status"]

            if not status:
                return ComponentResult(
                    prefix=prefix, min_val=min_v, max_val=max_v, status=False,
                    threshold=0, score=0, score_obtained=0, passed=True
                )

            threshold = calc(min_v, max_v)

            # Get raw score from services
            score_key = COMPONENTS[prefix]["score_key"]
            raw = scores.get(score_key, 0.0) if score_key else 0.0
            score_pct = raw * 100.0

            # Points = (SCORE / 100) * MAX
            points = (score_pct / 100.0) * max_v

            passed = score_pct >= threshold

            if not passed:
                reasons.append(
                    f"{prefix}: score {score_pct:.1f}% < threshold {threshold:.1f}% "
                    f"(got {points:.1f}/{max_v} pts, need {min_v})"
                )

            return ComponentResult(
                prefix=prefix, min_val=min_v, max_val=max_v, status=True,
                threshold=threshold, score=score_pct, score_obtained=points, passed=passed
            )

        # ── Helper: evaluate a category (sums children) ──────────────
        def eval_category(prefix: str) -> ComponentResult:
            cfg = config.get(prefix, DEFAULT_CONFIG.get(prefix, {"min": 0, "max": 0, "status": False}))
            min_v = cfg["min"]
            max_v = cfg["max"]
            status = cfg["status"]

            if not status:
                return ComponentResult(
                    prefix=prefix, min_val=min_v, max_val=max_v, status=False,
                    threshold=0, score=0, score_obtained=0, passed=True
                )

            threshold = calc(min_v, max_v)

            # Sum child points
            children = CATEGORY_CHILDREN.get(prefix, [])
            total_pts = 0.0
            for child_prefix in children:
                if child_prefix in CATEGORY_CHILDREN:
                    # Child is itself a category
                    child_result = eval_category(child_prefix)
                else:
                    # Child is a leaf
                    child_result = eval_leaf(child_prefix)
                all_results[child_prefix] = child_result
                total_pts += child_result.score_obtained

            # Cap at category max
            total_pts = min(total_pts, max_v)

            # Category score as percentage of its max
            cat_score_pct = (total_pts / max_v * 100.0) if max_v > 0 else 0.0
            cat_passed = total_pts >= min_v

            if not cat_passed:
                reasons.append(
                    f"{prefix}: {total_pts:.1f}/{max_v} pts (min required: {min_v})"
                )

            return ComponentResult(
                prefix=prefix, min_val=min_v, max_val=max_v, status=True,
                threshold=threshold, score=cat_score_pct,
                score_obtained=total_pts, passed=cat_passed
            )

        # ── Root evaluation (main1.py: if EKYC_STATUS == 1) ──────────
        ekyc_cfg = config.get("ekyc", DEFAULT_CONFIG["ekyc"])
        if not ekyc_cfg["status"]:
            return PolicyResult(
                decision="APPROVED", total_score=0, max_possible_score=0,
                reasons=["EKYC disabled — dynamic checks bypassed"]
            )

        ekyc_result = eval_category("ekyc")
        all_results["ekyc"] = ekyc_result

        # ── Decision based on eKYC total score ─────────────────────
        total = ekyc_result.score_obtained

        if total > 90:
            decision = "APPROVED"
        elif total >= 50:
            decision = "MANUAL_REVIEW"
        else:
            decision = "REJECTED"

        return PolicyResult(
            decision=decision,
            total_score=ekyc_result.score_obtained,
            max_possible_score=ekyc_cfg["max"],
            components=all_results,
            reasons=reasons,
        )

    # ── log_result ───────────────────────────────────────────────────

    @staticmethod
    async def log_result(
        db: AsyncSession,
        user_id: int,
        scores: Dict[str, float],
        result: PolicyResult,
    ):
        """Persist the scoring result to the flat kyc_data table."""
        calc = VerificationPolicyService.calculate_threshold_percentage

        try:
            data = KycData(
                user_id=user_id,
                ekyc_data_id=str(uuid.uuid4()),
            )

            # For each component, copy min/max/status from config + computed threshold/score
            for prefix in COMPONENTS:
                comp = result.components.get(prefix)
                if comp:
                    setattr(data, f"{prefix}_min", comp.min_val)
                    setattr(data, f"{prefix}_max", comp.max_val)
                    setattr(data, f"{prefix}_status", comp.status)
                    setattr(data, f"{prefix}_threshold", comp.threshold)
                    setattr(data, f"{prefix}_score", comp.score)  # 0-100 percentage

            db.add(data)
            await db.commit()
            return data.ekyc_data_id
        except Exception as e:
            logger.error(f"Failed to log to KycData: {e}")
            return None
