"""Database CRUD endpoints for ID cards and passports."""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from models.schemas import (
    SaveIDCardRequest, SavePassportRequest,
    IDCardRecord, PassportRecord,
    IDCardListResponse, PassportListResponse,
    SaveRecordResponse,
)
from services.database import get_id_card_db, get_passport_db

router = APIRouter(tags=["Database"])


# =====================================================
# ID CARD ENDPOINTS
# =====================================================

@router.post("/save-id-card", response_model=SaveRecordResponse)
async def save_id_card(request: SaveIDCardRequest):
    """
    Save extracted ID card data to the database.
    
    Names can be provided as:
    - Full names (name_arabic, name_english) which will be auto-split
    - Individual components (first_name_*, middle_name_*, last_name_*)
    """
    try:
        db = get_id_card_db()
        
        # Check if record already exists
        existing = db.get_by_national_id(request.national_id)
        if existing:
            # Update existing record
            data = request.model_dump(exclude_none=True)
            db.update(request.national_id, data)
            return SaveRecordResponse(
                success=True,
                record_id=existing["id"],
                message=f"Updated existing record for ID: {request.national_id}"
            )
        
        # Insert new record
        data = request.model_dump(exclude_none=True)
        record_id = db.insert(data)
        
        return SaveRecordResponse(
            success=True,
            record_id=record_id,
            message=f"Saved new ID card record: {request.national_id}"
        )
        
    except Exception as e:
        return SaveRecordResponse(
            success=False,
            error=str(e)
        )


@router.get("/id-cards", response_model=IDCardListResponse)
async def list_id_cards():
    """List all ID card records from the database."""
    try:
        db = get_id_card_db()
        records = db.get_all()
        
        return IDCardListResponse(
            success=True,
            count=len(records),
            records=[IDCardRecord(**r) for r in records]
        )
        
    except Exception as e:
        return IDCardListResponse(
            success=False,
            error=str(e)
        )


@router.get("/id-cards/{national_id}")
async def get_id_card(national_id: str):
    """Get a specific ID card record by national ID number."""
    try:
        db = get_id_card_db()
        record = db.get_by_national_id(national_id)
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"ID card with national ID '{national_id}' not found"
            )
        
        return IDCardRecord(**record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/id-cards/{record_id}")
async def delete_id_card(record_id: int):
    """Delete an ID card record by its database ID."""
    try:
        db = get_id_card_db()
        deleted = db.delete(record_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"ID card record with ID {record_id} not found"
            )
        
        return {"success": True, "message": f"Deleted record {record_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/id-cards")
async def export_id_cards(
    format: str = Query("csv", description="Export format: csv or excel")
):
    """
    Export all ID card records to CSV or Excel file.
    
    Returns the file for download.
    """
    try:
        db = get_id_card_db()
        
        if format.lower() == "excel":
            export_path = db.export_excel()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            export_path = db.export_csv()
            media_type = "text/csv"
        
        return FileResponse(
            path=str(export_path),
            filename=export_path.name,
            media_type=media_type
        )
        
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Excel export requires openpyxl. Install with: pip install openpyxl"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# PASSPORT ENDPOINTS
# =====================================================

@router.post("/save-passport", response_model=SaveRecordResponse)
async def save_passport(request: SavePassportRequest):
    """
    Save extracted passport data to the database.
    
    Names can be provided as:
    - Full names (name_arabic, name_english) which will be auto-split
    - Individual components (first_name_*, middle_name_*, last_name_*)
    """
    try:
        db = get_passport_db()
        
        # Check if record already exists
        existing = db.get_by_passport_number(request.passport_number)
        if existing:
            # Update existing record
            data = request.model_dump(exclude_none=True)
            db.update(request.passport_number, data)
            return SaveRecordResponse(
                success=True,
                record_id=existing["id"],
                message=f"Updated existing record for passport: {request.passport_number}"
            )
        
        # Insert new record
        data = request.model_dump(exclude_none=True)
        record_id = db.insert(data)
        
        return SaveRecordResponse(
            success=True,
            record_id=record_id,
            message=f"Saved new passport record: {request.passport_number}"
        )
        
    except Exception as e:
        return SaveRecordResponse(
            success=False,
            error=str(e)
        )


@router.get("/passports", response_model=PassportListResponse)
async def list_passports():
    """List all passport records from the database."""
    try:
        db = get_passport_db()
        records = db.get_all()
        
        return PassportListResponse(
            success=True,
            count=len(records),
            records=[PassportRecord(**r) for r in records]
        )
        
    except Exception as e:
        return PassportListResponse(
            success=False,
            error=str(e)
        )


@router.get("/passports/{passport_number}")
async def get_passport(passport_number: str):
    """Get a specific passport record by passport number."""
    try:
        db = get_passport_db()
        record = db.get_by_passport_number(passport_number)
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Passport with number '{passport_number}' not found"
            )
        
        return PassportRecord(**record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/passports/{record_id}")
async def delete_passport(record_id: int):
    """Delete a passport record by its database ID."""
    try:
        db = get_passport_db()
        deleted = db.delete(record_id)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Passport record with ID {record_id} not found"
            )
        
        return {"success": True, "message": f"Deleted record {record_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/passports")
async def export_passports(
    format: str = Query("csv", description="Export format: csv or excel")
):
    """
    Export all passport records to CSV or Excel file.
    
    Returns the file for download.
    """
    try:
        db = get_passport_db()
        
        if format.lower() == "excel":
            export_path = db.export_excel()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            export_path = db.export_csv()
            media_type = "text/csv"
        
        return FileResponse(
            path=str(export_path),
            filename=export_path.name,
            media_type=media_type
        )
        
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Excel export requires openpyxl. Install with: pip install openpyxl"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
