from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.hall_of_fame import HallOfFameResponse
from app.services.hall_of_fame import build_hall_of_fame

router = APIRouter(tags=["hall-of-fame"])


@router.get("/hall-of-fame", response_model=HallOfFameResponse)
async def get_hall_of_fame(db: AsyncSession = Depends(get_db)) -> HallOfFameResponse:
    """Every season with a recorded champion, newest first.

    Public: it is built from the same PlayerSummary the rest of the site uses,
    which has no private fields on it.
    """
    return await build_hall_of_fame(db)
