import uuid

from pydantic import BaseModel

from app.schemas.announcement import AnnouncementRead
from app.schemas.player import PlayerSummary


class HomeLink(BaseModel):
    """A resolved home-page link.

    `external` tells the client whether to render a router link or an outbound
    anchor - the standings link points inside the site by default, but becomes
    an outbound URL once an admin pins one.
    """

    url: str
    label: str
    external: bool = True


class HomeSeasonInfo(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    sheet_url: str | None
    roster: list[PlayerSummary]


class HomeResponse(BaseModel):
    announcements: list[AnnouncementRead]
    # Each is the admin's pinned override, or the derived default.
    latest_stream: HomeLink | None
    document: HomeLink | None
    table: HomeLink | None
    current_season: HomeSeasonInfo | None
