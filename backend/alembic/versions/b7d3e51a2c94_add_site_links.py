"""add site_links overrides for the home page

Revision ID: b7d3e51a2c94
Revises: a4f1c9d27b3e
Create Date: 2026-07-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d3e51a2c94'
down_revision: Union[str, None] = 'a4f1c9d27b3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stream_url', sa.String(length=512), nullable=True),
        sa.Column('stream_label', sa.String(length=120), nullable=True),
        sa.Column('document_url', sa.String(length=512), nullable=True),
        sa.Column('document_label', sa.String(length=120), nullable=True),
        sa.Column('table_url', sa.String(length=512), nullable=True),
        sa.Column('table_label', sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        # Single-row table by constraint, not by convention.
        sa.CheckConstraint('id = 1', name='ck_site_links_singleton'),
    )
    # Seed the empty row so a fresh deploy has no first-write race.
    op.execute("INSERT INTO site_links (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table('site_links')
