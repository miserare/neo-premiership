import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.player import Player
    from app.models.season_entry import SeasonEntry


class SeasonRosterPokemon(Base):
    """A Pokémon in a player's drafted pool for one season.

    species_name is stored alongside pokeapi_id so rendering never depends on an
    external lookup, and a renamed/removed upstream entry can't blank the roster.
    """

    __tablename__ = "season_roster_pokemon"
    __table_args__ = (UniqueConstraint("season_entry_id", "slot", name="uq_season_roster_pokemon_entry_slot"),)

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

    season_entry: Mapped["SeasonEntry"] = relationship("SeasonEntry", back_populates="pokemon", lazy="raise")

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
