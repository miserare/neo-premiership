"""add match games, pokemon rosters, and the placeholder player flag

Revision ID: a4f1c9d27b3e
Revises: 009661f2cb3d
Create Date: 2026-07-28 01:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app


# revision identifiers, used by Alembic.
revision: str = 'a4f1c9d27b3e'
down_revision: Union[str, None] = '009661f2cb3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default so the column can be NOT NULL against already-existing rows.
    op.add_column(
        'players',
        sa.Column('is_placeholder', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        'match_games',
        sa.Column('id', app.utils.db_types.GUID(), nullable=False),
        sa.Column('match_id', app.utils.db_types.GUID(), nullable=False),
        sa.Column('game_number', sa.Integer(), nullable=False),
        sa.Column('winner_id', app.utils.db_types.GUID(), nullable=True),
        sa.Column('replay_url', sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['winner_id'], ['players.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_id', 'game_number', name='uq_match_games_match_game'),
    )
    op.create_index(op.f('ix_match_games_match_id'), 'match_games', ['match_id'], unique=False)

    op.create_table(
        'season_roster_pokemon',
        sa.Column('id', app.utils.db_types.GUID(), nullable=False),
        sa.Column('season_entry_id', app.utils.db_types.GUID(), nullable=False),
        sa.Column('pokeapi_id', sa.Integer(), nullable=False),
        sa.Column('species_name', sa.String(length=64), nullable=False),
        sa.Column('slot', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['season_entry_id'], ['season_entries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('season_entry_id', 'slot', name='uq_season_roster_pokemon_entry_slot'),
    )
    op.create_index(
        op.f('ix_season_roster_pokemon_season_entry_id'),
        'season_roster_pokemon',
        ['season_entry_id'],
        unique=False,
    )

    op.create_table(
        'match_pokemon',
        sa.Column('id', app.utils.db_types.GUID(), nullable=False),
        sa.Column('match_id', app.utils.db_types.GUID(), nullable=False),
        sa.Column('player_id', app.utils.db_types.GUID(), nullable=False),
        sa.Column('pokeapi_id', sa.Integer(), nullable=False),
        sa.Column('species_name', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_id', 'player_id', 'pokeapi_id', name='uq_match_pokemon_match_player_species'),
    )
    op.create_index(op.f('ix_match_pokemon_match_id'), 'match_pokemon', ['match_id'], unique=False)
    op.create_index(op.f('ix_match_pokemon_player_id'), 'match_pokemon', ['player_id'], unique=False)

    # Backfill: every match that already has a replay becomes a one-game series,
    # so the new games-based UI shows existing history instead of losing it.
    # matches.replay_url is kept as the legacy single-replay field.
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        new_id = 'gen_random_uuid()'
    else:
        new_id = "lower(hex(randomblob(16)))"
    op.execute(
        f"""
        INSERT INTO match_games (id, match_id, game_number, winner_id, replay_url)
        SELECT {new_id}, id, 1, winner_id, replay_url
        FROM matches
        WHERE replay_url IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_match_pokemon_player_id'), table_name='match_pokemon')
    op.drop_index(op.f('ix_match_pokemon_match_id'), table_name='match_pokemon')
    op.drop_table('match_pokemon')
    op.drop_index(op.f('ix_season_roster_pokemon_season_entry_id'), table_name='season_roster_pokemon')
    op.drop_table('season_roster_pokemon')
    op.drop_index(op.f('ix_match_games_match_id'), table_name='match_games')
    op.drop_table('match_games')
    op.drop_column('players', 'is_placeholder')
