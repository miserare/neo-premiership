import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.match_game import MatchGame
    from app.models.player import Player
    from app.models.playoff_round import PlayoffRound
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
    __table_args__ = (
        CheckConstraint("home_player_id != away_player_id", name="ck_matches_distinct_players"),
        CheckConstraint("bracket_order IS NULL OR bracket_order > 0", name="ck_matches_bracket_order_positive"),
        CheckConstraint(
            "homepage_feature_order IS NULL OR homepage_feature_order > 0",
            name="ck_matches_homepage_feature_order_positive",
        ),
        # Two matches cannot occupy the same slot in the same round. Partial, so
        # the many matches with no round (group stage) or no slot yet are not
        # forced into a single-row uniqueness class. Both dialect keywords are
        # given: without sqlite_where the tests would exercise a *different*
        # index from production and prove nothing.
        Index(
            "uq_matches_playoff_round_bracket_order",
            "playoff_round_id",
            "bracket_order",
            unique=True,
            postgresql_where=text("playoff_round_id IS NOT NULL AND bracket_order IS NOT NULL"),
            sqlite_where=text("playoff_round_id IS NOT NULL AND bracket_order IS NOT NULL"),
        ),
    )

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
    # Which playoff round this match belongs to. Null for group-stage matches,
    # which are not organized into rounds. This - not round_label/round_order
    # below - is the authority on where a playoff match appears.
    playoff_round_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("playoff_rounds.id"), nullable=True, index=True
    )
    # The match's position within its round; 1 is the first/top match. Unique
    # within a round (see the partial index above).
    bracket_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- legacy, retained for rollback compatibility only ------------------
    # Before playoff rounds were modelled as rows, every match carried its own
    # copy of the round's name and position, which is what let matches in one
    # conceptual round disagree about both. New code MUST NOT read these as the
    # source of truth for playoff ordering - services.matches derives the
    # round's name and position from `playoff_round` instead.
    #
    # They are still written for playoff matches so that rolling this release
    # back to code that reads them renders the same bracket, and round_label is
    # still the real per-match label for GROUP matches ("Group A",
    # "Group - Matchday 1"), which have no round entity. A later, separately
    # reviewed migration drops them once production has stabilized.
    round_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    round_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    replay_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- homepage highlighting ---------------------------------------------
    # An explicit administrator decision, not a heuristic over dates or status:
    # a featured match appears in the homepage fixtures list whatever week it
    # falls in and whether it is scheduled, completed or cancelled.
    featured_on_homepage: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa_false(), nullable=False, index=True
    )
    # Position among the featured matches; null sorts after every numbered one.
    # Not unique - two matches sharing a position fall back to the deterministic
    # ordering in services.home rather than rejecting an administrator's edit.
    homepage_feature_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # lazy="raise" forces call sites to eager-load these via joinedload/selectinload
    # (async SQLAlchemy can't lazy-load outside a greenlet anyway) so N+1s fail loudly.
    season: Mapped["Season"] = relationship("Season", lazy="raise")
    home_player: Mapped["Player"] = relationship("Player", foreign_keys=[home_player_id], lazy="raise")
    away_player: Mapped["Player"] = relationship("Player", foreign_keys=[away_player_id], lazy="raise")
    winner: Mapped["Player | None"] = relationship("Player", foreign_keys=[winner_id], lazy="raise")
    playoff_round: Mapped["PlayoffRound | None"] = relationship(
        "PlayoffRound", back_populates="matches", lazy="raise"
    )

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
