import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pokemon import MatchPokemon, SeasonRosterPokemon
from app.schemas.pokemon import PokemonSet


async def get_draft_pool(db: AsyncSession, season_entry_id: uuid.UUID) -> list[SeasonRosterPokemon]:
    stmt = (
        select(SeasonRosterPokemon)
        .where(SeasonRosterPokemon.season_entry_id == season_entry_id)
        .order_by(SeasonRosterPokemon.slot)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def replace_draft_pool(
    db: AsyncSession, season_entry_id: uuid.UUID, pokemon_in: PokemonSet
) -> list[SeasonRosterPokemon]:
    """Replace a roster entry's drafted pool. Slots are assigned from list order,
    so reordering in the admin UI is just a re-send."""
    await db.execute(
        delete(SeasonRosterPokemon).where(SeasonRosterPokemon.season_entry_id == season_entry_id)
    )
    for slot, pokemon in enumerate(pokemon_in.pokemon):
        db.add(
            SeasonRosterPokemon(
                season_entry_id=season_entry_id,
                pokeapi_id=pokemon.pokeapi_id,
                species_name=pokemon.species_name,
                slot=slot,
            )
        )
    await db.commit()
    return await get_draft_pool(db, season_entry_id)


async def replace_match_team(
    db: AsyncSession, match_id: uuid.UUID, player_id: uuid.UUID, pokemon_in: PokemonSet
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
