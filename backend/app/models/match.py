import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.match_game import MatchGame
    from app.models.player import Player
    from app.models.pokemon import MatchPokemon
    from app.models.season import Season


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MatchStage(str, enum.Enum):
    GROUP = "group"
    PLAYOFFS = "playoffs"


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (CheckConstraint("home_player_id != away_player_id", name="ck_matches_distinct_players"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    home_player_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    away_player_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    winner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[MatchStatus] = mapped_column(
        Enum(
            MatchStatus,
            native_enum=False,
            length=16,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=MatchStatus.SCHEDULED,
        nullable=False,
        index=True,
    )
    stage: Mapped[MatchStage] = mapped_column(
        Enum(
            MatchStage,
            native_enum=False,
            length=16,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    # Display name for the round, e.g. "Group A", "Semifinal", "Grand Final".
    round_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Sort key for rounds within the playoff bracket (lower = earlier round).
    # Left null for group-stage matches, which aren't organized into rounds.
    round_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Sort key for a match's position within its round (e.g. bracket slot).
    bracket_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    replay_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # lazy="raise" forces call sites to eager-load these via joinedload/selectinload
    # (async SQLAlchemy can't lazy-load outside a greenlet anyway) so N+1s fail loudly.
    season: Mapped["Season"] = relationship("Season", lazy="raise")
    home_player: Mapped["Player"] = relationship("Player", foreign_keys=[home_player_id], lazy="raise")
    away_player: Mapped["Player"] = relationship("Player", foreign_keys=[away_player_id], lazy="raise")
    winner: Mapped["Player | None"] = relationship("Player", foreign_keys=[winner_id], lazy="raise")

    games: Mapped[list["MatchGame"]] = relationship(
        "MatchGame",
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchGame.game_number",
        lazy="raise",
    )
    pokemon: Mapped[list["MatchPokemon"]] = relationship(
        "MatchPokemon",
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchPokemon.pokeapi_id",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Match id={self.id} season_id={self.season_id} stage={self.stage}>"
