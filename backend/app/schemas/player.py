"""Player schemas.

Split deliberately into public and administrator shapes. `discord_id` is
personal contact information and must never appear in an anonymous response, so
it lives only on the *Admin* models, which are returned exclusively from
authenticated routes. The public models simply do not declare the field, so it
cannot leak by accident even if an ORM object carrying it is passed in.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.models.player import MAX_BIOGRAPHY_LENGTH
from app.schemas.common import SlugStr
from app.schemas.pokemon import SeasonRosterPokemonRead

if TYPE_CHECKING:
    from app.schemas.match import MatchRead


# --------------------------------------------------------------- write models


class PlayerCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=32, description="Unique in-league display name")
    # Optional: derived from the username when omitted. Supplying it is how an
    # administrator picks a slug that the username would not produce.
    slug: SlugStr | None = None
    biography: str | None = Field(default=None, max_length=MAX_BIOGRAPHY_LENGTH)
    discord_id: str | None = Field(default=None, max_length=32)
    is_active: bool = True
    initial_elo_rating: int | None = Field(default=None, ge=-10_000, le=10_000)
    is_site_creator: bool = False


class PlayerUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=32)
    # Only ever changed deliberately - renaming a player leaves their slug, and
    # therefore their existing links, alone.
    slug: SlugStr | None = None
    biography: str | None = Field(default=None, max_length=MAX_BIOGRAPHY_LENGTH)
    discord_id: str | None = None
    is_active: bool | None = None
    initial_elo_rating: int | None = Field(default=None, ge=-10_000, le=10_000)
    is_site_creator: bool | None = None


# -------------------------------------------------------------- public models


class PlayerPublic(BaseModel):
    """A player as anyone may see them. No contact details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    username: str
    join_date: datetime
    is_active: bool
    elo_rating: int


class PlayerSummary(BaseModel):
    """Lightweight player identity, embedded in rosters, matches, and standings.

    Public by construction - this is the only player shape that appears nested
    inside season, match, standings and home responses. It carries `slug`
    because every one of those places links to the player, but deliberately not
    `biography`: a season roster of twenty would otherwise ship twenty essays.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    username: str
    elo_rating: int
    is_active: bool


class ChampionshipRead(BaseModel):
    """A season this player is the recorded champion of.

    Derived from `seasons.champion_id`; there is deliberately no `is_champion`
    column to keep in step with it.
    """

    season_id: uuid.UUID
    season_slug: str
    season_name: str
    start_date: date
    end_date: date | None


class PlayerRecord(BaseModel):
    wins: int
    losses: int


class PlayerSeasonRecord(BaseModel):
    season_id: uuid.UUID
    season_slug: str
    season_name: str
    wins: int
    losses: int
    # The Pokémon this player drafted that season, for the sprite roster on
    # their profile.
    pokemon: list[SeasonRosterPokemonRead] = []
    former_pokemon: list[SeasonRosterPokemonRead] = []


class EloRatingHistoryEntry(BaseModel):
    match_id: uuid.UUID
    match_game_id: uuid.UUID
    game_number: int
    opponent_id: uuid.UUID
    opponent_slug: str
    opponent_username: str
    occurred_at: datetime
    result: int
    expected_score: float
    rating_before: int
    rating_after: int
    rating_change: int
    player_pokemon_score: int | None
    opponent_pokemon_score: int | None


class PlayerDetail(BaseModel):
    """Public player profile. Deliberately has no discord_id field."""

    id: uuid.UUID
    slug: str
    username: str
    biography: str | None
    join_date: datetime
    is_active: bool
    elo_rating: int
    is_site_creator: bool
    # Empty for the placeholder player even if a deleted player's championships
    # were transferred to it - see services.records.
    championships: list[ChampionshipRead]
    elo_history: list[EloRatingHistoryEntry]
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

    biography: str | None = None
    discord_id: str | None = None
    initial_elo_rating: int
    is_site_creator: bool
