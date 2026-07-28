from httpx import AsyncClient

from tests.conftest import ADMIN_HEADERS


async def test_create_player(client: AsyncClient) -> None:
    payload = {"username": "TestTrainer", "discord_id": "test#1234", "is_active": True}

    response = await client.post("/api/players", json=payload, headers=ADMIN_HEADERS)

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "TestTrainer"
    assert data["discord_id"] == "test#1234"
    assert data["is_active"] is True
    assert "id" in data
    assert "join_date" in data
    assert data["elo_rating"] == 1000


async def test_create_player_requires_admin_token(client: AsyncClient) -> None:
    response = await client.post("/api/players", json={"username": "NoTokenTrainer"})
    assert response.status_code == 401

    response = await client.post(
        "/api/players", json={"username": "WrongTokenTrainer"}, headers={"X-Admin-Token": "wrong"}
    )
    assert response.status_code == 401


async def test_create_player_duplicate_username_rejected(client: AsyncClient) -> None:
    payload = {"username": "DupeTrainer"}

    first = await client.post("/api/players", json=payload, headers=ADMIN_HEADERS)
    assert first.status_code == 201

    second = await client.post("/api/players", json=payload, headers=ADMIN_HEADERS)
    assert second.status_code == 409


async def test_list_players(client: AsyncClient) -> None:
    usernames = ["TrainerOne", "TrainerTwo"]
    for username in usernames:
        response = await client.post("/api/players", json={"username": username}, headers=ADMIN_HEADERS)
        assert response.status_code == 201

    response = await client.get("/api/players")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(usernames)
    assert {player["username"] for player in data} == set(usernames)


async def test_search_players_case_insensitive(client: AsyncClient) -> None:
    await client.post("/api/players", json={"username": "SearchableTrainer"}, headers=ADMIN_HEADERS)
    await client.post("/api/players", json={"username": "OtherTrainer"}, headers=ADMIN_HEADERS)

    response = await client.get("/api/players", params={"q": "searchable"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["username"] == "SearchableTrainer"


async def test_search_players_no_results(client: AsyncClient) -> None:
    await client.post("/api/players", json={"username": "SomeTrainer"}, headers=ADMIN_HEADERS)

    response = await client.get("/api/players", params={"q": "nonexistent"})

    assert response.status_code == 200
    assert response.json() == []


async def test_get_player_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/players/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_get_player_detail_empty_history(client: AsyncClient) -> None:
    create = await client.post("/api/players", json={"username": "FreshTrainer"}, headers=ADMIN_HEADERS)
    player_id = create.json()["id"]

    response = await client.get(f"/api/players/{player_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["most_recent_season_record"] is None
    assert data["historical_record"] == {"wins": 0, "losses": 0}
    assert data["season_records"] == []
    assert data["backlog"] == []
    assert data["completed_matches"] == []


async def test_update_player_elo_rating(client: AsyncClient) -> None:
    create = await client.post("/api/players", json={"username": "EloTrainer"}, headers=ADMIN_HEADERS)
    player_id = create.json()["id"]

    response = await client.patch(f"/api/players/{player_id}", json={"elo_rating": 1234}, headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["elo_rating"] == 1234


async def test_delete_player(client: AsyncClient) -> None:
    create = await client.post("/api/players", json={"username": "DeleteMeTrainer"}, headers=ADMIN_HEADERS)
    player_id = create.json()["id"]

    response = await client.delete(f"/api/players/{player_id}", headers=ADMIN_HEADERS)
    assert response.status_code == 204

    get_response = await client.get(f"/api/players/{player_id}")
    assert get_response.status_code == 404


async def test_delete_player_without_admin_token_rejected(client: AsyncClient) -> None:
    create = await client.post("/api/players", json={"username": "ProtectedTrainer"}, headers=ADMIN_HEADERS)
    player_id = create.json()["id"]

    response = await client.delete(f"/api/players/{player_id}")
    assert response.status_code == 401
