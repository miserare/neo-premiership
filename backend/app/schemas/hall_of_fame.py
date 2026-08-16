"""Hall of Fame responses.

Kept apart from season.py because these are a different view of the same rows,
not another shape of a season: they are keyed on the championship, and the
entry's centre of gravity is the champion and their playoff run.
"""

import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.match import MatchRead
from app.schemas.player import PlayerSummary


class HallOfFameEntry(BaseModel):
    """One completed championship.

    `championship_run` is the champion's own playoff matches that season, in
    tournament order - by the round's explicit display_order, then by bracket
    position. It is a plain list of MatchRead so replays, per-game winners, the
    YouTube link and both teams are the same shape the rest of the site already
    renders, rather than a second copy of match data.
    """

    season_id: uuid.UUID
    season_slug: str
    season_name: str
    start_date: date
    end_date: date | None
    champion: PlayerSummary
    # How many seasons this player has won in total, so the page can say
    # "3× Champion" without the client counting entries itself.
    championship_count: int
    description: str | None
    # True when `description` fell back to the season overview because no Hall
    # of Fame text has been written, so the page can label it honestly.
    description_is_fallback: bool
    championship_run: list[MatchRead]


class HallOfFameResponse(BaseModel):
    entries: list[HallOfFameEntry]
