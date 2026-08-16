import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.announcement import AnnouncementRead
from app.schemas.match import MatchRead
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
    slug: str
    name: str
    is_active: bool
    sheet_url: str | None
    roster: list[PlayerSummary]


class HomeFixtures(BaseModel):
    """This week's matches, plus whatever an administrator has pinned.

    Two lists rather than one merged list: they are different claims. `this_week`
    is a fact about the calendar, `featured` is an editorial decision. A featured
    match that also falls in the current week appears only in `featured`, so
    nothing is rendered twice.

    `week_start`/`week_end` are the half-open UTC bounds actually used, and
    `timezone` is the league zone they were derived in - so the page can say
    which week it is showing rather than leaving the visitor to guess.
    """

    week_start: datetime
    week_end: datetime
    timezone: str
    featured: list[MatchRead]
    this_week: list[MatchRead]


class HomeResponse(BaseModel):
    announcements: list[AnnouncementRead]
    # Each is the admin's pinned override, or the derived default.
    latest_stream: HomeLink | None
    document: HomeLink | None
    table: HomeLink | None
    current_season: HomeSeasonInfo | None
    fixtures: HomeFixtures
