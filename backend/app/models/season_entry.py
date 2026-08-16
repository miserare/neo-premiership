import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.pokemon import SeasonRosterPokemon
    from app.models.season import Season


class SeasonEntry(Base):
    """A player's roster membership in a season - the historical roster record."""

    __tablename__ = "season_entries"
    __table_args__ = (UniqueConstraint("season_id", "player_id", name="uq_season_entries_season_player"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Legacy manual secondary tie-break value. Pokémon differential is derived
    # from MatchGame scores and is always considered first.
    tiebreaker_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    player: Mapped["Player"] = relationship("Player", lazy="raise")
    season: Mapped["Season"] = relationship("Season", lazy="raise")
    pokemon_history: Mapped[list["SeasonRosterPokemon"]] = relationship(
        "SeasonRosterPokemon",
        back_populates="season_entry",
        cascade="all, delete-orphan",
        order_by="SeasonRosterPokemon.slot, SeasonRosterPokemon.acquired_at",
        lazy="raise",
    )

    @property
    def pokemon(self) -> list["SeasonRosterPokemon"]:
        """The currently owned pool, kept under the original API field name."""
        return sorted(
            (pokemon for pokemon in self.pokemon_history if pokemon.released_at is None),
            key=lambda pokemon: pokemon.slot,
        )

    @property
    def former_pokemon(self) -> list["SeasonRosterPokemon"]:
        """Released tenures, newest release first, for roster history."""
        return sorted(
            (pokemon for pokemon in self.pokemon_history if pokemon.released_at is not None),
            key=lambda pokemon: (pokemon.released_at, pokemon.slot),
            reverse=True,
        )

    def __repr__(self) -> str:
        return f"<SeasonEntry season_id={self.season_id} player_id={self.player_id}>"
