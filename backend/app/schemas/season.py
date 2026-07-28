import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.match import MatchRead
from app.schemas.player import PlayerSummary
from app.schemas.pokemon import SeasonRosterPokemonRead


class SeasonSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    start_date: date
    end_date: date | None
    champion: PlayerSummary | None


class SeasonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    start_date: date
    end_date: date | None = None
    champion_id: uuid.UUID | None = None
    overview: str | None = None
    sheet_url: HttpUrl | None = None


class SeasonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    start_date: date | None = None
    end_date: date | None = None
    champion_id: uuid.UUID | None = None
    overview: str | None = None
    sheet_url: HttpUrl | None = None


class SeasonEntryCreate(BaseModel):
    player_id: uuid.UUID
    group_label: str | None = Field(default=None, max_length=32)
    tiebreaker_value: float | None = None


class SeasonEntryUpdate(BaseModel):
    group_label: str | None = Field(default=None, max_length=32)
    tiebreaker_value: float | None = None


class SeasonEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    player: PlayerSummary
    group_label: str | None
    tiebreaker_value: float | None
    pokemon: list[SeasonRosterPokemonRead]


class RosterEntry(BaseModel):
    player: PlayerSummary
    group_label: str | None
    pokemon: list[SeasonRosterPokemonRead]


class StandingsEntry(BaseModel):
    player: PlayerSummary
    wins: int
    losses: int
    tiebreaker_value: float | None


class StandingsGroup(BaseModel):
    group_label: str | None
    standings: list[StandingsEntry]


class BracketRound(BaseModel):
    round_label: str
    round_order: int
    matches: list[MatchRead]


class SeasonStream(BaseModel):
    url: str
    label: str


class SeasonDetail(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date | None
    is_active: bool
    sheet_url: str | None
    overview: str | None
    champion: PlayerSummary | None
    roster: list[RosterEntry]
    standings: list[StandingsGroup]
    bracket: list[BracketRound]
    streams: list[SeasonStream]
