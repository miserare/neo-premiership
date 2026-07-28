from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.crud import site_links as crud
from app.database import get_db
from app.schemas.site_links import SiteLinksRead, SiteLinksUpdate

router = APIRouter(prefix="/site-links", tags=["site"])


@router.get("", response_model=SiteLinksRead)
async def get_site_links(db: AsyncSession = Depends(get_db)) -> SiteLinksRead:
    """The raw overrides, for the admin form to populate itself. The public home
    page reads the *resolved* links from /api/home instead."""
    return await crud.get_site_links(db)


@router.put("", response_model=SiteLinksRead, dependencies=[Depends(require_admin)])
async def set_site_links(links_in: SiteLinksUpdate, db: AsyncSession = Depends(get_db)) -> SiteLinksRead:
    return await crud.update_site_links(db, links_in)
