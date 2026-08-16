import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID
from app.utils.slugs import MAX_SLUG_LENGTH

if TYPE_CHECKING:
    from app.models.player import Player

MAX_HALL_OF_FAME_DESCRIPTION_LENGTH = 4000


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        # See Player.slug for why a lowercase check is what makes the plain
        # unique index case-insensitive.
        CheckConstraint("slug = lower(slug) AND length(slug) > 0", name="ck_seasons_slug_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # URL identity: /seasons/6/standings. Free text rather than a number, so a
    # season named "Summer 2027" gets a stable slug without inventing an index.
    slug: Mapped[str] = mapped_column(String(MAX_SLUG_LENGTH), unique=True, index=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    champion_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("players.id", ondelete="SET NULL"), nullable=True
    )
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The Hall of Fame's own prose about this championship. Kept apart from
    # `overview`, which describes the season itself and is shown elsewhere.
    hall_of_fame_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sheet_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    champion: Mapped["Player | None"] = relationship(
        "Player",
        back_populates="championships",
        foreign_keys=[champion_id],
    )

    def __repr__(self) -> str:
        return f"<Season id={self.id} name={self.name!r}>"
