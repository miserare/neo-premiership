"""model series formats and Pokémon scores per individual game

Revision ID: 7d2e9c4a1b6f
Revises: b8e1d3a67c25

The legacy league mapping is explicit and guarded: group fixtures were BO1
and playoff fixtures were BO3. Completed group rows stored the one game's
remaining-Pokémon score on the parent. Playoff game scores were never stored
and remain NULL; they are not fabricated.
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app


revision: str = "7d2e9c4a1b6f"
down_revision: Union[str, None] = "b8e1d3a67c25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# League-approved correction supplied for the one ambiguous production row.
_AEL_RENK_MATCH_ID = uuid.UUID("c2dece82-561d-4664-be58-fa94c4d96e2a")


def _apply_reviewed_corrections(connection: sa.Connection) -> None:
    """Remove only the reviewed unused G3 from AEL's 2–0 win over Renk.

    The guards are deliberately exhaustive. If the production row no longer
    has the audited shape, the migration stops instead of deleting anything.
    Databases without this historical match (new installs and tests) are a
    no-op.
    """
    match = connection.execute(
        sa.text(
            """
            SELECT m.id, m.status, m.stage, m.home_player_id, m.away_player_id,
                   m.winner_id, hp.username AS home_username,
                   ap.username AS away_username
            FROM matches m
            JOIN players hp ON hp.id = m.home_player_id
            JOIN players ap ON ap.id = m.away_player_id
            WHERE m.id = :match_id
            """
        ),
        {"match_id": _AEL_RENK_MATCH_ID},
    ).mappings().one_or_none()
    if match is None:
        return

    games = connection.execute(
        sa.text(
            "SELECT id, game_number, winner_id FROM match_games "
            "WHERE match_id=:match_id ORDER BY game_number, id"
        ),
        {"match_id": _AEL_RENK_MATCH_ID},
    ).mappings().all()
    expected_shape = (
        match["status"] == "completed"
        and match["stage"] == "playoffs"
        and match["home_username"] == "AEL (Cheeburbur)"
        and match["away_username"] == "Renk"
        and match["winner_id"] == match["home_player_id"]
        and len(games) == 3
        and [game["game_number"] for game in games] == [1, 2, 3]
        and games[0]["winner_id"] == match["home_player_id"]
        and games[1]["winner_id"] == match["home_player_id"]
        and games[2]["winner_id"] is None
    )
    if not expected_shape:
        raise RuntimeError(
            "The reviewed AEL vs Renk correction no longer matches production. "
            f"Refusing to alter match {_AEL_RENK_MATCH_ID}."
        )
    connection.execute(
        sa.text("DELETE FROM match_games WHERE id=:game_id"),
        {"game_id": games[2]["id"]},
    )


def _expected_score(player_rating: int, opponent_rating: int) -> float:
    difference = (opponent_rating - player_rating) / 400
    if difference >= 0:
        inverse_ratio = 10 ** (-difference)
        return inverse_ratio / (1 + inverse_ratio)
    ratio = 10**difference
    return 1 / (1 + ratio)


def _round_change(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _preflight(connection: sa.Connection) -> None:
    invalid_group = connection.execute(
        sa.text(
            """
            SELECT id, home_score, away_score, winner_id, home_player_id, away_player_id
            FROM matches
            WHERE status = 'completed' AND stage = 'group'
              AND NOT COALESCE((
                (home_score BETWEEN 1 AND 6 AND away_score = 0 AND winner_id = home_player_id)
                OR
                (away_score BETWEEN 1 AND 6 AND home_score = 0 AND winner_id = away_player_id)
              ), false)
            ORDER BY id
            """
        )
    ).mappings().all()
    if invalid_group:
        ids = ", ".join(str(row["id"]) for row in invalid_group)
        raise RuntimeError(
            "Cannot migrate completed legacy group fixtures with an unknown or invalid "
            f"Pokémon score. Supply league-approved data for match IDs: {ids}"
        )

    invalid_group_games = connection.execute(
        sa.text(
            """
            SELECT m.id
            FROM matches m
            JOIN match_games g ON g.match_id = m.id
            WHERE m.status = 'completed' AND m.stage = 'group'
            GROUP BY m.id, m.winner_id
            HAVING count(*) <> 1 OR min(g.game_number) <> 1 OR max(g.game_number) <> 1
               OR bool_or(g.winner_id IS DISTINCT FROM m.winner_id)
            ORDER BY m.id
            """
        )
    ).scalars().all()
    if invalid_group_games:
        ids = ", ".join(str(match_id) for match_id in invalid_group_games)
        raise RuntimeError(
            "Cannot reconcile existing BO1 game rows with their completed group fixtures. "
            f"Supply the authoritative game mapping for match IDs: {ids}"
        )

    # Every completed playoff game must have a winner and the ledger must be a
    # contiguous, clinch-valid BO3. Unknown Pokémon scores are allowed; unknown
    # game outcomes or post-clinch games are not something a migration may fix.
    playoff_matches = connection.execute(
        sa.text(
            """
            SELECT id, home_player_id, away_player_id, winner_id
            FROM matches
            WHERE status = 'completed' AND stage = 'playoffs'
            ORDER BY id
            """
        )
    ).mappings().all()
    for match in playoff_matches:
        games = connection.execute(
            sa.text(
                "SELECT id, game_number, winner_id FROM match_games "
                "WHERE match_id = :match_id ORDER BY game_number, id"
            ),
            {"match_id": match["id"]},
        ).mappings().all()
        numbers = [game["game_number"] for game in games]
        if numbers != list(range(1, len(games) + 1)) or not games:
            raise RuntimeError(
                f"Cannot establish a contiguous playoff series for match {match['id']}; "
                "supply its authoritative game mapping."
            )
        home_wins = 0
        away_wins = 0
        for index, game in enumerate(games):
            if game["winner_id"] == match["home_player_id"]:
                home_wins += 1
            elif game["winner_id"] == match["away_player_id"]:
                away_wins += 1
            else:
                raise RuntimeError(
                    f"Cannot migrate match {match['id']} game {game['id']}: winner is missing "
                    "or is not a participant. Supply the authoritative outcome."
                )
            if max(home_wins, away_wins) == 2 and index != len(games) - 1:
                raise RuntimeError(
                    f"Cannot migrate match {match['id']}: game {games[index + 1]['id']} appears "
                    "after the BO3 series was clinched. Supply the authoritative format/outcome."
                )
        derived = (
            match["home_player_id"] if home_wins == 2 else match["away_player_id"] if away_wins == 2 else None
        )
        if derived is None or derived != match["winner_id"]:
            raise RuntimeError(
                f"Cannot derive the recorded winner for playoff match {match['id']}; "
                "supply the authoritative series mapping."
            )


def _rebuild_elo(connection: sa.Connection) -> None:
    connection.execute(sa.text("DELETE FROM elo_rating_events"))
    players = connection.execute(
        sa.text("SELECT id, initial_elo_rating FROM players ORDER BY id")
    ).mappings().all()
    ratings = {row["id"]: row["initial_elo_rating"] for row in players}

    games = connection.execute(
        sa.text(
            """
            SELECT g.id AS match_game_id, g.match_id, g.game_number, g.winner_id,
                   COALESCE(g.completed_at, m.completed_at) AS occurred_at,
                   m.home_player_id, m.away_player_id
            FROM match_games g
            JOIN matches m ON m.id = g.match_id
            WHERE m.status = 'completed' AND g.winner_id IS NOT NULL
              AND COALESCE(g.completed_at, m.completed_at) IS NOT NULL
            ORDER BY COALESCE(g.completed_at, m.completed_at), m.id, g.game_number, g.id
            """
        )
    ).mappings().all()

    events: list[dict] = []
    for game in games:
        home_id = game["home_player_id"]
        away_id = game["away_player_id"]
        if home_id not in ratings or away_id not in ratings:
            continue
        home_before = ratings[home_id]
        away_before = ratings[away_id]
        home_expected = _expected_score(home_before, away_before)
        home_result = 1 if game["winner_id"] == home_id else 0
        home_change = (
            _round_change(64 * (1 - home_expected))
            if home_result
            else -_round_change(64 * home_expected)
        )
        away_change = -home_change
        home_after = home_before + home_change
        away_after = away_before + away_change
        ratings[home_id] = home_after
        ratings[away_id] = away_after
        common = {
            "match_id": game["match_id"],
            "match_game_id": game["match_game_id"],
            "occurred_at": game["occurred_at"],
        }
        events.extend(
            [
                {
                    "id": uuid.uuid4(), "player_id": home_id, "opponent_id": away_id,
                    "rating_before": home_before, "rating_after": home_after,
                    "rating_change": home_change, "result": home_result,
                    "expected_score": Decimal(f"{home_expected:.7f}"), **common,
                },
                {
                    "id": uuid.uuid4(), "player_id": away_id, "opponent_id": home_id,
                    "rating_before": away_before, "rating_after": away_after,
                    "rating_change": away_change, "result": 1 - home_result,
                    "expected_score": Decimal(f"{1 - home_expected:.7f}"), **common,
                },
            ]
        )
    if events:
        table = sa.table(
            "elo_rating_events",
            sa.column("id", app.utils.db_types.GUID()),
            sa.column("match_id", app.utils.db_types.GUID()),
            sa.column("match_game_id", app.utils.db_types.GUID()),
            sa.column("player_id", app.utils.db_types.GUID()),
            sa.column("opponent_id", app.utils.db_types.GUID()),
            sa.column("occurred_at", sa.DateTime(timezone=True)),
            sa.column("rating_before", sa.Integer()),
            sa.column("rating_after", sa.Integer()),
            sa.column("rating_change", sa.Integer()),
            sa.column("result", sa.Integer()),
            sa.column("expected_score", sa.Numeric(8, 7)),
        )
        connection.execute(table.insert(), events)
    for player_id, rating in ratings.items():
        connection.execute(
            sa.text("UPDATE players SET elo_rating = :rating WHERE id = :player_id"),
            {"rating": rating, "player_id": player_id},
        )


def upgrade() -> None:
    connection = op.get_bind()
    _apply_reviewed_corrections(connection)
    _preflight(connection)

    op.add_column("matches", sa.Column("best_of", sa.Integer(), server_default="1", nullable=False))
    op.create_check_constraint("ck_matches_supported_best_of", "matches", "best_of IN (1, 3, 5, 7, 9)")
    op.execute("UPDATE matches SET best_of = CASE WHEN stage = 'playoffs' THEN 3 ELSE 1 END")

    op.add_column("match_games", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("match_games", sa.Column("home_pokemon_score", sa.Integer(), nullable=True))
    op.add_column("match_games", sa.Column("away_pokemon_score", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_match_games_completed_at"), "match_games", ["completed_at"], unique=False)

    # Ensure every legacy BO1 has its one real game row, then copy only the
    # score whose audited meaning is unambiguous.
    existing_group_ids = {
        row[0]
        for row in connection.execute(
            sa.text(
                "SELECT DISTINCT g.match_id FROM match_games g JOIN matches m ON m.id=g.match_id "
                "WHERE m.status='completed' AND m.stage='group'"
            )
        ).all()
    }
    groups = connection.execute(
        sa.text(
            "SELECT id, winner_id, completed_at, home_score, away_score, replay_url "
            "FROM matches WHERE status='completed' AND stage='group' ORDER BY id"
        )
    ).mappings().all()
    game_table = sa.table(
        "match_games",
        sa.column("id", app.utils.db_types.GUID()),
        sa.column("match_id", app.utils.db_types.GUID()),
        sa.column("game_number", sa.Integer()),
        sa.column("winner_id", app.utils.db_types.GUID()),
        sa.column("replay_url", sa.String(512)),
        sa.column("completed_at", sa.DateTime(timezone=True)),
        sa.column("home_pokemon_score", sa.Integer()),
        sa.column("away_pokemon_score", sa.Integer()),
    )
    for match in groups:
        if match["id"] in existing_group_ids:
            connection.execute(
                sa.text(
                    "UPDATE match_games SET completed_at=:completed_at, "
                    "home_pokemon_score=:home_score, away_pokemon_score=:away_score "
                    "WHERE match_id=:match_id AND game_number=1"
                ),
                {**match, "match_id": match["id"]},
            )
        else:
            connection.execute(
                game_table.insert(),
                {
                    "id": uuid.uuid4(), "match_id": match["id"], "game_number": 1,
                    "winner_id": match["winner_id"], "replay_url": match["replay_url"],
                    "completed_at": match["completed_at"],
                    "home_pokemon_score": match["home_score"],
                    "away_pokemon_score": match["away_score"],
                },
            )
    op.execute(
        "UPDATE match_games g SET completed_at=m.completed_at FROM matches m "
        "WHERE g.match_id=m.id AND g.completed_at IS NULL"
    )
    op.create_check_constraint("ck_match_games_number_positive", "match_games", "game_number > 0")
    op.create_check_constraint(
        "ck_match_games_valid_pokemon_score",
        "match_games",
        "(home_pokemon_score IS NULL AND away_pokemon_score IS NULL) OR "
        "(home_pokemon_score BETWEEN 1 AND 6 AND away_pokemon_score = 0) OR "
        "(away_pokemon_score BETWEEN 1 AND 6 AND home_pokemon_score = 0)",
    )

    op.add_column(
        "players", sa.Column("is_site_creator", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.create_check_constraint(
        "ck_players_placeholder_not_site_creator", "players", "NOT (is_placeholder AND is_site_creator)"
    )
    op.create_index(
        "uq_players_single_site_creator",
        "players",
        ["is_site_creator"],
        unique=True,
        postgresql_where=sa.text("is_site_creator"),
        sqlite_where=sa.text("is_site_creator = 1"),
    )
    candidates = connection.execute(
        sa.text(
            "SELECT id FROM players WHERE username='Spectre (Nizhinsky)' AND is_placeholder=false"
        )
    ).scalars().all()
    if len(candidates) > 1:
        raise RuntimeError("Spectre (Nizhinsky) is ambiguous; supply the correct player ID")
    if len(candidates) == 1:
        connection.execute(
            sa.text("UPDATE players SET is_site_creator=true WHERE id=:player_id"),
            {"player_id": candidates[0]},
        )

    op.drop_constraint("uq_elo_rating_events_match_player", "elo_rating_events", type_="unique")
    op.add_column(
        "elo_rating_events",
        sa.Column("match_game_id", app.utils.db_types.GUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_elo_rating_events_match_game_id", "elo_rating_events", "match_games",
        ["match_game_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(
        op.f("ix_elo_rating_events_match_game_id"), "elo_rating_events", ["match_game_id"], unique=False
    )
    _rebuild_elo(connection)
    op.alter_column("elo_rating_events", "match_game_id", nullable=False)
    op.create_unique_constraint(
        "uq_elo_rating_events_game_player", "elo_rating_events", ["match_game_id", "player_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_elo_rating_events_game_player", "elo_rating_events", type_="unique")
    # A multi-game series has more than one event per player, so those rows
    # cannot satisfy the legacy per-match uniqueness constraint. Elo is derived
    # data: discard the new ledger and reset its cache rather than leaving a
    # downgrade that can fail or silently retain only an arbitrary game.
    op.execute("DELETE FROM elo_rating_events")
    op.execute("UPDATE players SET elo_rating=initial_elo_rating")
    op.drop_index(op.f("ix_elo_rating_events_match_game_id"), table_name="elo_rating_events")
    op.drop_constraint("fk_elo_rating_events_match_game_id", "elo_rating_events", type_="foreignkey")
    op.drop_column("elo_rating_events", "match_game_id")
    op.create_unique_constraint(
        "uq_elo_rating_events_match_player", "elo_rating_events", ["match_id", "player_id"]
    )
    op.drop_index("uq_players_single_site_creator", table_name="players")
    op.drop_constraint("ck_players_placeholder_not_site_creator", "players", type_="check")
    op.drop_column("players", "is_site_creator")
    op.drop_constraint("ck_match_games_valid_pokemon_score", "match_games", type_="check")
    op.drop_constraint("ck_match_games_number_positive", "match_games", type_="check")
    op.drop_index(op.f("ix_match_games_completed_at"), table_name="match_games")
    op.drop_column("match_games", "away_pokemon_score")
    op.drop_column("match_games", "home_pokemon_score")
    op.drop_column("match_games", "completed_at")
    op.drop_constraint("ck_matches_supported_best_of", "matches", type_="check")
    op.drop_column("matches", "best_of")
