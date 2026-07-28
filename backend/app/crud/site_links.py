from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site_links import SITE_LINKS_ID, SiteLinks
from app.schemas.site_links import SiteLinksUpdate
from app.utils.serialization import stringify_urls

_URL_FIELDS = ("stream_url", "document_url", "table_url")


async def get_site_links(db: AsyncSession) -> SiteLinks:
    """The settings row, created empty on first read so callers never have to
    handle its absence."""
    existing = (await db.execute(select(SiteLinks).where(SiteLinks.id == SITE_LINKS_ID))).scalar_one_or_none()
    if existing is not None:
        return existing
    links = SiteLinks(id=SITE_LINKS_ID)
    db.add(links)
    await db.commit()
    await db.refresh(links)
    return links


async def update_site_links(db: AsyncSession, links_in: SiteLinksUpdate) -> SiteLinks:
    links = await get_site_links(db)
    # Not exclude_unset: this is a full replacement, so an omitted field is an
    # explicit "go back to deriving it".
    for field, value in stringify_urls(links_in.model_dump(), _URL_FIELDS).items():
        setattr(links, field, value)
    await db.commit()
    await db.refresh(links)
    return links
