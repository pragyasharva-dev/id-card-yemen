"""e-KYC verification endpoints."""
import cv2
from fastapi import APIRouter, UploadFile, File

from models.schemas import VerifyRequest, VerifyResponse, LivenessResult
from services.ocr_service import extract_id_from_image
from services.face_recognition import verify_identity
from services.database import get_id_card_db
from utils.image_manager import load_image, save_image
from utils.config import PROCESSED_DIR

router = APIRouter(tags=["Verification"])


@router.post("/verify", response_model=VerifyResponse)
async def verify_identity_endpoint(
    id_card_front: UploadFile = File(..., description="ID card front side image"),
    selfie: UploadFile = File(..., description="Selfie image file"),
    id_card_back: UploadFile = File(None, description="ID card back side image (optional)")
):
    """
    e-KYC verification endpoint with optional front and back ID card support.
    
    1. Receives ID card front (required) and optionally back side
    2. Extracts ID number and structured data from front card
    3. Extracts face from front card
    4. Compares with selfie face
    5. Returns extracted data and similarity score
    
    The similarity score is a value between 0.0 and 1.0 - 
    higher values indicate higher likelihood of same person.
    """
    try:
        # Load front ID card and selfie
        id_card_front_bytes = await id_card_front.read()
        selfie_bytes = await selfie.read()
        
        id_card_front_image = load_image(id_card_front_bytes)
        selfie_image = load_image(selfie_bytes)
        
        # Initialize filenames
        id_front_filename = None
        id_back_filename = None
        
        # Optionally load back ID card
        id_card_back_image = None
        if id_card_back:
            id_card_back_bytes = await id_card_back.read()
            id_card_back_image = load_image(id_card_back_bytes)
        
        # Extract ID from front card
        front_ocr_result = extract_id_from_image(id_card_front_image)
        extracted_id = front_ocr_result.get("extracted_id")
        id_type = front_ocr_result.get("id_type")
        
        # Note: Structured data parsing removed - data is now entered manually into database
        parsed_data = {}
        
        # Save images with proper naming if ID was extracted
        if extracted_id:
            import time
            timestamp = int(time.time())
            
            # Save front image to processed directory
            id_front_filename = f"{extracted_id}_front_{timestamp}.jpg"
            save_image(id_card_front_image, id_front_filename, PROCESSED_DIR)
            
            # Save back image if provided
            if id_card_back_image is not None:
                id_back_filename = f"{extracted_id}_back_{timestamp}.jpg"
                save_image(id_card_back_image, id_back_filename, PROCESSED_DIR)
        
        # Face verification using front card
        face_result = verify_identity(id_card_front_image, selfie_image)
        
        # Convert liveness dict to LivenessResult model if present
        liveness_response = None
        if face_result.get("liveness"):
            liveness_data = face_result["liveness"]
            liveness_response = LivenessResult(
                is_live=liveness_data.get("is_live", False),
                confidence=liveness_data.get("confidence", 0.0),
                spoof_probability=liveness_data.get("spoof_probability", 1.0),
                checks=liveness_data.get("checks", {}),
                error=liveness_data.get("error")
            )
        
        if face_result.get("error"):
            return VerifyResponse(
                success=False,
                extracted_id=extracted_id,
                id_type=id_type,
                similarity_score=None,
                id_front=id_front_filename,
                id_back=id_back_filename,
                name_arabic=parsed_data.get("name_arabic"),
                name_english=parsed_data.get("name_english"),
                date_of_birth=parsed_data.get("date_of_birth"),
                gender=parsed_data.get("gender"),
                place_of_birth=parsed_data.get("place_of_birth"),
                issuance_date=parsed_data.get("issuance_date"),
                expiry_date=parsed_data.get("expiry_date"),
                liveness=liveness_response,
                error=face_result["error"]
            )
        
        # AUTO-SAVE: Save extracted data to database after successful verification
        if extracted_id:
            try:
                db = get_id_card_db()
                
                # Convert images to JPEG bytes for blob storage
                front_blob = None
                back_blob = None
                selfie_blob = None
                
                if id_card_front_image is not None:
                    _, front_encoded = cv2.imencode('.jpg', id_card_front_image)
                    front_blob = front_encoded.tobytes()
                
                if id_card_back_image is not None:
                    _, back_encoded = cv2.imencode('.jpg', id_card_back_image)
                    back_blob = back_encoded.tobytes()
                
                if selfie_image is not None:
                    _, selfie_encoded = cv2.imencode('.jpg', selfie_image)
                    selfie_blob = selfie_encoded.tobytes()
                
                db_data = {
                    "national_id": extracted_id,
                    "name_arabic": parsed_data.get("name_arabic"),
                    "name_english": parsed_data.get("name_english"),
                    "date_of_birth": parsed_data.get("date_of_birth"),
                    "place_of_birth": parsed_data.get("place_of_birth"),
                    "gender": parsed_data.get("gender"),
                    "issuance_date": parsed_data.get("issuance_date"),
                    "expiry_date": parsed_data.get("expiry_date"),
                    "front_image_blob": front_blob,
                    "back_image_blob": back_blob,
                    "selfie_image_blob": selfie_blob
                }
                
                # Check if record exists, update or insert
                existing = db.get_by_national_id(extracted_id)
                if existing:
                    db.update(extracted_id, db_data)
                else:
                    db.insert(db_data)
            except Exception as db_error:
                # Log error but don't fail the verification
                print(f"Warning: Failed to save to database: {db_error}")
        
        return VerifyResponse(
            success=True,
            extracted_id=extracted_id,
            id_type=id_type,
            similarity_score=face_result["similarity_score"],
            id_front=id_front_filename,
            id_back=id_back_filename,
            name_arabic=parsed_data.get("name_arabic"),
            name_english=parsed_data.get("name_english"),
            date_of_birth=parsed_data.get("date_of_birth"),
            gender=parsed_data.get("gender"),
            place_of_birth=parsed_data.get("place_of_birth"),
            issuance_date=parsed_data.get("issuance_date"),
            expiry_date=parsed_data.get("expiry_date"),
            liveness=liveness_response,
            error=None
        )
        
    except Exception as e:
        return VerifyResponse(
            success=False,
            extracted_id=None,
            id_type=None,
            similarity_score=None,
            id_front=None,
            id_back=None,
            name_arabic=None,
            name_english=None,
            date_of_birth=None,
            gender=None,
            place_of_birth=None,
            issuance_date=None,
            expiry_date=None,
            liveness=None,
            error=str(e)
        )


