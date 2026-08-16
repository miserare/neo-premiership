"""add canonical slugs, player biography, hall of fame text and homepage features

Revision ID: b8e1d3a67c25
Revises: e4a7c2b8d5f1
Create Date: 2026-08-15 09:40:00.000000

Adds the persistent fields behind canonical URLs (`players.slug`,
`seasons.slug`), the player biography, the Hall of Fame's per-season prose and
explicit homepage highlighting on matches.

Slugs are backfilled here rather than left to the application, because the
column is NOT NULL and UNIQUE from the moment this revision completes. The slug
rules are **copied into this file rather than imported from app.utils.slugs**:
a migration has to keep producing the same result for the rest of the project's
life, and it must not silently change because a helper it imports was later
tuned.
"""

import re
import unicodedata
from typing import Callable, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8e1d3a67c25"
down_revision: Union[str, None] = "e4a7c2b8d5f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MAX_SLUG_LENGTH = 64

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")
_SEASON_PREFIX = re.compile(r"^\s*seasons?\b[\s:.-]*", re.IGNORECASE)

# Two league members carry a parenthetical second name, and the slug each should
# get is not derivable from a single rule: one takes the leading name, the other
# takes the parenthetical. They are listed explicitly - inferring a rule from
# two examples would be exactly the presentation heuristic this project keeps
# out of its data. Keys are matched case-insensitively on the whole username.
PLAYER_SLUG_OVERRIDES = {
    "spectre (nizhinsky)": "spectre",
    "ael (cheeburbur)": "cheeburbur",
}


def _slugify(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    hyphenated = _NON_SLUG_CHARS.sub("-", ascii_only.lower()).strip("-")
    return hyphenated[:MAX_SLUG_LENGTH].strip("-")


def _slugify_season_name(name: str) -> str:
    return _slugify(_SEASON_PREFIX.sub("", name, count=1)) or _slugify(name)


def _with_suffix(base: str, suffix: int) -> str:
    """`base-2`, truncated so the result still fits the column."""
    tail = f"-{suffix}"
    return f"{base[: MAX_SLUG_LENGTH - len(tail)].rstrip('-')}{tail}"


def _assign_slugs(
    rows: Sequence[tuple[object, str]],
    derive: Callable[[str], str],
    overrides: dict[str, str],
    fallback_prefix: str,
) -> dict[object, str]:
    """Deterministic slug per row, with collisions resolved explicitly.

    `rows` must already be in a stable order (see the callers): the first row
    to want a slug keeps it, and each later claimant gets `-2`, `-3`, ... so
    re-running this migration on the same data always produces the same
    assignment.

    A name with no ASCII content at all slugifies to "", which cannot be
    stored. Those fall back to `<prefix>-<row id>` - ugly but unique, stable,
    and visible enough that an administrator will want to replace it.
    """
    assigned: dict[object, str] = {}
    taken: set[str] = set()

    # Reserved first, so a different row whose name happens to derive the same
    # slug defers to the override instead of winning on ordering.
    for row_id, name in rows:
        override = overrides.get(name.strip().casefold())
        if override is None:
            continue
        if override in taken:
            raise RuntimeError(
                f"slug override {override!r} is claimed by more than one row; "
                "fix PLAYER_SLUG_OVERRIDES before migrating"
            )
        assigned[row_id] = override
        taken.add(override)

    for row_id, name in rows:
        if row_id in assigned:
            continue
        base = derive(name) or f"{fallback_prefix}-{str(row_id).replace('-', '')[:12]}"
        candidate = base
        suffix = 2
        while candidate in taken:
            candidate = _with_suffix(base, suffix)
            suffix += 1
        assigned[row_id] = candidate
        taken.add(candidate)

    if len(set(assigned.values())) != len(assigned):
        raise RuntimeError("slug backfill produced duplicates; refusing to add the unique index")
    return assigned


def _backfill(connection, table: str, order_by: str, derive, overrides, fallback_prefix) -> None:
    rows = [
        (row["id"], row["name"])
        for row in connection.execute(
            sa.text(f"SELECT id, {'username' if table == 'players' else 'name'} AS name "
                    f"FROM {table} ORDER BY {order_by}")
        ).mappings()
    ]
    for row_id, slug in _assign_slugs(rows, derive, overrides, fallback_prefix).items():
        connection.execute(
            sa.text(f"UPDATE {table} SET slug = :slug WHERE id = :row_id"),
            {"slug": slug, "row_id": row_id},
        )


def upgrade() -> None:
    op.add_column("players", sa.Column("slug", sa.String(length=MAX_SLUG_LENGTH), nullable=True))
    op.add_column("players", sa.Column("biography", sa.Text(), nullable=True))

    op.add_column("seasons", sa.Column("slug", sa.String(length=MAX_SLUG_LENGTH), nullable=True))
    op.add_column("seasons", sa.Column("hall_of_fame_description", sa.Text(), nullable=True))

    op.add_column(
        "matches",
        sa.Column("featured_on_homepage", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("matches", sa.Column("homepage_feature_order", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_matches_featured_on_homepage"), "matches", ["featured_on_homepage"], unique=False
    )
    op.create_check_constraint(
        "ck_matches_homepage_feature_order_positive",
        "matches",
        "homepage_feature_order IS NULL OR homepage_feature_order > 0",
    )

    connection = op.get_bind()
    # join_date/start_date first so the assignment reflects league seniority and
    # does not shuffle if a row is later renamed; id breaks exact ties.
    _backfill(connection, "players", "join_date, id", _slugify, PLAYER_SLUG_OVERRIDES, "player")
    _backfill(connection, "seasons", "start_date, id", _slugify_season_name, {}, "season")

    op.alter_column("players", "slug", existing_type=sa.String(length=MAX_SLUG_LENGTH), nullable=False)
    op.alter_column("seasons", "slug", existing_type=sa.String(length=MAX_SLUG_LENGTH), nullable=False)

    op.create_index(op.f("ix_players_slug"), "players", ["slug"], unique=True)
    op.create_index(op.f("ix_seasons_slug"), "seasons", ["slug"], unique=True)

    # The stored form is always lowercase, which is what makes the plain unique
    # index above equivalent to case-insensitive uniqueness.
    op.create_check_constraint(
        "ck_players_slug_lowercase", "players", "slug = lower(slug) AND length(slug) > 0"
    )
    op.create_check_constraint(
        "ck_seasons_slug_lowercase", "seasons", "slug = lower(slug) AND length(slug) > 0"
    )


def downgrade() -> None:
    """Reverses cleanly, but is not lossless.

    Dropping these columns discards administrator-authored biographies, Hall of
    Fame descriptions and homepage highlighting. Slugs are recomputed on a later
    re-upgrade, so canonical URLs survive a downgrade/upgrade cycle only for
    rows whose names have not changed in between.
    """
    op.drop_constraint("ck_seasons_slug_lowercase", "seasons", type_="check")
    op.drop_constraint("ck_players_slug_lowercase", "players", type_="check")
    op.drop_index(op.f("ix_seasons_slug"), table_name="seasons")
    op.drop_index(op.f("ix_players_slug"), table_name="players")

    op.drop_constraint("ck_matches_homepage_feature_order_positive", "matches", type_="check")
    op.drop_index(op.f("ix_matches_featured_on_homepage"), table_name="matches")
    op.drop_column("matches", "homepage_feature_order")
    op.drop_column("matches", "featured_on_homepage")

    op.drop_column("seasons", "hall_of_fame_description")
    op.drop_column("seasons", "slug")

    op.drop_column("players", "biography")
    op.drop_column("players", "slug")
