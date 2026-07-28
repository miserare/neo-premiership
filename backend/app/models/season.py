import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID

if TYPE_CHECKING:
    from app.models.player import Player


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    champion_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    sheet_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    champion: Mapped["Player | None"] = relationship(
        "Player",
        back_populates="championships",
        foreign_keys=[champion_id],
    )

    def __repr__(self) -> str:
        return f"<Season id={self.id} name={self.name!r}>"
