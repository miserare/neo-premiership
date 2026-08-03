import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.playoff_round import PlayoffRound
from app.schemas.playoff_round import PlayoffRoundCreate, PlayoffRoundUpdate

# Reordering has to pass through a range of positions that cannot collide with
# any real one. Positions are always contiguous 1..N, so any offset larger than
# the number of rounds a season could plausibly have is safe - and it keeps the
# intermediate values positive, so the display_order > 0 check still holds.
_REORDER_OFFSET = 100_000


class RoundNotEmptyError(Exception):
    """Raised when a round that still holds matches is deleted."""

    def __init__(self, match_count: int) -> None:
        self.match_count = match_count
        super().__init__(f"round still contains {match_count} match(es)")


class DuplicatePositionError(Exception):
    """Raised when a requested display_order is already taken in the season."""


async def get_rounds_for_season(db: AsyncSession, season_id: uuid.UUID) -> list[PlayoffRound]:
    """A season's rounds in presentation order.

    Ordered by display_order and nothing else - not by label, not by the dates
    of the matches inside. The id tie-breaker is defensive only; the unique
    constraint on (season_id, display_order) means it never actually decides.
    """
    stmt = (
        select(PlayoffRound)
        .where(PlayoffRound.season_id == season_id)
        .order_by(PlayoffRound.display_order, PlayoffRound.id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_round_by_id(db: AsyncSession, round_id: uuid.UUID) -> PlayoffRound | None:
    result = await db.execute(select(PlayoffRound).where(PlayoffRound.id == round_id))
    return result.scalar_one_or_none()


async def count_matches_by_round(db: AsyncSession, season_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Match counts for every round in a season, in one query (not one per round)."""
    stmt = (
        select(Match.playoff_round_id, func.count(Match.id))
        .join(PlayoffRound, PlayoffRound.id == Match.playoff_round_id)
        .where(PlayoffRound.season_id == season_id)
        .group_by(Match.playoff_round_id)
    )
    result = await db.execute(stmt)
    return {round_id: count for round_id, count in result.all()}


async def count_matches_in_round(db: AsyncSession, round_id: uuid.UUID) -> int:
    result = await db.execute(select(func.count(Match.id)).where(Match.playoff_round_id == round_id))
    return int(result.scalar_one())


async def create_round(db: AsyncSession, season_id: uuid.UUID, round_in: PlayoffRoundCreate) -> PlayoffRound:
    if round_in.display_order is None:
        highest = await db.execute(
            select(func.max(PlayoffRound.display_order)).where(PlayoffRound.season_id == season_id)
        )
        display_order = (highest.scalar_one_or_none() or 0) + 1
    else:
        display_order = round_in.display_order
        taken = await db.execute(
            select(PlayoffRound.id).where(
                PlayoffRound.season_id == season_id, PlayoffRound.display_order == display_order
            )
        )
        if taken.scalar_one_or_none() is not None:
            raise DuplicatePositionError(f"another round in this season is already at position {display_order}")

    playoff_round = PlayoffRound(season_id=season_id, label=round_in.label, display_order=display_order)
    db.add(playoff_round)
    await db.commit()
    await db.refresh(playoff_round)
    return playoff_round


async def update_round(db: AsyncSession, playoff_round: PlayoffRound, round_in: PlayoffRoundUpdate) -> PlayoffRound:
    """Rename in place. display_order is deliberately untouched, so a rename
    can never move a round."""
    playoff_round.label = round_in.label
    # Keep the legacy mirror on this round's matches in step. Nothing reads it
    # at runtime; it exists so that a rollback to the previous release still
    # renders the right bracket. See models.match for the full note.
    await db.execute(
        update(Match).where(Match.playoff_round_id == playoff_round.id).values(round_label=round_in.label)
    )
    await db.commit()
    await db.refresh(playoff_round)
    return playoff_round


async def reorder_rounds(db: AsyncSession, season_id: uuid.UUID, round_ids: list[uuid.UUID]) -> list[PlayoffRound]:
    """Rewrite every round's position from the caller's complete ordered list.

    Two-phase inside one transaction: park every affected row at an offset
    position, then write the final contiguous 1..N. A direct rewrite would
    transiently put two rounds on the same display_order and trip the unique
    constraint - and unlike a deferred constraint, this behaves identically on
    PostgreSQL and SQLite, so the tests exercise what production runs.
    """
    existing = await get_rounds_for_season(db, season_id)
    existing_ids = {playoff_round.id for playoff_round in existing}
    if set(round_ids) != existing_ids:
        raise ValueError("round_ids must list exactly the rounds of this season, each once")

    for position, round_id in enumerate(round_ids, start=1):
        await db.execute(
            update(PlayoffRound)
            .where(PlayoffRound.id == round_id)
            .values(display_order=position + _REORDER_OFFSET)
        )
    for position, round_id in enumerate(round_ids, start=1):
        await db.execute(
            update(PlayoffRound).where(PlayoffRound.id == round_id).values(display_order=position)
        )
        # Legacy mirror, for rollback compatibility only - see update_round.
        await db.execute(
            update(Match).where(Match.playoff_round_id == round_id).values(round_order=position)
        )

    await db.commit()
    return await get_rounds_for_season(db, season_id)


async def delete_round(db: AsyncSession, playoff_round: PlayoffRound) -> None:
    """Delete an empty round. A round holding matches is refused rather than
    silently orphaning or deleting them."""
    match_count = await count_matches_in_round(db, playoff_round.id)
    if match_count:
        raise RoundNotEmptyError(match_count)
    await db.delete(playoff_round)
    await db.commit()
