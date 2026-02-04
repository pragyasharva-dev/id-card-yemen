"""Face comparison endpoints."""
from fastapi import APIRouter, UploadFile, File
from fastapi.concurrency import run_in_threadpool

from models.schemas import CompareFacesResponse
from services.face_recognition import compare_faces
from utils.image_manager import load_image

router = APIRouter(tags=["Face"])


@router.post("/compare-faces", response_model=CompareFacesResponse)
async def compare_faces_endpoint(
    image1: UploadFile = File(..., description="First image (e.g., ID card)"),
    image2: UploadFile = File(..., description="Second image (e.g., selfie)")
):
    """
    Compare faces in two images.
    
    Returns a similarity score between 0.0 and 1.0.
    """
    try:
        image1_bytes = await image1.read()
        image2_bytes = await image2.read()
        
        img1 = load_image(image1_bytes)
        img2 = load_image(image2_bytes)
        
        result = await run_in_threadpool(compare_faces, img1, img2)
        
        if result.get("error"):
            return CompareFacesResponse(
                success=False,
                similarity_score=None,
                error=result["error"]
            )
        
        return CompareFacesResponse(
            success=True,
            similarity_score=result["similarity_score"],
            error=None
        )
        
    except Exception as e:
        return CompareFacesResponse(
            success=False,
            similarity_score=None,
            error=str(e)
        )
