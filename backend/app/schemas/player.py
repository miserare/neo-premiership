import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pokemon import SeasonRosterPokemonRead

if TYPE_CHECKING:
    from app.schemas.match import MatchRead


class PlayerBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=32, description="Unique in-league display name")
    discord_id: str | None = Field(default=None, max_length=32)
    is_active: bool = True


class PlayerCreate(PlayerBase):
    elo_rating: int | None = Field(default=None, ge=0)


class PlayerUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=32)
    discord_id: str | None = None
    is_active: bool | None = None
    elo_rating: int | None = Field(default=None, ge=0)


class PlayerRead(PlayerBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    join_date: datetime
    elo_rating: int


class PlayerSummary(BaseModel):
    """Lightweight player identity, embedded in rosters, matches, and standings."""

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


class PlayerDetail(BaseModel):
    id: uuid.UUID
    username: str
    discord_id: str | None
    join_date: datetime
    is_active: bool
    elo_rating: int
    most_recent_season_record: PlayerSeasonRecord | None
    historical_record: PlayerRecord
    season_records: list[PlayerSeasonRecord]
    backlog: list["MatchRead"]
    completed_matches: list["MatchRead"]
