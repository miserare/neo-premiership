import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.season import Season

DEFAULT_ELO_RATING = 1000


class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    discord_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    join_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    elo_rating: Mapped[int] = mapped_column(Integer, default=DEFAULT_ELO_RATING, nullable=False)
    # Marks the single tombstone player that a deleted player's matches are
    # reassigned to, so match history survives the deletion. Excluded from
    # player listings, standings, and every admin picker.
    is_placeholder: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa_false(), nullable=False
    )

    # A player can be the recorded champion of multiple seasons.
    # Games (not modeled yet) will eventually FK to both Player and Season.
    championships: Mapped[list["Season"]] = relationship(
        "Season",
        back_populates="champion",
        foreign_keys="Season.champion_id",
    )

    def __repr__(self) -> str:
        return f"<Player id={self.id} username={self.username!r}>"
