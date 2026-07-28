import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.utils.serialization import stringify_urls

_URL_FIELDS = ("link_url",)


async def get_recent_announcements(db: AsyncSession, limit: int = 5) -> list[Announcement]:
    stmt = select(Announcement).order_by(Announcement.published_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_announcements(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Announcement]:
    stmt = select(Announcement).order_by(Announcement.published_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_announcement_by_id(db: AsyncSession, announcement_id: uuid.UUID) -> Announcement | None:
    result = await db.execute(select(Announcement).where(Announcement.id == announcement_id))
    return result.scalar_one_or_none()


async def create_announcement(db: AsyncSession, announcement_in: AnnouncementCreate) -> Announcement:
    data = stringify_urls(announcement_in.model_dump(), _URL_FIELDS)
    if data.get("published_at") is None:
        data["published_at"] = datetime.now(timezone.utc)
    announcement = Announcement(**data)
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)
    return announcement


async def update_announcement(
    db: AsyncSession, announcement: Announcement, announcement_in: AnnouncementUpdate
) -> Announcement:
    data = stringify_urls(announcement_in.model_dump(exclude_unset=True), _URL_FIELDS)
    for field, value in data.items():
        setattr(announcement, field, value)
    await db.commit()
    await db.refresh(announcement)
    return announcement


async def delete_announcement(db: AsyncSession, announcement: Announcement) -> None:
    await db.delete(announcement)
    await db.commit()
