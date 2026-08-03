"""Anonymous callers must never receive private administrative fields.

discord_id is personal contact information. It is legitimate for an
administrator to see it and illegitimate for the public to. These tests walk
every anonymous endpoint - including the nested player objects inside season,
roster, standings, bracket, match and home responses - and assert it is absent.
"""

from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.models.player import Player
from app.models.playoff_round import PlayoffRound
from app.models.season import Season
from app.models.season_entry import SeasonEntry
from tests.conftest import ADMIN_HEADERS

PRIVATE_MARKER = "trainer#4821"
PRIVATE_FIELD = "discord_id"


async def _league_with_private_data(db_session: AsyncSession) -> tuple[Player, Season]:
    """A fully populated season whose players all carry a discord_id, so any
    leak anywhere in the response graph shows up as the marker string."""
    season = Season(name="Privacy Season", start_date=date(2024, 1, 1))
    home = Player(username="PrivacyHome", discord_id=PRIVATE_MARKER)
    away = Player(username="PrivacyAway", discord_id="other#0002")
    db_session.add_all([season, home, away])
    await db_session.flush()

    season.champion_id = home.id
    final = PlayoffRound(season_id=season.id, label="Final", display_order=1)
    db_session.add(final)
    await db_session.flush()

    db_session.add_all(
        [
            SeasonEntry(season_id=season.id, player_id=home.id, group_label="A"),
            SeasonEntry(season_id=season.id, player_id=away.id, group_label="A"),
            Match(
                season_id=season.id,
                home_player_id=home.id,
                away_player_id=away.id,
                winner_id=home.id,
                status=MatchStatus.COMPLETED,
                stage=MatchStage.GROUP,
            ),
            Match(
                season_id=season.id,
                home_player_id=home.id,
                away_player_id=away.id,
                winner_id=home.id,
                status=MatchStatus.COMPLETED,
                stage=MatchStage.PLAYOFFS,
                playoff_round_id=final.id,
                bracket_order=1,
            ),
        ]
    )
    await db_session.commit()
    return home, season


def _assert_clean(payload: str, where: str) -> None:
    assert PRIVATE_MARKER not in payload, f"discord_id value leaked in {where}"
    assert PRIVATE_FIELD not in payload, f"discord_id field leaked in {where}"


async def test_anonymous_player_list_hides_discord_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _league_with_private_data(db_session)

    response = await client.get("/api/players")

    assert response.status_code == 200
    assert any(p["username"] == "PrivacyHome" for p in response.json())
    _assert_clean(response.text, "GET /api/players")


async def test_anonymous_player_detail_hides_discord_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    home, _ = await _league_with_private_data(db_session)

    response = await client.get(f"/api/players/{home.id}")

    assert response.status_code == 200
    body = response.json()
    # Public information is still present - this is a redaction, not a blackout.
    assert body["username"] == "PrivacyHome"
    assert "elo_rating" in body
    assert "historical_record" in body
    _assert_clean(response.text, "GET /api/players/{id}")


async def test_nested_players_across_every_public_endpoint_are_clean(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Season, roster, standings, bracket, match and home responses all embed
    player objects. A single over-broad schema anywhere would leak here."""
    home, season = await _league_with_private_data(db_session)

    endpoints = [
        "/api/home",
        "/api/players",
        f"/api/players/{home.id}",
        "/api/seasons",
        f"/api/seasons/{season.id}",
        f"/api/seasons/{season.id}/roster",
        f"/api/matches?season_id={season.id}",
        "/api/announcements",
        "/api/site-links",
    ]

    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert response.status_code == 200, f"{endpoint} -> {response.status_code}"
        _assert_clean(response.text, endpoint)


async def test_individual_match_response_is_clean(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, season = await _league_with_private_data(db_session)
    matches = (await client.get(f"/api/matches?season_id={season.id}")).json()

    for match in matches:
        response = await client.get(f"/api/matches/{match['id']}")
        assert response.status_code == 200
        _assert_clean(response.text, f"GET /api/matches/{match['id']}")


async def test_administrator_can_still_see_discord_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The data is not destroyed - an authenticated administrator needs it."""
    await _league_with_private_data(db_session)

    response = await client.get("/api/players/admin/list", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    players = {p["username"]: p for p in response.json()}
    assert players["PrivacyHome"]["discord_id"] == PRIVATE_MARKER


async def test_admin_player_list_requires_authentication(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _league_with_private_data(db_session)

    response = await client.get("/api/players/admin/list")

    assert response.status_code == 401
    _assert_clean(response.text, "unauthenticated GET /api/players/admin/list")


async def test_public_openapi_does_not_describe_private_fields(client: AsyncClient) -> None:
    """If the schema is exposed at all, the public player models it documents
    must not advertise a discord_id field."""
    response = await client.get("/openapi.json")
    if response.status_code == 404:
        return  # docs disabled entirely, which is the production posture

    schemas = response.json()["components"]["schemas"]
    for name in ("PlayerPublic", "PlayerDetail", "PlayerSummary"):
        # Check declared properties, not the raw JSON: the docstrings mention
        # the field by name precisely to explain that it is excluded.
        properties = schemas[name].get("properties", {})
        assert PRIVATE_FIELD not in properties, f"{name} exposes {PRIVATE_FIELD}"

    # And the admin model, which is only ever returned from a guarded route,
    # must still carry it - otherwise administrators lost the data.
    assert PRIVATE_FIELD in schemas["PlayerAdmin"]["properties"]


async def test_admin_session_details_are_not_public(client: AsyncClient) -> None:
    """Session metadata (IP addresses, user agents) is administrative."""
    response = await client.get("/api/admin/sessions")
    assert response.status_code == 401
    assert "ip_address" not in response.text
