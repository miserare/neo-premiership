import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.crud import announcements as crud
from app.database import get_db
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementRead,
    AnnouncementUpdate,
)

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("", response_model=list[AnnouncementRead])
async def list_announcements(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
) -> list[AnnouncementRead]:
    return await crud.get_announcements(db, skip=skip, limit=limit)


@router.post(
    "", response_model=AnnouncementRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)]
)
async def create_announcement(
    announcement_in: AnnouncementCreate, db: AsyncSession = Depends(get_db)
) -> AnnouncementRead:
    return await crud.create_announcement(db, announcement_in)


@router.patch("/{announcement_id}", response_model=AnnouncementRead, dependencies=[Depends(require_admin)])
async def update_announcement(
    announcement_id: uuid.UUID, announcement_in: AnnouncementUpdate, db: AsyncSession = Depends(get_db)
) -> AnnouncementRead:
    announcement = await crud.get_announcement_by_id(db, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    return await crud.update_announcement(db, announcement, announcement_in)


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_announcement(announcement_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    announcement = await crud.get_announcement_by_id(db, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    await crud.delete_announcement(db, announcement)
