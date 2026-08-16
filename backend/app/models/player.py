import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, text
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID
from app.utils.slugs import MAX_SLUG_LENGTH

if TYPE_CHECKING:
    from app.models.season import Season

DEFAULT_ELO_RATING = 1000
MAX_BIOGRAPHY_LENGTH = 4000


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        # lower()/length() both exist in PostgreSQL and SQLite, so tests
        # exercise the same constraint production does. The full character set
        # is enforced in the schema layer; what the database guarantees is the
        # part uniqueness depends on - a stored slug is always lowercase and
        # non-empty, which makes the plain unique index below case-insensitive.
        CheckConstraint("slug = lower(slug) AND length(slug) > 0", name="ck_players_slug_lowercase"),
        CheckConstraint(
            "NOT (is_placeholder AND is_site_creator)", name="ck_players_placeholder_not_site_creator"
        ),
        Index(
            "uq_players_single_site_creator",
            "is_site_creator",
            unique=True,
            postgresql_where=text("is_site_creator"),
            sqlite_where=text("is_site_creator = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    # Canonical URL identity: /player/psykick. Stored separately from username
    # and deliberately not re-derived on rename, so existing links keep working.
    slug: Mapped[str] = mapped_column(String(MAX_SLUG_LENGTH), unique=True, index=True, nullable=False)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    discord_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    join_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # The immutable starting point for chronological Elo calculation. The
    # current rating below is a derived cache rebuilt from completed matches.
    initial_elo_rating: Mapped[int] = mapped_column(Integer, default=DEFAULT_ELO_RATING, nullable=False)
    elo_rating: Mapped[int] = mapped_column(Integer, default=DEFAULT_ELO_RATING, nullable=False)
    # Marks the single tombstone player that a deleted player's matches are
    # reassigned to, so match history survives the deletion. Excluded from
    # player listings, standings, and every admin picker.
    is_placeholder: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa_false(), nullable=False
    )
    is_site_creator: Mapped[bool] = mapped_column(
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
