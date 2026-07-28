from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.home import HomeResponse
from app.services.home import build_home_response

router = APIRouter(tags=["home"])


@router.get("/home", response_model=HomeResponse)
async def get_home(db: AsyncSession = Depends(get_db)) -> HomeResponse:
    return await build_home_response(db)
