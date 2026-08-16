import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.match import Match, MatchStage, MatchStatus
from app.models.playoff_round import PlayoffRound
from app.schemas.match import MatchCreate, MatchUpdate
from app.services.elo import recalculate_elo_ratings
from app.utils.serialization import stringify_urls

_URL_FIELDS = ("replay_url", "youtube_url")

# A match's round position, for ordering, without joining PlayoffRound into the
# statement itself (which would collide with the joinedload's own alias).
_ROUND_DISPLAY_ORDER = (
    select(PlayoffRound.display_order).where(PlayoffRound.id == Match.playoff_round_id).scalar_subquery()
)


def _with_participants(stmt: Select) -> Select:
    # games/pokemon are selectinload rather than joinedload: they're collections,
    # and joining two of them onto the same row would multiply it out.
    #
    # playoff_round is joined here rather than only in the season-detail path so
    # that every caller - match detail, player detail, the home page stream, the
    # admin list - can read the round without tripping lazy="raise".
    return stmt.options(
        joinedload(Match.home_player),
        joinedload(Match.away_player),
        joinedload(Match.season),
        joinedload(Match.playoff_round),
        selectinload(Match.games),
        selectinload(Match.pokemon),
    )


async def _sync_legacy_round_columns(db: AsyncSession, match: Match) -> None:
    """Mirror the round's name and position onto the match's legacy columns.

    Nothing in this release reads them. They are written so that rolling back
    to the previous release - which sorted the bracket from these columns -
    still renders the right order for matches created or moved in between.
    """
    if match.playoff_round_id is None:
        match.round_order = None
        if match.stage == MatchStage.PLAYOFFS:
            # Unassigned from its round: the copy of that round's name has to go
            # with it, or a rollback would file the match under a round it no
            # longer belongs to. A GROUP match keeps its round_label - that is
            # its own group/matchday label, not a copy of a round's.
            match.round_label = None
        return
    result = await db.execute(
        select(PlayoffRound.label, PlayoffRound.display_order).where(PlayoffRound.id == match.playoff_round_id)
    )
    row = result.first()
    if row is not None:
        match.round_label, match.round_order = row


async def get_matches_for_player(db: AsyncSession, player_id: uuid.UUID) -> list[Match]:
    stmt = _with_participants(select(Match)).where(
        or_(Match.home_player_id == player_id, Match.away_player_id == player_id)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_matches_for_season(db: AsyncSession, season_id: uuid.UUID, stage: MatchStage | None = None) -> list[Match]:
    stmt = _with_participants(select(Match)).where(Match.season_id == season_id)
    if stage is not None:
        stmt = stmt.where(Match.stage == stage)
    # Rounds order by their own display_order; matches inside a round by
    # bracket position, then by id so the result is always deterministic.
    # Dates only break ties between matches that have no bracket position -
    # they never decide which round comes first.
    stmt = stmt.order_by(
        Match.stage,
        _ROUND_DISPLAY_ORDER.nullsfirst(),
        Match.bracket_order.nullsfirst(),
        Match.scheduled_at.nullslast(),
        Match.id,
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_matches_for_seasons(
    db: AsyncSession, season_ids: Sequence[uuid.UUID], stage: MatchStage | None = None
) -> list[Match]:
    """Matches across several seasons in one query, for pages that render more
    than one season at a time (the Hall of Fame). Callers do their own ordering,
    so this only guarantees determinism, not presentation order."""
    if not season_ids:
        return []
    stmt = _with_participants(select(Match)).where(Match.season_id.in_(season_ids))
    if stage is not None:
        stmt = stmt.where(Match.stage == stage)
    result = await db.execute(stmt.order_by(Match.season_id, Match.id))
    return list(result.unique().scalars().all())


async def get_matches_scheduled_between(
    db: AsyncSession, season_id: uuid.UUID, start: datetime, end: datetime
) -> list[Match]:
    """A season's matches scheduled inside a half-open [start, end) window.

    Cancelled matches are excluded: a cancelled fixture is not something to put
    in front of visitors as this week's schedule. An administrator who wants one
    shown anyway can feature it explicitly.
    """
    stmt = (
        _with_participants(select(Match))
        .where(
            Match.season_id == season_id,
            Match.status != MatchStatus.CANCELLED,
            Match.scheduled_at.is_not(None),
            Match.scheduled_at >= start,
            Match.scheduled_at < end,
        )
        .order_by(Match.scheduled_at, Match.id)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_featured_matches(db: AsyncSession) -> list[Match]:
    """Matches an administrator has pinned to the homepage.

    Deliberately unfiltered by season, date or status - featuring a match is an
    explicit statement that it should appear whatever its dates say. Ordering is
    the administrator's own `homepage_feature_order`; matches without one sort
    after those that have one, then by schedule and id so the list never
    reshuffles between requests.
    """
    stmt = (
        _with_participants(select(Match))
        .where(Match.featured_on_homepage.is_(True))
        .order_by(
            Match.homepage_feature_order.nullslast(),
            Match.scheduled_at.nullslast(),
            Match.id,
        )
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_most_recent_stream_match(db: AsyncSession) -> Match | None:
    stmt = (
        _with_participants(select(Match))
        .where(Match.youtube_url.is_not(None))
        .order_by(Match.completed_at.desc().nullslast(), Match.scheduled_at.desc().nullslast())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.unique().scalars().first()


async def get_match_by_id(db: AsyncSession, match_id: uuid.UUID, refresh: bool = False) -> Match | None:
    stmt = _with_participants(select(Match)).where(Match.id == match_id)
    if refresh:
        # The instance is already in the identity map with its collections
        # loaded, and a plain re-query won't overwrite them - so games/pokemon
        # would come back stale after being replaced.
        stmt = stmt.execution_options(populate_existing=True)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def create_match(db: AsyncSession, match_in: MatchCreate) -> Match:
    data = stringify_urls(match_in.model_dump(), _URL_FIELDS)
    match = Match(**data)
    db.add(match)
    await _sync_legacy_round_columns(db, match)
    await db.flush()
    await recalculate_elo_ratings(db)
    await db.commit()
    loaded = await get_match_by_id(db, match.id)
    assert loaded is not None
    return loaded


async def update_match(db: AsyncSession, match: Match, match_in: MatchUpdate) -> Match:
    data = stringify_urls(match_in.model_dump(exclude_unset=True), _URL_FIELDS)
    for field, value in data.items():
        setattr(match, field, value)
    if "playoff_round_id" in data:
        await _sync_legacy_round_columns(db, match)
    await db.flush()
    await recalculate_elo_ratings(db)
    await db.commit()
    # refresh=True: `match` is already in the identity map with playoff_round
    # loaded, and with expire_on_commit=False a plain re-query will not replace
    # an already-populated relationship - so a match moved to another round
    # would come back still reporting the old one.
    loaded = await get_match_by_id(db, match.id, refresh=True)
    assert loaded is not None
    return loaded


async def delete_match(db: AsyncSession, match: Match) -> None:
    await db.delete(match)
    await db.flush()
    await recalculate_elo_ratings(db)
    await db.commit()
