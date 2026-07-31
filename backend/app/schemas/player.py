"""Player schemas.

Split deliberately into public and administrator shapes. `discord_id` is
personal contact information and must never appear in an anonymous response, so
it lives only on the *Admin* models, which are returned exclusively from
authenticated routes. The public models simply do not declare the field, so it
cannot leak by accident even if an ORM object carrying it is passed in.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pokemon import SeasonRosterPokemonRead

if TYPE_CHECKING:
    from app.schemas.match import MatchRead


# --------------------------------------------------------------- write models


class PlayerCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=32, description="Unique in-league display name")
    discord_id: str | None = Field(default=None, max_length=32)
    is_active: bool = True
    elo_rating: int | None = Field(default=None, ge=0)


class PlayerUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=32)
    discord_id: str | None = None
    is_active: bool | None = None
    elo_rating: int | None = Field(default=None, ge=0)


# -------------------------------------------------------------- public models


class PlayerPublic(BaseModel):
    """A player as anyone may see them. No contact details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    join_date: datetime
    is_active: bool
    elo_rating: int


class PlayerSummary(BaseModel):
    """Lightweight player identity, embedded in rosters, matches, and standings.

    Public by construction - this is the only player shape that appears nested
    inside season, match, standings and home responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    elo_rating: int
    is_active: bool


class PlayerRecord(BaseModel):
    wins: int
    losses: int


class PlayerSeasonRecord(BaseModel):
    season_id: uuid.UUID
    season_name: str
    wins: int
    losses: int
    # The Pokémon this player drafted that season, for the sprite roster on
    # their profile.
    pokemon: list[SeasonRosterPokemonRead] = []
    former_pokemon: list[SeasonRosterPokemonRead] = []


class PlayerDetail(BaseModel):
    """Public player profile. Deliberately has no discord_id field."""

    id: uuid.UUID
    username: str
    join_date: datetime
    is_active: bool
    elo_rating: int
    most_recent_season_record: PlayerSeasonRecord | None
    historical_record: PlayerRecord
    season_records: list[PlayerSeasonRecord]
    backlog: list["MatchRead"]
    completed_matches: list["MatchRead"]


# --------------------------------------------------------- administrator-only


class PlayerAdmin(PlayerPublic):
    """Everything in PlayerPublic plus private administrative fields.

    Only ever returned from routes guarded by an administrator session.
    """

    discord_id: str | None = None
