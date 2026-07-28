from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import announcements as announcement_crud
from app.crud import matches as match_crud
from app.crud import season_entries as season_entry_crud
from app.models.match import Match
from app.schemas.announcement import AnnouncementRead
from app.schemas.home import HomeResponse, HomeSeasonInfo, HomeStream
from app.schemas.player import PlayerSummary
from app.services.seasons import get_current_season


def _stream_label(match: Match) -> str:
    return f"{match.season.name}: {match.home_player.username} vs {match.away_player.username}"


async def build_home_response(db: AsyncSession, today: date | None = None) -> HomeResponse:
    announcements = await announcement_crud.get_recent_announcements(db)
    stream_match = await match_crud.get_most_recent_stream_match(db)
    season, is_active = await get_current_season(db, today)

    current_season_info = None
    if season is not None:
        roster_entries = await season_entry_crud.get_roster(db, season.id)
        current_season_info = HomeSeasonInfo(
            id=season.id,
            name=season.name,
            is_active=is_active,
            sheet_url=season.sheet_url,
            roster=[PlayerSummary.model_validate(entry.player) for entry in roster_entries],
        )

    latest_stream = None
    if stream_match is not None and stream_match.youtube_url:
        latest_stream = HomeStream(url=stream_match.youtube_url, label=_stream_label(stream_match))

    return HomeResponse(
        announcements=[AnnouncementRead.model_validate(a) for a in announcements],
        latest_stream=latest_stream,
        current_season=current_season_info,
    )
