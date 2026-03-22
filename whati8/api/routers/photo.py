"""Photo recognition API endpoints."""

import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.deps import get_current_user, get_db
from whati8.models.user import User
from whati8.services.photo_recognition import recognize_food_photo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/photo", tags=["photo"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/recognize")
async def recognize_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a food photo for AI recognition."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_data = await file.read()
    if len(image_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    try:
        result = await recognize_food_photo(
            image_data=image_data,
            media_type=file.content_type,
        )
    except Exception as e:
        logger.error(f"Photo recognition failed: {e}")
        raise HTTPException(status_code=500, detail=f"Recognition failed: {str(e)}")

    return {
        "is_nutrition_label": result.is_nutrition_label,
        "items": [
            {
                "name": item.name,
                "serving_description": item.serving_description,
                "serving_size_g": item.serving_size_g,
                "confidence": item.confidence,
                "nutrients": item.nutrients,
            }
            for item in result.items
        ],
    }
