import uuid

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.match import Match, MatchStage
from app.schemas.match import MatchCreate, MatchUpdate
from app.utils.serialization import stringify_urls

_URL_FIELDS = ("replay_url", "youtube_url")


def _with_participants(stmt: Select) -> Select:
    # games/pokemon are selectinload rather than joinedload: they're collections,
    # and joining two of them onto the same row would multiply it out.
    return stmt.options(
        joinedload(Match.home_player),
        joinedload(Match.away_player),
        joinedload(Match.season),
        selectinload(Match.games),
        selectinload(Match.pokemon),
    )


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
    stmt = stmt.order_by(
        Match.stage,
        Match.round_order.nullsfirst(),
        Match.bracket_order.nullsfirst(),
        Match.scheduled_at.nullslast(),
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
    await db.commit()
    loaded = await get_match_by_id(db, match.id)
    assert loaded is not None
    return loaded


async def update_match(db: AsyncSession, match: Match, match_in: MatchUpdate) -> Match:
    data = stringify_urls(match_in.model_dump(exclude_unset=True), _URL_FIELDS)
    for field, value in data.items():
        setattr(match, field, value)
    await db.commit()
    loaded = await get_match_by_id(db, match.id)
    assert loaded is not None
    return loaded


async def delete_match(db: AsyncSession, match: Match) -> None:
    await db.delete(match)
    await db.commit()
