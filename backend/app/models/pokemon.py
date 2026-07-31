import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.player import Player
    from app.models.season_entry import SeasonEntry


class SeasonRosterPokemon(Base):
    """One continuous ownership tenure for a Pokémon on a season roster.

    species_name is stored alongside pokeapi_id so rendering never depends on an
    external lookup.  A released row is retained: match teams are independent
    snapshots, while these dated tenures explain who owned a Pokémon when.
    """

    __tablename__ = "season_roster_pokemon"
    __table_args__ = (
        CheckConstraint(
            "(released_at IS NULL AND release_type IS NULL) OR "
            "(released_at IS NOT NULL AND release_type IS NOT NULL)",
            name="ck_season_roster_pokemon_release_complete",
        ),
        CheckConstraint(
            "released_at IS NULL OR acquired_at IS NULL OR released_at >= acquired_at",
            name="ck_season_roster_pokemon_tenure_order",
        ),
        Index(
            "uq_season_roster_pokemon_active_species",
            "season_entry_id",
            "pokeapi_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
            sqlite_where=text("released_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    season_entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("season_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # PokeAPI's own id rather than the national dex number, so regional forms
    # and megas (which share a dex number with their base species) resolve to
    # the right sprite.
    pokeapi_id: Mapped[int] = mapped_column(Integer, nullable=False)
    species_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # Draft order within the player's pool; also the display order.
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    # Null acquired_at means "owned since the start of our recorded history".
    # Existing rows are migrated this way because their real acquisition date is
    # unknowable.  New changes always receive an effective timestamp.
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acquisition_type: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    release_type: Mapped[str | None] = mapped_column(String(16), nullable=True)

    season_entry: Mapped["SeasonEntry"] = relationship(
        "SeasonEntry", back_populates="pokemon_history", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<SeasonRosterPokemon entry_id={self.season_entry_id} species={self.species_name!r}>"


class MatchPokemon(Base):
    """A Pokémon one player actually brought to one match - normally a subset of
    that player's drafted pool for the season."""

    __tablename__ = "match_pokemon"
    __table_args__ = (
        UniqueConstraint("match_id", "player_id", "pokeapi_id", name="uq_match_pokemon_match_player_species"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pokeapi_id: Mapped[int] = mapped_column(Integer, nullable=False)
    species_name: Mapped[str] = mapped_column(String(64), nullable=False)

    match: Mapped["Match"] = relationship("Match", back_populates="pokemon", lazy="raise")
    player: Mapped["Player"] = relationship("Player", lazy="raise")

    def __repr__(self) -> str:
        return f"<MatchPokemon match_id={self.match_id} species={self.species_name!r}>"
