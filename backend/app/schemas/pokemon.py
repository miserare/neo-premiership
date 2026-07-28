import uuid

from pydantic import BaseModel, ConfigDict, Field


class PokemonInput(BaseModel):
    """One Pokémon as supplied by the admin UI's species picker."""

    # PokeAPI's id, which is what the sprite URL is keyed on.
    pokeapi_id: int = Field(..., ge=1)
    species_name: str = Field(..., min_length=1, max_length=64)


class SeasonRosterPokemonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pokeapi_id: int
    species_name: str
    slot: int


class MatchPokemonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    player_id: uuid.UUID
    pokeapi_id: int
    species_name: str


class PokemonSet(BaseModel):
    """Whole-collection replacement.

    Drafted pools and brought teams are edited as a unit in the admin UI, so a
    single PUT of the full list is both simpler to drive and free of the
    ordering/uniqueness races that per-row create/delete would introduce.
    """

    pokemon: list[PokemonInput] = Field(default_factory=list, max_length=24)
