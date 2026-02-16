"""
SQLAlchemy Models for the e-KYC System (PostgreSQL).
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Index, LargeBinary, BigInteger, Numeric
from sqlalchemy.dialects.postgresql import JSONB, BYTEA
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from services.db import Base

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_number: Mapped[str] = mapped_column(String(50), nullable=False)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'yemen_id', 'passport'
    
    # V1 API Transaction ID (links OCR Check and Face Match)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    
    # Searchable Name Fields
    full_name_arabic: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    full_name_english: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    
    # Flexible Data Storage (extracted OCR fields)
    ocr_data: Mapped[dict] = mapped_column(JSONB, server_default='{}')
    
    # Images stored as BLOBs (BYTEA in Postgres)
    front_image_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    back_image_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    verifications: Mapped[List["Verification"]] = relationship(back_populates="document")

    __table_args__ = (
        Index("idx_documents_type_number", "document_type", "document_number"),
        Index("idx_documents_ocr_data", "ocr_data", postgresql_using="gin"),
    )


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    
    # V1 API Transaction ID
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    
    # Verification details
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, verified, failed
    similarity_score: Mapped[Optional[float]] = mapped_column(Float)
    failure_reason: Mapped[dict] = mapped_column(JSONB, server_default='{}')
    
    # Selfie Image (BLOB)
    selfie_image_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    
    # Liveness Data (JSONB)
    liveness_data: Mapped[dict] = mapped_column(JSONB, server_default='{}')

    # Detailed Verification Signals (JSONB)
    image_quality_metrics: Mapped[dict] = mapped_column(JSONB, server_default='{}')
    authenticity_checks: Mapped[dict] = mapped_column(JSONB, server_default='{}')
    
    # Timestamps
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="verifications")


class SystemConfig(Base):
    """Dynamic configuration overrides set via Admin API."""
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_info: Mapped[dict] = mapped_column("metadata", JSONB, server_default='{}')
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KycConfig(Base):
    """
    Flat KYC scoring configuration.
    One row = one complete config set. Each component has _min, _max, _status columns.
    """
    __tablename__ = "kyc_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ekyc_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # EKYC (root)
    ekyc_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ekyc_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ekyc_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    # Document Verification
    document_verify_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_verify_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_verify_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    document_authenticity_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_authenticity_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_authenticity_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    document_quality_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_quality_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_quality_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    ocr_confidence_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ocr_confidence_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ocr_confidence_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    front_back_id_match_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    front_back_id_match_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    front_back_id_match_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    # Face & Liveness
    face_liveness_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_liveness_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_liveness_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    face_matching_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_matching_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_matching_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    passive_photo_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    passive_photo_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    passive_photo_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    # Data Match
    data_match_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    data_match_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    data_match_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    id_number_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    id_number_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    id_number_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    name_matching_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    name_matching_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    name_matching_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    dob_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    dob_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    dob_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    issuance_date_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    issuance_date_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    issuance_date_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    expiry_date_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    expiry_date_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    expiry_date_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    gender_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    gender_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    gender_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    # Device Risk & Compliance
    device_risk_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    device_risk_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    device_risk_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    compliance_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    compliance_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    compliance_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())


class KycData(Base):
    """
    Log of individual verification attempts.
    One row per verification. Each component has _min, _max, _status, _threshold, _score columns.
    """
    __tablename__ = "kyc_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ekyc_data_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # EKYC (root)
    ekyc_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ekyc_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ekyc_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    ekyc_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ekyc_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Document Verification
    document_verify_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_verify_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_verify_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    document_verify_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_verify_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    document_authenticity_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_authenticity_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_authenticity_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    document_authenticity_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_authenticity_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    document_quality_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_quality_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_quality_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    document_quality_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    document_quality_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    ocr_confidence_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ocr_confidence_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ocr_confidence_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    ocr_confidence_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    ocr_confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    front_back_id_match_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    front_back_id_match_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    front_back_id_match_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    front_back_id_match_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    front_back_id_match_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Face & Liveness
    face_liveness_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_liveness_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_liveness_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    face_liveness_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_liveness_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    face_matching_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_matching_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_matching_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    face_matching_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    face_matching_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    passive_photo_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    passive_photo_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    passive_photo_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    passive_photo_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    passive_photo_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Data Match
    data_match_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    data_match_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    data_match_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    data_match_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    data_match_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    id_number_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    id_number_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    id_number_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    id_number_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    id_number_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    name_matching_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    name_matching_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    name_matching_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    name_matching_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    name_matching_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    dob_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    dob_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    dob_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    dob_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    dob_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    issuance_date_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    issuance_date_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    issuance_date_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    issuance_date_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    issuance_date_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    expiry_date_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    expiry_date_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    expiry_date_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    expiry_date_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    expiry_date_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    gender_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    gender_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    gender_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    gender_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    gender_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Device Risk & Compliance
    device_risk_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    device_risk_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    device_risk_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    device_risk_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    device_risk_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    compliance_min: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    compliance_max: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    compliance_status: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    compliance_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    compliance_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
