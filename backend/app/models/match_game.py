import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.player import Player


class MatchGame(Base):
    """One game within a match. A match is a series: best-of-one has a single
    game, a best-of-three has up to three. Each game carries its own replay so
    a series shows G1/G2/G3 links rather than one ambiguous "replay"."""

    __tablename__ = "match_games"
    __table_args__ = (UniqueConstraint("match_id", "game_number", name="uq_match_games_match_game"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 1-based position in the series.
    game_number: Mapped[int] = mapped_column(Integer, nullable=False)
    winner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    replay_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="games", lazy="raise")
    winner: Mapped["Player | None"] = relationship("Player", foreign_keys=[winner_id], lazy="raise")

    def __repr__(self) -> str:
        return f"<MatchGame match_id={self.match_id} game={self.game_number}>"
