import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models.match import MatchStage, MatchStatus
from app.schemas.player import PlayerSummary
from app.schemas.pokemon import MatchPokemonRead


class MatchGameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None
    game_number: int
    winner_id: uuid.UUID | None
    replay_url: str | None


class MatchGameInput(BaseModel):
    game_number: int = Field(..., ge=1, le=9)
    winner_id: uuid.UUID | None = None
    replay_url: HttpUrl | None = None


class MatchGamesSet(BaseModel):
    """Whole-series replacement - see PokemonSet for why this is a PUT."""

    games: list[MatchGameInput] = Field(default_factory=list, max_length=9)

    @model_validator(mode="after")
    def _unique_game_numbers(self) -> "MatchGamesSet":
        numbers = [game.game_number for game in self.games]
        if len(numbers) != len(set(numbers)):
            raise ValueError("game_number must be unique within a match")
        return self


class MatchSeries(BaseModel):
    """Series tally derived from the individual games, so a best-of-three reads
    as "2-1" without anyone maintaining a separate score field."""

    home_wins: int
    away_wins: int
    game_count: int


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    season_id: uuid.UUID
    home_player: PlayerSummary
    away_player: PlayerSummary
    winner_id: uuid.UUID | None
    status: MatchStatus
    stage: MatchStage
    round_label: str | None
    round_order: int | None
    bracket_order: int | None
    scheduled_at: datetime | None
    completed_at: datetime | None
    home_score: int | None
    away_score: int | None
    replay_url: str | None
    youtube_url: str | None
    games: list[MatchGameRead]
    series: MatchSeries
    home_team: list[MatchPokemonRead]
    away_team: list[MatchPokemonRead]


class MatchCreate(BaseModel):
    season_id: uuid.UUID
    home_player_id: uuid.UUID
    away_player_id: uuid.UUID
    stage: MatchStage
    status: MatchStatus = MatchStatus.SCHEDULED
    round_label: str | None = None
    round_order: int | None = None
    bracket_order: int | None = None
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    home_score: int | None = None
    away_score: int | None = None
    winner_id: uuid.UUID | None = None
    replay_url: HttpUrl | None = None
    youtube_url: HttpUrl | None = None

    @model_validator(mode="after")
    def _validate(self) -> "MatchCreate":
        if self.home_player_id == self.away_player_id:
            raise ValueError("home_player_id and away_player_id must be different players")
        if self.winner_id is not None and self.winner_id not in (self.home_player_id, self.away_player_id):
            raise ValueError("winner_id must be the home or away player")
        if self.status == MatchStatus.COMPLETED and self.winner_id is None:
            raise ValueError("a completed match requires a winner_id")
        if self.status == MatchStatus.COMPLETED and self.completed_at is None:
            raise ValueError("a completed match requires completed_at for Elo ordering")
        if self.completed_at is not None and self.completed_at.utcoffset() is None:
            raise ValueError("completed_at must include a timezone")
        return self


class MatchUpdate(BaseModel):
    """Participants/season/stage are immutable after creation - delete and
    recreate the match if they need to change."""

    status: MatchStatus | None = None
    round_label: str | None = None
    round_order: int | None = None
    bracket_order: int | None = None
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    home_score: int | None = None
    away_score: int | None = None
    winner_id: uuid.UUID | None = None
    replay_url: HttpUrl | None = None
    youtube_url: HttpUrl | None = None

    @model_validator(mode="after")
    def _validate_timestamps(self) -> "MatchUpdate":
        if self.completed_at is not None and self.completed_at.utcoffset() is None:
            raise ValueError("completed_at must include a timezone")
        return self