@router.post("/verify-json", response_model=VerifyResponse)
async def verify_identity_json(request: VerifyRequest):
    """
    e-KYC verification using JSON body with ID number and selfie path/base64.
    
    Searches ID cards database for matching ID, then compares faces.
    """
    try:
        from services.id_database import search_id_card_by_number
        
        # Load selfie image
        if request.selfie_path:
            selfie_image = load_image(request.selfie_path)
        elif request.selfie_base64:
            selfie_image = load_image(request.selfie_base64)
        else:
            raise ValueError("Either selfie_path or selfie_base64 is required")
        
        # Search for ID card in database
        search_result = search_id_card_by_number(request.id_number)
        
        if search_result is None:
            return VerifyResponse(
                success=False,
                extracted_id=request.id_number,
                id_type=None,
                similarity_score=None,
                id_front=None,
                id_back=None,
                name_arabic=None,
                name_english=None,
                date_of_birth=None,
                gender=None,
                place_of_birth=None,
                issuance_date=None,
                expiry_date=None,
                error=f"ID card with number '{request.id_number}' not found in database"
            )
        
        card_path, id_card_image, ocr_result = search_result
        extracted_id = ocr_result.get("extracted_id")
        id_type = ocr_result.get("id_type")
        
        # Face verification
        face_result = verify_identity(id_card_image, selfie_image)
        
        if face_result.get("error"):
            return VerifyResponse(
                success=False,
                extracted_id=extracted_id,
                id_type=id_type,
                similarity_score=None,
                id_front=None,
                id_back=None,
                name_arabic=None,
                name_english=None,
                date_of_birth=None,
                gender=None,
                place_of_birth=None,
                issuance_date=None,
                expiry_date=None,
                error=face_result["error"]
            )
        
        return VerifyResponse(
            success=True,
            extracted_id=extracted_id,
            id_type=id_type,
            similarity_score=face_result["similarity_score"],
            id_front=None,
            id_back=None,
            name_arabic=None,
            name_english=None,
            date_of_birth=None,
            gender=None,
            place_of_birth=None,
            issuance_date=None,
            expiry_date=None,
            error=None
        )
        
    except Exception as e:
        return VerifyResponse(
            success=False,
            extracted_id=None,
            id_type=None,
            similarity_score=None,
            id_front=None,
            id_back=None,
            name_arabic=None,
            name_english=None,
            date_of_birth=None,
            gender=None,
            place_of_birth=None,
            issuance_date=None,
            expiry_date=None,
            error=str(e)
        )
