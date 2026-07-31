import enum
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class RosterChangeType(str, enum.Enum):
    DRAFT = "draft"
    FREE_AGENCY = "free_agency"
    TRADE = "trade"
    CORRECTION = "correction"


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
    acquired_at: datetime | None
    released_at: datetime | None
    acquisition_type: RosterChangeType
    release_type: RosterChangeType | None


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


class RosterPokemonSet(PokemonSet):
    """Desired current roster and metadata for additions/removals in this save."""

    effective_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    change_type: RosterChangeType = RosterChangeType.DRAFT


class MatchPokemonSet(BaseModel):
    """A team actually brought to one match."""

    pokemon: list[PokemonInput] = Field(default_factory=list, max_length=6)
