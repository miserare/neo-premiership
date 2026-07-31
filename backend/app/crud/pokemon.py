import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import MatchPokemon, SeasonRosterPokemon
from app.models.season_entry import SeasonEntry
from app.schemas.pokemon import MatchPokemonSet, RosterPokemonSet


async def get_draft_pool(db: AsyncSession, season_entry_id: uuid.UUID) -> list[SeasonRosterPokemon]:
    stmt = (
        select(SeasonRosterPokemon)
        .where(
            SeasonRosterPokemon.season_entry_id == season_entry_id,
            SeasonRosterPokemon.released_at.is_(None),
        )
        .order_by(SeasonRosterPokemon.slot)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _utc(value: datetime) -> datetime:
    """Normalize timestamps before Python comparisons (SQLite may drop tzinfo)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def replace_draft_pool(
    db: AsyncSession, season_entry_id: uuid.UUID, pokemon_in: RosterPokemonSet
) -> list[SeasonRosterPokemon]:
    """Reconcile the current roster without deleting ownership history.

    Rows removed from the desired pool are closed at ``effective_at``. Additions
    begin a new tenure; unchanged Pokémon retain their original acquisition
    metadata. MatchPokemon rows are deliberately untouched historical snapshots.
    """
    effective_at = _utc(pokemon_in.effective_at)
    result = await db.execute(
        select(SeasonRosterPokemon).where(
            SeasonRosterPokemon.season_entry_id == season_entry_id,
            SeasonRosterPokemon.released_at.is_(None),
        )
    )
    current = {pokemon.pokeapi_id: pokemon for pokemon in result.scalars().all()}
    desired = {pokemon.pokeapi_id: (slot, pokemon) for slot, pokemon in enumerate(pokemon_in.pokemon)}

    for pokeapi_id, owned in current.items():
        requested = desired.get(pokeapi_id)
        if requested is not None:
            slot, pokemon = requested
            owned.slot = slot
            owned.species_name = pokemon.species_name
            continue

        if owned.acquired_at is not None and effective_at < _utc(owned.acquired_at):
            raise ValueError(f"{owned.species_name} cannot be released before it was acquired")
        owned.released_at = effective_at
        owned.release_type = pokemon_in.change_type.value

    # Close releases before inserting reacquisitions so active-row uniqueness
    # checks never see both the old and new tenure as current.
    await db.flush()

    for pokeapi_id, (slot, pokemon) in desired.items():
        if pokeapi_id in current:
            continue

        # Backdated changes must not overlap a later ownership tenure.
        overlap = await db.scalar(
            select(SeasonRosterPokemon.id)
            .where(
                SeasonRosterPokemon.season_entry_id == season_entry_id,
                SeasonRosterPokemon.pokeapi_id == pokeapi_id,
                or_(
                    SeasonRosterPokemon.released_at.is_(None),
                    SeasonRosterPokemon.released_at > effective_at,
                ),
            )
            .limit(1)
        )
        if overlap is not None:
            raise ValueError(f"{pokemon.species_name} already has an ownership tenure after that time")

        db.add(
            SeasonRosterPokemon(
                season_entry_id=season_entry_id,
                pokeapi_id=pokemon.pokeapi_id,
                species_name=pokemon.species_name,
                slot=slot,
                acquired_at=effective_at,
                acquisition_type=pokemon_in.change_type.value,
            )
        )
    await db.commit()
    return await get_draft_pool(db, season_entry_id)


async def replace_match_team(
    db: AsyncSession, match_id: uuid.UUID, player_id: uuid.UUID, pokemon_in: MatchPokemonSet
) -> None:
    """Replace what one player brought to one match, leaving the opponent's
    side of the same match untouched."""
    await db.execute(
        delete(MatchPokemon).where(
            MatchPokemon.match_id == match_id, MatchPokemon.player_id == player_id
        )
    )
    for pokemon in pokemon_in.pokemon:
        db.add(
            MatchPokemon(
                match_id=match_id,
                player_id=player_id,
                pokeapi_id=pokemon.pokeapi_id,
                species_name=pokemon.species_name,
            )
        )
    await db.commit()


async def get_eligible_roster_pokemon(
    db: AsyncSession,
    season_id: uuid.UUID,
    player_id: uuid.UUID,
    played_at: datetime | None,
) -> list[SeasonRosterPokemon]:
    """Ownership tenures that cover a match's date.

    An undated legacy match returns the whole season history so an admin can
    still backfill its team. Once the match has a date, acquisition/release
    boundaries are enforced.
    """
    stmt = (
        select(SeasonRosterPokemon)
        .join(SeasonEntry, SeasonEntry.id == SeasonRosterPokemon.season_entry_id)
        .where(SeasonEntry.season_id == season_id, SeasonEntry.player_id == player_id)
    )
    if played_at is not None:
        stmt = stmt.where(
            or_(
                SeasonRosterPokemon.acquired_at.is_(None),
                SeasonRosterPokemon.acquired_at <= played_at,
            ),
            or_(
                SeasonRosterPokemon.released_at.is_(None),
                SeasonRosterPokemon.released_at > played_at,
            ),
        )
    result = await db.execute(stmt.order_by(SeasonRosterPokemon.slot))
    return list(result.scalars().all())


async def get_match_team_ids(
    db: AsyncSession, match_id: uuid.UUID, player_id: uuid.UUID
) -> set[int]:
    result = await db.execute(
        select(MatchPokemon.pokeapi_id).where(
            MatchPokemon.match_id == match_id,
            MatchPokemon.player_id == player_id,
        )
    )
    return set(result.scalars().all())
