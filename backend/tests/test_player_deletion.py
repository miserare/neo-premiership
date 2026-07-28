"""Deleting a player must preserve their match history by reassigning it to a
placeholder player.

NOTE: SQLite (used here) does not enforce foreign keys unless a per-connection
pragma is set, so these tests cannot catch an ON DELETE CASCADE wiping the
matches. The reassign-commit-then-delete ordering in crud.players.delete_player
is verified against the real Postgres database separately.
"""
from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.players import PLACEHOLDER_USERNAME
from app.models.match import Match, MatchStage, MatchStatus
from app.models.player import Player
from app.models.season import Season
from tests.conftest import ADMIN_HEADERS


async def _season_with_match(db_session: AsyncSession, label: str) -> tuple[Player, Player, Match]:
    season = Season(name=f"Deletion Season {label}", start_date=date(2024, 1, 1))
    leaver = Player(username=f"Leaving{label}")
    stayer = Player(username=f"Staying{label}")
    db_session.add_all([season, leaver, stayer])
    await db_session.flush()

    match = Match(
        season_id=season.id,
        home_player_id=leaver.id,
        away_player_id=stayer.id,
        winner_id=leaver.id,
        stage=MatchStage.GROUP,
        status=MatchStatus.COMPLETED,
    )
    db_session.add(match)
    await db_session.commit()
    return leaver, stayer, match


async def test_delete_player_reassigns_matches_to_placeholder(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    leaver, stayer, match = await _season_with_match(db_session, "A")

    response = await client.delete(f"/api/players/{leaver.id}", headers=ADMIN_HEADERS)
    assert response.status_code == 204

    match_response = await client.get(f"/api/matches/{match.id}")
    assert match_response.status_code == 200, "the match must survive the deletion"
    data = match_response.json()
    assert data["home_player"]["username"] == PLACEHOLDER_USERNAME
    assert data["away_player"]["username"] == stayer.username
    # The result is preserved too - the placeholder inherits the win.
    assert data["winner_id"] == data["home_player"]["id"]


async def test_placeholder_is_hidden_from_the_player_list(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    leaver, _, _ = await _season_with_match(db_session, "B")
    await client.delete(f"/api/players/{leaver.id}", headers=ADMIN_HEADERS)

    response = await client.get("/api/players")

    assert response.status_code == 200
    usernames = [p["username"] for p in response.json()]
    assert PLACEHOLDER_USERNAME not in usernames


async def test_only_one_placeholder_is_ever_created(client: AsyncClient, db_session: AsyncSession) -> None:
    first, _, _ = await _season_with_match(db_session, "C")
    second, _, _ = await _season_with_match(db_session, "D")

    await client.delete(f"/api/players/{first.id}", headers=ADMIN_HEADERS)
    await client.delete(f"/api/players/{second.id}", headers=ADMIN_HEADERS)

    result = await db_session.execute(select(Player).where(Player.is_placeholder.is_(True)))
    assert len(list(result.scalars().all())) == 1


async def test_match_against_the_placeholder_is_dropped(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Both participants deleted would put the same player on both sides of the
    match, violating ck_matches_distinct_players - there is no record left to
    keep, so the match goes."""
    leaver, stayer, match = await _season_with_match(db_session, "E")

    await client.delete(f"/api/players/{leaver.id}", headers=ADMIN_HEADERS)
    await client.delete(f"/api/players/{stayer.id}", headers=ADMIN_HEADERS)

    match_response = await client.get(f"/api/matches/{match.id}")
    assert match_response.status_code == 404


async def test_placeholder_itself_cannot_be_deleted(client: AsyncClient, db_session: AsyncSession) -> None:
    leaver, _, _ = await _season_with_match(db_session, "F")
    await client.delete(f"/api/players/{leaver.id}", headers=ADMIN_HEADERS)

    result = await db_session.execute(select(Player).where(Player.is_placeholder.is_(True)))
    placeholder = result.scalars().one()

    response = await client.delete(f"/api/players/{placeholder.id}", headers=ADMIN_HEADERS)
    assert response.status_code == 409


async def test_deleting_a_champion_transfers_the_title(client: AsyncClient, db_session: AsyncSession) -> None:
    """A season's champion must not silently become "no champion" - the bracket
    still shows them winning the final, so the placeholder inherits the title."""
    champion = Player(username="ChampionToDelete")
    db_session.add(champion)
    await db_session.flush()
    season = Season(name="Championship Season", start_date=date(2024, 1, 1), champion_id=champion.id)
    db_session.add(season)
    await db_session.commit()

    response = await client.delete(f"/api/players/{champion.id}", headers=ADMIN_HEADERS)
    assert response.status_code == 204

    season_response = await client.get(f"/api/seasons/{season.id}")
    assert season_response.status_code == 200
    data = season_response.json()
    assert data["champion"] is not None, "the season must not lose its champion entirely"
    assert data["champion"]["username"] == PLACEHOLDER_USERNAME


async def test_placeholder_username_is_reserved(client: AsyncClient) -> None:
    response = await client.post(
        "/api/players", json={"username": PLACEHOLDER_USERNAME}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 409


async def test_player_without_matches_still_deletes_cleanly(client: AsyncClient) -> None:
    create = await client.post("/api/players", json={"username": "NoMatchesTrainer"}, headers=ADMIN_HEADERS)
    player_id = create.json()["id"]

    response = await client.delete(f"/api/players/{player_id}", headers=ADMIN_HEADERS)
    assert response.status_code == 204
    assert (await client.get(f"/api/players/{player_id}")).status_code == 404
