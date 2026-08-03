"""model playoff rounds explicitly

Turns the playoff bracket's structure into data. Each conceptual round becomes a
row in `playoff_rounds` carrying its own label and display position, and every
playoff match points at one. Nothing derives a round's position from its name,
from the alphabet, or from when its matches happen to have been played.

The existing per-match `round_label`/`round_order` columns are deliberately
kept. They are marked legacy, are no longer read by the application, and exist
so that rolling this release back renders the same bracket it did before. A
later, separately reviewed migration removes them.

The data step is explicit and self-checking. It refuses to guess: a season whose
rounds cannot be ordered from data already in the database, or from the reviewed
mapping below, aborts the whole migration with the season, the labels and the
matches that a human needs to look at. PostgreSQL runs a migration in one
transaction, so an abort leaves the schema and the data exactly as they were.

Revision ID: e4a7c2b8d5f1
Revises: f3d9e2a4c711
Create Date: 2026-08-03 11:20:44.913277

"""
from collections import defaultdict
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

import app


# revision identifiers, used by Alembic.
revision: str = "e4a7c2b8d5f1"
down_revision: Union[str, None] = "f3d9e2a4c711"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --------------------------------------------------------------------------
# Reviewed mapping for legacy data
# --------------------------------------------------------------------------
# This is NOT a general table of round names, and no code outside this one
# migration consults it. It is the record of a human reading the production
# database - the labels actually stored, who played whom, who won, and which
# round those winners turn up in next - and writing the answer down.
#
# Season 2 (the only season in production carrying playoff matches at the time
# this was written) stores no round_order and no bracket_order at all. Its order
# is established by advancement, not by the labels:
#
#   Steve vs Doodle            -> Doodle wins  -> plays Renk in the next round
#   AEL (Cheeburbur) vs Matts  -> AEL wins     -> plays Seb Ball in the next round
#   Renk vs Doodle             -> Doodle wins  -> plays in the last round
#   Seb Ball vs AEL            -> AEL wins     -> plays in the last round
#   AEL vs Doodle              -> the last round
#
# so "First Round" precedes "Semifinal" precedes "Final" as a fact about the
# matches, independent of what the rounds are called.
#
# Keyed by season name so a mapping reviewed for one season is never silently
# applied to another season that happens to reuse a label.
REVIEWED_ROUND_ORDER: dict[tuple[str, str], int] = {
    ("Season 2", "First Round"): 1,
    ("Season 2", "Semifinal"): 2,
    ("Season 2", "Final"): 3,
}

# Bracket positions within a round, keyed on the participants rather than on row
# ids. A match is only placed if the row really does hold the pairing that was
# reviewed, so a database that differs from the one audited aborts instead of
# being reordered on a stale assumption. Position is the index in the list + 1;
# a gap is a bye.
REVIEWED_BRACKET_POSITIONS: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("Season 2", "First Round"): [("Steve", "Doodle"), ("AEL (Cheeburbur)", "Matts")],
    ("Season 2", "Semifinal"): [("Renk", "Doodle"), ("Seb Ball", "AEL (Cheeburbur)")],
    ("Season 2", "Final"): [("AEL (Cheeburbur)", "Doodle")],
}

# What the previous release rendered for a playoff match with no label at all
# (`match.round_label or "Playoffs"`). Reusing it keeps such a season looking
# exactly as it did, rather than inventing a name for it.
_UNLABELLED_ROUND = "Playoffs"

_BRACKET_ORDER_CHECK = "ck_matches_bracket_order_positive"
_SLOT_INDEX = "uq_matches_playoff_round_bracket_order"
_SLOT_PREDICATE = "playoff_round_id IS NOT NULL AND bracket_order IS NOT NULL"


class AmbiguousLegacyData(Exception):
    """Raised when existing data cannot be converted without a human decision.

    Aborting the migration is the point: the alternative is a bracket that is
    quietly in the wrong order in production.
    """


def _fail(message: str) -> None:
    raise AmbiguousLegacyData(
        f"{message}\n\n"
        "This migration will not guess a playoff round order. Decide the intended "
        "order for the season above, add it to REVIEWED_ROUND_ORDER / "
        "REVIEWED_BRACKET_POSITIONS in this revision, and run the migration again. "
        "Nothing has been changed."
    )


