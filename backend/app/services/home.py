from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud import announcements as announcement_crud
from app.crud import matches as match_crud
from app.crud import season_entries as season_entry_crud
from app.crud import site_links as site_links_crud
from app.models.match import Match
from app.models.season import Season
from app.models.site_links import SiteLinks
from app.schemas.announcement import AnnouncementRead
from app.schemas.home import HomeFixtures, HomeLink, HomeResponse, HomeSeasonInfo
from app.schemas.player import PlayerSummary
from app.services.league_week import current_league_week
from app.services.matches import to_match_read
from app.services.seasons import get_current_season


def _stream_label(match: Match) -> str:
    return f"{match.season.name}: {match.home_player.username} vs {match.away_player.username}"


def _pinned(url: str | None, label: str | None, fallback_label: str) -> HomeLink | None:
    """The admin's override, if a URL was pinned. Label is optional in the admin
    form, so a blank one falls back rather than rendering an empty link."""
    if not url:
        return None
    return HomeLink(url=url, label=label or fallback_label, external=True)


def _resolve_stream(links: SiteLinks, stream_match: Match | None) -> HomeLink | None:
    pinned = _pinned(links.stream_url, links.stream_label, "Watch the latest stream")
    if pinned is not None:
        return pinned
    if stream_match is not None and stream_match.youtube_url:
        return HomeLink(url=stream_match.youtube_url, label=_stream_label(stream_match))
    return None


def _resolve_document(links: SiteLinks, season: Season | None) -> HomeLink | None:
    pinned = _pinned(links.document_url, links.document_label, "Open the league document")
    if pinned is not None:
        return pinned
    if season is not None and season.sheet_url:
        return HomeLink(url=season.sheet_url, label=f"{season.name} Google Sheet")
    return None


def _resolve_table(links: SiteLinks, season: Season | None) -> HomeLink | None:
    pinned = _pinned(links.table_url, links.table_label, "View the league table")
    if pinned is not None:
        return pinned
    if season is not None:
        # Internal by default: the season's own standings page, at its canonical
        # slug rather than its UUID.
        return HomeLink(
            url=f"/seasons/{season.slug}/standings", label=f"View {season.name} table", external=False
        )
    return None


async def build_fixtures(
    db: AsyncSession, season: Season | None, now: datetime | None = None
) -> HomeFixtures:
    """Featured matches, and the current league week's fixtures for `season`.

    A featured match is included whatever week it falls in and whatever its
    status, because featuring it is an explicit administrator decision. It is
    then removed from the weekly list so it cannot be shown twice.
    """
    week_start, week_end = current_league_week(now)
    featured = await match_crud.get_featured_matches(db)
    featured_ids = {match.id for match in featured}

    this_week: list[Match] = []
    if season is not None:
        this_week = [
            match
            for match in await match_crud.get_matches_scheduled_between(
                db, season.id, week_start, week_end
            )
            if match.id not in featured_ids
        ]

    return HomeFixtures(
        week_start=week_start,
        week_end=week_end,
        timezone=settings.league_timezone,
        featured=[to_match_read(match) for match in featured],
        this_week=[to_match_read(match) for match in this_week],
    )


async def build_home_response(
    db: AsyncSession, today: date | None = None, now: datetime | None = None
) -> HomeResponse:
    announcements = await announcement_crud.get_recent_announcements(db)
    stream_match = await match_crud.get_most_recent_stream_match(db)
    season, is_active = await get_current_season(db, today)
    links = await site_links_crud.get_site_links(db)

    current_season_info = None
    if season is not None:
        roster_entries = await season_entry_crud.get_roster(db, season.id)
        current_season_info = HomeSeasonInfo(
            id=season.id,
            slug=season.slug,
            name=season.name,
            is_active=is_active,
            sheet_url=season.sheet_url,
            roster=[PlayerSummary.model_validate(entry.player) for entry in roster_entries],
        )

    return HomeResponse(
        announcements=[AnnouncementRead.model_validate(a) for a in announcements],
        latest_stream=_resolve_stream(links, stream_match),
        document=_resolve_document(links, season),
        table=_resolve_table(links, season),
        current_season=current_season_info,
        fixtures=await build_fixtures(db, season, now),
    )
