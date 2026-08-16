import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models.match import MatchStage, MatchStatus
from app.schemas.player import PlayerSummary
from app.schemas.pokemon import MatchPokemonRead, PokemonInput


class MatchGameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None
    game_number: int
    completed_at: datetime | None
    winner_id: uuid.UUID | None
    home_pokemon_score: int | None
    away_pokemon_score: int | None
    replay_url: str | None


class MatchGameInput(BaseModel):
    game_number: int = Field(..., ge=1, le=9)
    completed_at: datetime | None = None
    winner_id: uuid.UUID | None = None
    home_pokemon_score: int | None = Field(default=None, ge=0, le=6)
    away_pokemon_score: int | None = Field(default=None, ge=0, le=6)
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

    home_series_wins: int
    away_series_wins: int
    game_count: int
    wins_required: int


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    season_id: uuid.UUID
    home_player: PlayerSummary
    away_player: PlayerSummary
    winner_id: uuid.UUID | None
    status: MatchStatus
    stage: MatchStage
    playoff_round_id: uuid.UUID | None
    bracket_order: int | None
    # Backward-compatible mirrors. For a playoff match both are derived from
    # the referenced round, never from the legacy match columns; for a group
    # match round_label is the match's own group/matchday label and there is
    # no round order. See services.matches.to_match_read.
    round_label: str | None
    round_order: int | None
    scheduled_at: datetime | None
    completed_at: datetime | None
    best_of: int
    replay_url: str | None
    youtube_url: str | None
    featured_on_homepage: bool
    homepage_feature_order: int | None
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
    best_of: int = Field(default=1)
    playoff_round_id: uuid.UUID | None = None
    bracket_order: int | None = Field(default=None, gt=0)
    # Group-stage label only ("Group A", "Group - Matchday 1"). A playoff
    # match takes its label from its round and must not carry its own.
    round_label: str | None = Field(default=None, max_length=64)
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    # Legacy parent score columns are deliberately absent: they are retained in
    # the database for rollback only, never accepted as an API score.
    winner_id: uuid.UUID | None = None
    replay_url: HttpUrl | None = None
    youtube_url: HttpUrl | None = None
    featured_on_homepage: bool = False
    homepage_feature_order: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate(self) -> "MatchCreate":
        if self.home_player_id == self.away_player_id:
            raise ValueError("home_player_id and away_player_id must be different players")
        if self.best_of not in (1, 3, 5, 7, 9):
            raise ValueError("best_of must be one of 1, 3, 5, 7, or 9")
        if self.stage == MatchStage.GROUP and self.playoff_round_id is not None:
            raise ValueError("a group-stage match must not reference a playoff round")
        if self.stage == MatchStage.PLAYOFFS and self.round_label is not None:
            raise ValueError("a playoff match takes its label from its round; set playoff_round_id instead")
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
    best_of: int | None = None
    # Setting playoff_round_id moves the match between rounds; the router
    # validates the move against the match's stage and season.
    playoff_round_id: uuid.UUID | None = None
    bracket_order: int | None = Field(default=None, gt=0)
    round_label: str | None = Field(default=None, max_length=64)
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    winner_id: uuid.UUID | None = None
    replay_url: HttpUrl | None = None
    youtube_url: HttpUrl | None = None
    featured_on_homepage: bool | None = None
    homepage_feature_order: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_timestamps(self) -> "MatchUpdate":
        if self.best_of is not None and self.best_of not in (1, 3, 5, 7, 9):
            raise ValueError("best_of must be one of 1, 3, 5, 7, or 9")
        if self.completed_at is not None and self.completed_at.utcoffset() is None:
            raise ValueError("completed_at must include a timezone")
        return self


# ------------------------------------------------------- unified result entry


class MatchResultGameInput(BaseModel):
    """One game of a recorded series.

    `winner_id` is required, unlike MatchGameInput: this endpoint records what
    happened, and a played game has a winner. A game that has not been played
    yet is simply not sent.
    """

    game_number: int = Field(..., ge=1, le=9)
    completed_at: datetime
    winner_id: uuid.UUID | None = None
    home_pokemon_score: int = Field(..., ge=0, le=6)
    away_pokemon_score: int = Field(..., ge=0, le=6)
    replay_url: HttpUrl | None = None

    @model_validator(mode="after")
    def _validate_game(self) -> "MatchResultGameInput":
        if self.completed_at.utcoffset() is None:
            raise ValueError("completed_at must include a timezone")
        scores = (self.home_pokemon_score, self.away_pokemon_score)
        if not (
            (1 <= scores[0] <= 6 and scores[1] == 0)
            or (1 <= scores[1] <= 6 and scores[0] == 0)
        ):
            raise ValueError(
                "Pokémon score must have one winner from 1 through 6 and one loser at 0"
            )
        return self


class MatchResultSet(BaseModel):
    """A match's whole result, saved in one transaction.

    Replaces the previous three-request dance (PATCH the match, PUT the games,
    PUT each team). The series score and the match winner are *derived* from the
    game winners rather than typed in a second time, which is what makes a
    disagreement between them impossible.
    """

    # Only these two: cancelling a match stays on the existing PATCH endpoint,
    # which is also where the cancellation reasons and corrections already live.
    status: MatchStatus = MatchStatus.COMPLETED
    best_of: int
    completed_at: datetime | None = None
    games: list[MatchResultGameInput] = Field(default_factory=list, max_length=9)
    # Teams as actually used. Sent every time so a result save is a complete
    # statement of the match; omitting a side clears it.
    home_team: list[PokemonInput] = Field(default_factory=list, max_length=6)
    away_team: list[PokemonInput] = Field(default_factory=list, max_length=6)
    youtube_url: HttpUrl | None = None

    @model_validator(mode="after")
    def _validate(self) -> "MatchResultSet":
        if self.status not in (MatchStatus.COMPLETED, MatchStatus.SCHEDULED):
            raise ValueError("status must be 'completed' or 'scheduled'; cancel a match from match details")

        numbers = [game.game_number for game in self.games]
        if len(numbers) != len(set(numbers)):
            raise ValueError("game_number must be unique within a match")
        if self.best_of not in (1, 3, 5, 7, 9):
            raise ValueError("best_of must be one of 1, 3, 5, 7, or 9")
        if sorted(numbers) != list(range(1, len(numbers) + 1)):
            raise ValueError("game numbers must be contiguous and begin at 1")
        if len(self.games) > self.best_of:
            raise ValueError("a series cannot contain more games than its best_of format")

        for team in (self.home_team, self.away_team):
            ids = [pokemon.pokeapi_id for pokemon in team]
            if len(ids) != len(set(ids)):
                raise ValueError("the same Pokémon cannot appear twice on one match team")

        if self.completed_at is not None and self.completed_at.utcoffset() is None:
            raise ValueError("completed_at must include a timezone")

        if self.status == MatchStatus.COMPLETED:
            if self.completed_at is None:
                raise ValueError("a completed match requires completed_at for Elo ordering")
            if not self.games:
                raise ValueError("a completed match needs at least one game to derive its result from")
        return self