def _resolve_display_order(season_name: str, label: str, rows: list) -> int:
    """Where a round belongs, from data - never from its name."""
    stored = {row.round_order for row in rows}
    if len(stored) == 1 and None not in stored:
        # Every match in the round already agrees on a position; trust it.
        # This is the path a development database seeded with round_order takes.
        order = stored.pop()
        if order <= 0:
            _fail(
                f"Season {season_name!r} round {label!r} has a stored round_order of {order}, "
                "which is not a valid position."
            )
        return order

    reviewed = REVIEWED_ROUND_ORDER.get((season_name, label))
    if reviewed is not None:
        return reviewed

    _fail(
        f"Season {season_name!r} round {label!r} ({len(rows)} match(es)) cannot be ordered: "
        f"stored round_order values are {sorted(o for o in stored if o is not None) or 'absent'}"
        f"{' and disagree' if len([o for o in stored if o is not None]) > 1 else ''}, "
        "and there is no reviewed mapping for it.\n"
        "Matches: "
        + "; ".join(f"{row.home_username} vs {row.away_username}" for row in rows)
    )
    raise AssertionError("unreachable")


def _resolve_bracket_positions(season_name: str, label: str, rows: list) -> dict[uuid.UUID, int]:
    """Each match's slot within its round, from stored values or the reviewed
    pairing list. Positions must be distinct; a clash is a human decision."""
    reviewed = REVIEWED_BRACKET_POSITIONS.get((season_name, label), [])
    pairing_position = {pair: index + 1 for index, pair in enumerate(reviewed)}

    positions: dict[uuid.UUID, int] = {}
    for row in rows:
        if row.bracket_order is not None:
            if row.bracket_order <= 0:
                _fail(
                    f"Season {season_name!r} round {label!r}: "
                    f"{row.home_username} vs {row.away_username} has bracket_order "
                    f"{row.bracket_order}, which is not a valid position."
                )
            positions[row.id] = row.bracket_order
            continue
        position = pairing_position.get((row.home_username, row.away_username))
        if position is None:
            _fail(
                f"Season {season_name!r} round {label!r}: "
                f"{row.home_username} vs {row.away_username} has no bracket position and no "
                "reviewed entry for that pairing."
            )
        positions[row.id] = position

    taken: dict[int, str] = {}
    for row in rows:
        position = positions[row.id]
        clash = taken.get(position)
        description = f"{row.home_username} vs {row.away_username}"
        if clash is not None:
            _fail(
                f"Season {season_name!r} round {label!r}: position {position} is claimed by both "
                f"{clash} and {description}."
            )
        taken[position] = description
    return positions


def _migrate_legacy_rounds(connection) -> None:
    rows = connection.execute(
        sa.text(
            """
            SELECT m.id, m.season_id, m.round_label, m.round_order, m.bracket_order,
                   s.name AS season_name,
                   hp.username AS home_username,
                   ap.username AS away_username
            FROM matches m
            JOIN seasons s ON s.id = m.season_id
            JOIN players hp ON hp.id = m.home_player_id
            JOIN players ap ON ap.id = m.away_player_id
            WHERE m.stage = 'playoffs'
            """
        )
    ).all()
    if not rows:
        return

    by_season: dict[uuid.UUID, list] = defaultdict(list)
    for row in rows:
        by_season[row.season_id].append(row)

    for season_id, season_rows in by_season.items():
        season_name = season_rows[0].season_name
        labels = {row.round_label for row in season_rows}

        if labels == {None}:
            # A season whose playoff matches were never labelled rendered as one
            # column called "Playoffs". Preserve that exactly.
            grouped: dict[str, list] = {_UNLABELLED_ROUND: season_rows}
        elif None in labels:
            unlabelled = [r for r in season_rows if r.round_label is None]
            _fail(
                f"Season {season_name!r} has playoff matches both with and without a round label, "
                f"so its rounds cannot be grouped. Unlabelled: "
                + "; ".join(f"{r.home_username} vs {r.away_username}" for r in unlabelled)
            )
            raise AssertionError("unreachable")
        else:
            grouped = defaultdict(list)
            for row in season_rows:
                grouped[row.round_label].append(row)

        resolved = {
            label: _resolve_display_order(season_name, label, label_rows)
            for label, label_rows in grouped.items()
        }

        clashes = defaultdict(list)
        for label, order in resolved.items():
            clashes[order].append(label)
        for order, sharing in clashes.items():
            if len(sharing) > 1:
                _fail(
                    f"Season {season_name!r} places {' and '.join(repr(s) for s in sorted(sharing))} "
                    f"at the same position ({order}). Two rounds cannot share a position."
                )

        # Store contiguous 1..N in the resolved order, so the reorder endpoint
        # starts from a clean sequence. Relative order is exactly as resolved.
        ordered_labels = sorted(resolved, key=lambda label: resolved[label])
        for display_order, label in enumerate(ordered_labels, start=1):
            round_id = uuid.uuid4()
            connection.execute(
                sa.text(
                    "INSERT INTO playoff_rounds (id, season_id, label, display_order) "
                    "VALUES (:id, :season_id, :label, :display_order)"
                ),
                {
                    "id": str(round_id),
                    "season_id": str(season_id),
                    "label": label,
                    "display_order": display_order,
                },
            )

            label_rows = grouped[label]
            positions = _resolve_bracket_positions(season_name, label, label_rows)
            for row in label_rows:
                connection.execute(
                    sa.text(
                        "UPDATE matches SET playoff_round_id = :round_id, "
                        "bracket_order = :bracket_order, "
                        # The legacy columns are written, not read: they are what
                        # a rollback to the previous release would sort on.
                        "round_label = :label, round_order = :display_order "
                        "WHERE id = :match_id"
                    ),
                    {
                        "round_id": str(round_id),
                        "bracket_order": positions[row.id],
                        "label": label,
                        "display_order": display_order,
                        "match_id": str(row.id),
                    },
                )

    _verify(connection, expected_playoff_matches=len(rows))


