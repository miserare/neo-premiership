from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# The row id of the one and only settings row.
SITE_LINKS_ID = 1


class SiteLinks(Base):
    """Admin overrides for the three links on the home page.

    Every field is optional. A null override means "keep deriving it" - the
    stream falls back to the most recent match with a video, the document to
    the current season's sheet, and the table to that season's own page. So an
    admin only has to touch the ones they want to pin.

    Single-row table: the CHECK makes that a constraint rather than a
    convention nothing enforces.
    """

    __tablename__ = "site_links"
    __table_args__ = (CheckConstraint("id = 1", name="ck_site_links_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SITE_LINKS_ID)

    stream_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    stream_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    document_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    table_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    table_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    def __repr__(self) -> str:
        return f"<SiteLinks id={self.id}>"
