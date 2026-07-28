import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.season_entry import SeasonEntry
from app.schemas.season import SeasonEntryCreate, SeasonEntryUpdate


async def get_roster(db: AsyncSession, season_id: uuid.UUID) -> list[SeasonEntry]:
    stmt = (
        select(SeasonEntry)
        .where(SeasonEntry.season_id == season_id)
        .options(joinedload(SeasonEntry.player), selectinload(SeasonEntry.pokemon))
        .order_by(SeasonEntry.group_label, SeasonEntry.id)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_player_season_entries(db: AsyncSession, player_id: uuid.UUID) -> list[SeasonEntry]:
    """A player's roster history, newest season first."""
    stmt = (
        select(SeasonEntry)
        .where(SeasonEntry.player_id == player_id)
        .options(joinedload(SeasonEntry.season), selectinload(SeasonEntry.pokemon))
    )
    result = await db.execute(stmt)
    entries = list(result.unique().scalars().all())
    return sorted(entries, key=lambda entry: entry.season.start_date, reverse=True)


async def get_entry_by_id(db: AsyncSession, entry_id: uuid.UUID, refresh: bool = False) -> SeasonEntry | None:
    stmt = (
        select(SeasonEntry)
        .where(SeasonEntry.id == entry_id)
        .options(joinedload(SeasonEntry.player), selectinload(SeasonEntry.pokemon))
    )
    if refresh:
        # Without this the already-loaded `pokemon` collection survives a
        # re-query, so a just-replaced draft pool would come back stale.
        stmt = stmt.execution_options(populate_existing=True)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def create_entry(db: AsyncSession, season_id: uuid.UUID, entry_in: SeasonEntryCreate) -> SeasonEntry:
    entry = SeasonEntry(season_id=season_id, **entry_in.model_dump())
    db.add(entry)
    await db.commit()
    # get_entry_by_id rather than db.refresh(), since the player relationship
    # is lazy="raise" and refresh() would trigger it outside an eager-load.
    loaded = await get_entry_by_id(db, entry.id)
    assert loaded is not None
    return loaded


async def update_entry(db: AsyncSession, entry: SeasonEntry, entry_in: SeasonEntryUpdate) -> SeasonEntry:
    for field, value in entry_in.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    await db.commit()
    loaded = await get_entry_by_id(db, entry.id)
    assert loaded is not None
    return loaded


async def delete_entry(db: AsyncSession, entry: SeasonEntry) -> None:
    await db.delete(entry)
    await db.commit()
