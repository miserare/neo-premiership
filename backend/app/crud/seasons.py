import uuid
from datetime import date

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.match import Match
from app.models.season import Season
from app.models.season_entry import SeasonEntry
from app.schemas.season import SeasonCreate, SeasonUpdate
from app.utils.serialization import stringify_urls

_URL_FIELDS = ("sheet_url",)


def _with_champion(stmt):
    return stmt.options(joinedload(Season.champion))


async def get_seasons(db: AsyncSession, skip: int = 0, limit: int = 100, q: str | None = None) -> list[Season]:
    stmt = _with_champion(select(Season)).order_by(Season.start_date.desc())
    if q:
        stmt = stmt.where(Season.name.ilike(f"%{q}%"))
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_season_by_id(db: AsyncSession, season_id: uuid.UUID) -> Season | None:
    stmt = _with_champion(select(Season)).where(Season.id == season_id)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_active_season(db: AsyncSession, today: date) -> Season | None:
    """A season is active when today is on/after start_date and its end_date
    is either null or has not yet passed."""
    stmt = (
        _with_champion(select(Season))
        .where(Season.start_date <= today, or_(Season.end_date.is_(None), Season.end_date >= today))
        .order_by(Season.start_date.desc())
    )
    result = await db.execute(stmt)
    return result.unique().scalars().first()


async def get_most_recently_started_season(db: AsyncSession) -> Season | None:
    stmt = _with_champion(select(Season)).order_by(Season.start_date.desc())
    result = await db.execute(stmt)
    return result.unique().scalars().first()


async def create_season(db: AsyncSession, season_in: SeasonCreate) -> Season:
    data = stringify_urls(season_in.model_dump(), _URL_FIELDS)
    season = Season(**data)
    db.add(season)
    await db.commit()
    # get_season_by_id rather than db.refresh(), so champion comes back
    # eager-loaded (it's accessed unconditionally by SeasonSummary/SeasonDetail).
    loaded = await get_season_by_id(db, season.id)
    assert loaded is not None
    return loaded


async def update_season(db: AsyncSession, season: Season, season_in: SeasonUpdate) -> Season:
    data = stringify_urls(season_in.model_dump(exclude_unset=True), _URL_FIELDS)
    for field, value in data.items():
        setattr(season, field, value)
    await db.commit()
    # populate_existing - `season` is already in the identity map (the router
    # loaded it before calling this), and with expire_on_commit=False its
    # `champion` relationship stays whatever it was at that load. A plain
    # re-query wouldn't override an already-populated relationship on the same
    # instance, so a changed champion_id would come back stale otherwise.
    stmt = _with_champion(select(Season)).where(Season.id == season.id).execution_options(populate_existing=True)
    result = await db.execute(stmt)
    loaded = result.unique().scalar_one_or_none()
    assert loaded is not None
    return loaded


async def delete_season(db: AsyncSession, season: Season) -> None:
    # Explicit child deletes rather than relying on the DB's ON DELETE CASCADE -
    # SQLite (used in tests) doesn't enforce foreign keys unless a per-connection
    # pragma is set, so the cascade can't be relied on there.
    await db.execute(delete(Match).where(Match.season_id == season.id))
    await db.execute(delete(SeasonEntry).where(SeasonEntry.season_id == season.id))
    await db.delete(season)
    await db.commit()
