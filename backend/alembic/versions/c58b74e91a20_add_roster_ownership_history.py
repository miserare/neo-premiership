"""add dated roster ownership history

Revision ID: c58b74e91a20
Revises: b7d3e51a2c94
Create Date: 2026-07-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c58b74e91a20"
down_revision: Union[str, None] = "b7d3e51a2c94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "season_roster_pokemon",
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "season_roster_pokemon",
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "season_roster_pokemon",
        sa.Column(
            "acquisition_type",
            sa.String(length=16),
            server_default="draft",
            nullable=False,
        ),
    )
    op.add_column(
        "season_roster_pokemon",
        sa.Column("release_type", sa.String(length=16), nullable=True),
    )

    # Historical tenures legitimately reuse a display slot. Only current
    # ownership must be unique, which is enforced by the active-species index.
    op.drop_constraint(
        "uq_season_roster_pokemon_entry_slot",
        "season_roster_pokemon",
        type_="unique",
    )
    op.create_check_constraint(
        "ck_season_roster_pokemon_release_complete",
        "season_roster_pokemon",
        "(released_at IS NULL AND release_type IS NULL) OR "
        "(released_at IS NOT NULL AND release_type IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_season_roster_pokemon_tenure_order",
        "season_roster_pokemon",
        "released_at IS NULL OR acquired_at IS NULL OR released_at >= acquired_at",
    )
    op.create_index(
        "uq_season_roster_pokemon_active_species",
        "season_roster_pokemon",
        ["season_entry_id", "pokeapi_id"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_season_roster_pokemon_active_species",
        table_name="season_roster_pokemon",
    )
    op.drop_constraint(
        "ck_season_roster_pokemon_tenure_order",
        "season_roster_pokemon",
        type_="check",
    )
    op.drop_constraint(
        "ck_season_roster_pokemon_release_complete",
        "season_roster_pokemon",
        type_="check",
    )

    # The old schema cannot represent multiple tenures for one slot. Keep the
    # current state and discard released history when explicitly downgrading.
    op.execute("DELETE FROM season_roster_pokemon WHERE released_at IS NOT NULL")
    op.create_unique_constraint(
        "uq_season_roster_pokemon_entry_slot",
        "season_roster_pokemon",
        ["season_entry_id", "slot"],
    )
    op.drop_column("season_roster_pokemon", "release_type")
    op.drop_column("season_roster_pokemon", "acquisition_type")
    op.drop_column("season_roster_pokemon", "released_at")
    op.drop_column("season_roster_pokemon", "acquired_at")
