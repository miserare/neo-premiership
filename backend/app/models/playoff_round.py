import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.season import Season


class PlayoffRound(Base):
    """One round of a season's playoff bracket, as a row rather than a string
    repeated on every match.

    ``display_order`` is the only thing that decides where a round appears.
    Labels are free text - "First Round", "QF", "Ottavi di finale" - and are
    never parsed, matched against a known list, or sorted on. Dates are not
    consulted either, so a postponed or late-entered match cannot move its
    round. A round exists independently of its matches, so next season's
    bracket can be laid out before a single game is played.
    """

    __tablename__ = "playoff_rounds"
    __table_args__ = (
        # One round per position per season. Reordering therefore has to be
        # atomic - see crud.playoff_rounds.reorder_rounds.
        UniqueConstraint("season_id", "display_order", name="uq_playoff_rounds_season_display_order"),
        CheckConstraint("display_order > 0", name="ck_playoff_rounds_display_order_positive"),
        # Both length() and trim() exist in PostgreSQL and SQLite, so the same
        # constraint holds in production and in tests.
        CheckConstraint("length(trim(label)) > 0", name="ck_playoff_rounds_label_not_empty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # lazy="raise" matches the rest of the model layer: call sites must
    # eager-load, so an N+1 fails loudly instead of quietly.
    season: Mapped["Season"] = relationship("Season", lazy="raise")
    matches: Mapped[list["Match"]] = relationship(
        "Match",
        back_populates="playoff_round",
        order_by="Match.bracket_order",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<PlayoffRound id={self.id} label={self.label!r} display_order={self.display_order}>"
