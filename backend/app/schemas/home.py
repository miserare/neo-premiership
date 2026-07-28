import uuid

from pydantic import BaseModel

from app.schemas.announcement import AnnouncementRead
from app.schemas.player import PlayerSummary


class HomeStream(BaseModel):
    url: str
    label: str


class HomeSeasonInfo(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    sheet_url: str | None
    roster: list[PlayerSummary]


class HomeResponse(BaseModel):
    announcements: list[AnnouncementRead]
    latest_stream: HomeStream | None
    current_season: HomeSeasonInfo | None
