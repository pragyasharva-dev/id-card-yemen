"""
SQLAlchemy Models for the e-KYC System (PostgreSQL).
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Index, LargeBinary
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


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_info: Mapped[dict] = mapped_column("metadata", JSONB, server_default='{}')
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
