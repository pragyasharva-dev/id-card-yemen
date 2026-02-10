"""
Data Service for interacting with the PostgreSQL database.
Handles CRUD operations for Documents and Verifications using SQLAlchemy.
"""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound

from models.sql_models import Document, Verification, AuditLog

async def save_document(
    session: AsyncSession,
    document_number: str,
    document_type: str,
    ocr_data: Dict[str, Any],
    front_image_data: Optional[bytes] = None,
    back_image_data: Optional[bytes] = None,
    transaction_id: Optional[str] = None
) -> Document:
    """
    Save or update an ID Document (ID Card or Passport).
    If the document exists (by type and number), it updates it.
    """
    # Check if document exists
    query = select(Document).where(
        Document.document_type == document_type,
        Document.document_number == document_number
    )
    result = await session.execute(query)
    document = result.scalar_one_or_none()
    
    # Extract common searchable fields from ocr_data for the main columns
    full_name_arabic = ocr_data.get("name_arabic") or \
                       " ".join(filter(None, [ocr_data.get("first_name_arabic"), ocr_data.get("middle_name_arabic"), ocr_data.get("last_name_arabic")]))
    
    full_name_english = ocr_data.get("name_english") or \
                        " ".join(filter(None, [ocr_data.get("first_name_english"), ocr_data.get("middle_name_english"), ocr_data.get("last_name_english")]))

    if document:
        # Update existing
        document.ocr_data = ocr_data
        document.full_name_arabic = full_name_arabic
        document.full_name_english = full_name_english
        document.updated_at = datetime.now()
        
        # Only update images if provided (to avoid overwriting with None if not re-uploaded)
        if front_image_data:
            document.front_image_data = front_image_data
        if back_image_data:
            document.back_image_data = back_image_data
        if transaction_id:
            document.transaction_id = transaction_id
            
    else:
        # Create new
        document = Document(
            document_number=document_number,
            document_type=document_type,
            ocr_data=ocr_data,
            full_name_arabic=full_name_arabic,
            full_name_english=full_name_english,
            front_image_data=front_image_data,
            back_image_data=back_image_data,
            transaction_id=transaction_id
        )
        session.add(document)
    
    await session.commit()
    await session.refresh(document)
    return document

async def save_verification(
    session: AsyncSession,
    document_id: int,
    status: str,
    similarity_score: Optional[float],
    selfie_image_data: Optional[bytes],
    liveness_data: Dict[str, Any],
    image_quality_metrics: Dict[str, Any] = {},
    authenticity_checks: Dict[str, Any] = {},
    failure_reason: Dict[str, Any] = {},
    transaction_id: Optional[str] = None
) -> Verification:
    """
    Save a new verification result linked to a document.
    """
    verification = Verification(
        document_id=document_id,
        status=status,
        similarity_score=similarity_score,
        selfie_image_data=selfie_image_data,
        liveness_data=liveness_data,
        image_quality_metrics=image_quality_metrics,
        authenticity_checks=authenticity_checks,
        failure_reason=failure_reason,
        transaction_id=transaction_id,
        verified_at=datetime.now() if status == "verified" else None
    )
    session.add(verification)
    await session.commit()
    await session.refresh(verification)
    return verification

async def get_document_by_number(
    session: AsyncSession, 
    document_number: str, 
    document_type: str = "yemen_id"
) -> Optional[Document]:
    """Retrieve a document by its unique number."""
    query = select(Document).where(
        Document.document_type == document_type,
        Document.document_number == document_number
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def log_audit_event(
    session: AsyncSession,
    event_type: str,
    metadata: Dict[str, Any]
):
    """Log a system event."""
    log = AuditLog(
        event_type=event_type,
        metadata_info=metadata
    )
    session.add(log)
    await session.commit()