def _verify(connection, expected_playoff_matches: int) -> None:
    """Prove the conversion before letting the transaction commit."""
    orphaned = connection.execute(
        sa.text("SELECT COUNT(*) FROM matches WHERE stage = 'playoffs' AND playoff_round_id IS NULL")
    ).scalar_one()
    if orphaned:
        _fail(f"{orphaned} playoff match(es) were left without a round.")

    strays = connection.execute(
        sa.text("SELECT COUNT(*) FROM matches WHERE stage <> 'playoffs' AND playoff_round_id IS NOT NULL")
    ).scalar_one()
    if strays:
        _fail(f"{strays} non-playoff match(es) ended up referencing a playoff round.")

    total = connection.execute(
        sa.text("SELECT COUNT(*) FROM matches WHERE stage = 'playoffs'")
    ).scalar_one()
    if total != expected_playoff_matches:
        _fail(f"playoff match count changed during the migration ({expected_playoff_matches} -> {total}).")

    duplicate_slots = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM (SELECT playoff_round_id, bracket_order FROM matches "
            "WHERE playoff_round_id IS NOT NULL AND bracket_order IS NOT NULL "
            "GROUP BY playoff_round_id, bracket_order HAVING COUNT(*) > 1) AS d"
        )
    ).scalar_one()
    if duplicate_slots:
        _fail(f"{duplicate_slots} bracket position(s) ended up used twice within one round.")

    cross_season = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM matches m JOIN playoff_rounds r ON r.id = m.playoff_round_id "
            "WHERE r.season_id <> m.season_id"
        )
    ).scalar_one()
    if cross_season:
        _fail(f"{cross_season} match(es) ended up in a round belonging to another season.")


def upgrade() -> None:
    op.create_table(
        "playoff_rounds",
        sa.Column("id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("season_id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("display_order > 0", name="ck_playoff_rounds_display_order_positive"),
        sa.CheckConstraint("length(trim(label)) > 0", name="ck_playoff_rounds_label_not_empty"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("season_id", "display_order", name="uq_playoff_rounds_season_display_order"),
    )
    op.create_index(op.f("ix_playoff_rounds_season_id"), "playoff_rounds", ["season_id"], unique=False)

    op.add_column("matches", sa.Column("playoff_round_id", app.utils.db_types.GUID(), nullable=True))
    op.create_index(op.f("ix_matches_playoff_round_id"), "matches", ["playoff_round_id"], unique=False)
    # No ON DELETE action: deleting a round that still holds matches must fail
    # (the API refuses it with a readable message), while deleting a *season*
    # still works, because its matches and its rounds both go in the same
    # statement and the default NO ACTION is checked once that statement ends.
    op.create_foreign_key(
        "fk_matches_playoff_round_id_playoff_rounds", "matches", "playoff_rounds", ["playoff_round_id"], ["id"]
    )

    connection = op.get_bind()
    _migrate_legacy_rounds(connection)

    # Added after the data step so the checks above report a legible problem
    # rather than the database rejecting a write mid-conversion. They are the
    # standing guarantee from here on.
    op.create_index(
        _SLOT_INDEX,
        "matches",
        ["playoff_round_id", "bracket_order"],
        unique=True,
        postgresql_where=sa.text(_SLOT_PREDICATE),
        sqlite_where=sa.text(_SLOT_PREDICATE),
    )
    op.create_check_constraint(
        _BRACKET_ORDER_CHECK, "matches", "bracket_order IS NULL OR bracket_order > 0"
    )


def downgrade() -> None:
    # The legacy round_label/round_order columns were kept in step throughout,
    # so the previous release's bracket ordering still works after this runs.
    op.drop_constraint(_BRACKET_ORDER_CHECK, "matches", type_="check")
    op.drop_index(_SLOT_INDEX, table_name="matches")
    op.drop_constraint("fk_matches_playoff_round_id_playoff_rounds", "matches", type_="foreignkey")
    op.drop_index(op.f("ix_matches_playoff_round_id"), table_name="matches")
    op.drop_column("matches", "playoff_round_id")
    op.drop_index(op.f("ix_playoff_rounds_season_id"), table_name="playoff_rounds")
    op.drop_table("playoff_rounds")
