import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.player import Player


class EloRatingEvent(Base):
    """One player's auditable rating change for one completed match."""

    __tablename__ = "elo_rating_events"
    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="uq_elo_rating_events_match_player"),
        CheckConstraint("result IN (0, 1)", name="ck_elo_rating_events_binary_result"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opponent_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    rating_before: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_after: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_change: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_score: Mapped[Decimal] = mapped_column(Numeric(8, 7), nullable=False)

    match: Mapped["Match"] = relationship("Match", lazy="raise")
    player: Mapped["Player"] = relationship("Player", foreign_keys=[player_id], lazy="raise")
    opponent: Mapped["Player"] = relationship("Player", foreign_keys=[opponent_id], lazy="raise")
