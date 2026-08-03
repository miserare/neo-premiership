"""add chronological Elo rating history

Revision ID: f3d9e2a4c711
Revises: d92a4f6b1c07
Create Date: 2026-07-31 18:00:00.000000

Existing current ratings become each player's starting rating. Completed
matches that have a winner and completion timestamp are then replayed in
chronological order to establish the first derived current ratings and ledger.
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app


revision: str = "f3d9e2a4c711"
down_revision: Union[str, None] = "d92a4f6b1c07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _expected_score(player_rating: int, opponent_rating: int) -> float:
    difference = (opponent_rating - player_rating) / 400
    if difference >= 0:
        inverse_ratio = 10 ** (-difference)
        return inverse_ratio / (1 + inverse_ratio)
    ratio = 10**difference
    return 1 / (1 + ratio)


def _round_change(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("initial_elo_rating", sa.Integer(), server_default="1000", nullable=False),
    )
    op.execute("UPDATE players SET initial_elo_rating = elo_rating")

    op.create_table(
        "elo_rating_events",
        sa.Column("id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("match_id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("player_id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("opponent_id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rating_before", sa.Integer(), nullable=False),
        sa.Column("rating_after", sa.Integer(), nullable=False),
        sa.Column("rating_change", sa.Integer(), nullable=False),
        sa.Column("result", sa.Integer(), nullable=False),
        sa.Column("expected_score", sa.Numeric(precision=8, scale=7), nullable=False),
        sa.CheckConstraint("result IN (0, 1)", name="ck_elo_rating_events_binary_result"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opponent_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "player_id", name="uq_elo_rating_events_match_player"),
    )
    op.create_index(
        op.f("ix_elo_rating_events_match_id"), "elo_rating_events", ["match_id"], unique=False
    )
    op.create_index(
        op.f("ix_elo_rating_events_player_id"), "elo_rating_events", ["player_id"], unique=False
    )
    op.create_index(
        op.f("ix_elo_rating_events_occurred_at"),
        "elo_rating_events",
        ["occurred_at"],
        unique=False,
    )

    connection = op.get_bind()
    player_rows = connection.execute(
        sa.text("SELECT id, initial_elo_rating FROM players ORDER BY id")
    ).mappings()
    ratings = {row["id"]: row["initial_elo_rating"] for row in player_rows}
    events: list[dict] = []

    matches = connection.execute(
        sa.text(
            "SELECT id, home_player_id, away_player_id, winner_id, completed_at "
            "FROM matches "
            "WHERE status = 'completed' AND winner_id IS NOT NULL AND completed_at IS NOT NULL "
            "ORDER BY completed_at, id"
        )
    ).mappings()
    for match in matches:
        home_id = match["home_player_id"]
        away_id = match["away_player_id"]
        winner_id = match["winner_id"]
        if home_id not in ratings or away_id not in ratings:
            continue
        if winner_id not in (home_id, away_id):
            continue

        home_before = ratings[home_id]
        away_before = ratings[away_id]
        home_expected = _expected_score(home_before, away_before)
        home_result = 1 if winner_id == home_id else 0
        if home_result:
            home_change = _round_change(64 * (1 - home_expected))
        else:
            home_change = -_round_change(64 * home_expected)
        away_change = -home_change
        home_after = home_before + home_change
        away_after = away_before + away_change
        ratings[home_id] = home_after
        ratings[away_id] = away_after

        common = {"match_id": match["id"], "occurred_at": match["completed_at"]}
        events.extend(
            [
                {
                    "id": uuid.uuid4(),
                    "player_id": home_id,
                    "opponent_id": away_id,
                    "rating_before": home_before,
                    "rating_after": home_after,
                    "rating_change": home_change,
                    "result": home_result,
                    "expected_score": Decimal(f"{home_expected:.7f}"),
                    **common,
                },
                {
                    "id": uuid.uuid4(),
                    "player_id": away_id,
                    "opponent_id": home_id,
                    "rating_before": away_before,
                    "rating_after": away_after,
                    "rating_change": away_change,
                    "result": 1 - home_result,
                    "expected_score": Decimal(f"{1 - home_expected:.7f}"),
                    **common,
                },
            ]
        )

    if events:
        event_table = sa.table(
            "elo_rating_events",
            sa.column("id", app.utils.db_types.GUID()),
            sa.column("match_id", app.utils.db_types.GUID()),
            sa.column("player_id", app.utils.db_types.GUID()),
            sa.column("opponent_id", app.utils.db_types.GUID()),
            sa.column("occurred_at", sa.DateTime(timezone=True)),
            sa.column("rating_before", sa.Integer()),
            sa.column("rating_after", sa.Integer()),
            sa.column("rating_change", sa.Integer()),
            sa.column("result", sa.Integer()),
            sa.column("expected_score", sa.Numeric(8, 7)),
        )
        connection.execute(event_table.insert(), events)

    for player_id, rating in ratings.items():
        connection.execute(
            sa.text("UPDATE players SET elo_rating = :rating WHERE id = :player_id"),
            {"rating": rating, "player_id": player_id},
        )

    # New ORM-created players receive the Python default. The temporary server
    # default exists only so the NOT NULL column can be added safely.
    op.alter_column("players", "initial_elo_rating", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_elo_rating_events_occurred_at"), table_name="elo_rating_events")
    op.drop_index(op.f("ix_elo_rating_events_player_id"), table_name="elo_rating_events")
    op.drop_index(op.f("ix_elo_rating_events_match_id"), table_name="elo_rating_events")
    op.drop_table("elo_rating_events")
    op.drop_column("players", "initial_elo_rating")
