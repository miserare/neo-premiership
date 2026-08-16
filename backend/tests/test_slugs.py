"""Canonical slugs, biographies and champion markers."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.slugs import slugify, slugify_season_name
from tests.conftest import ADMIN_HEADERS, make_player, make_season


# ------------------------------------------------------------- slug derivation


@pytest.mark.parametrize(
    ("username", "expected"),
    [
        ("Psykick", "psykick"),
        ("Brazilian Fury", "brazilian-fury"),
        ("T10S", "t10s"),
        ("  Spaced  Out  ", "spaced-out"),
        ("Renè Accented", "rene-accented"),
        ("Punctuation!!!Heavy???", "punctuation-heavy"),
        ("限界突破", ""),
    ],
)
def test_slugify_is_deterministic_ascii(username: str, expected: str) -> None:
    assert slugify(username) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Season 6", "6"),
        ("season 6", "6"),
        ("Season Summer 2027", "summer-2027"),
        # No leading "Season", so nothing is stripped.
        ("Summer Invitational", "summer-invitational"),
        # Only the word itself: there is nothing to strip down to, so it stands.
        ("Season", "season"),
    ],
)
def test_season_slugs_do_not_assume_a_number(name: str, expected: str) -> None:
    assert slugify_season_name(name) == expected


# ------------------------------------------------------------ slug validation


async def test_player_slug_is_derived_from_the_username(client: AsyncClient) -> None:
    response = await client.post(
        "/api/players", json={"username": "Slug Derived"}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "slug-derived"


async def test_an_explicit_slug_overrides_the_derived_one(client: AsyncClient) -> None:
    response = await client.post(
        "/api/players",
        json={"username": "AEL (Cheeburbur)", "slug": "cheeburbur"},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "cheeburbur"


# Uppercase is deliberately absent: it is folded rather than refused, which the
# next test covers.
@pytest.mark.parametrize(
    "slug", ["Has Spaces", "trailing-", "-leading", "double--hyphen", "punctuation!", "", "x" * 65]
)
async def test_invalid_slugs_are_rejected(client: AsyncClient, slug: str) -> None:
    response = await client.post(
        "/api/players", json={"username": "SlugValidation", "slug": slug}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 422


async def test_slug_input_is_case_folded_not_rejected(client: AsyncClient) -> None:
    """"Psykick " and "psykick" are plainly the same slug, so the obvious
    normalization happens rather than an error."""
    response = await client.post(
        "/api/players", json={"username": "CaseFolded", "slug": "  PsyKick  "}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "psykick"


async def test_slug_uniqueness_is_case_insensitive(client: AsyncClient) -> None:
    first = await client.post(
        "/api/players", json={"username": "FirstClaim", "slug": "contested"}, headers=ADMIN_HEADERS
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/players", json={"username": "SecondClaim", "slug": "CONTESTED"}, headers=ADMIN_HEADERS
    )
    assert second.status_code == 409


async def test_a_derived_slug_collision_asks_for_an_explicit_one(client: AsyncClient) -> None:
    """No silent "psykick-2": the administrator is told, and chooses."""
    await client.post("/api/players", json={"username": "Caps Lock"}, headers=ADMIN_HEADERS)

    clash = await client.post("/api/players", json={"username": "caps lock"}, headers=ADMIN_HEADERS)
    assert clash.status_code == 409
    assert "caps-lock" in clash.json()["detail"]


async def test_a_username_with_no_ascii_requires_an_explicit_slug(client: AsyncClient) -> None:
    response = await client.post("/api/players", json={"username": "限界突破"}, headers=ADMIN_HEADERS)
    assert response.status_code == 422

    explicit = await client.post(
        "/api/players", json={"username": "限界突破", "slug": "genkai"}, headers=ADMIN_HEADERS
    )
    assert explicit.status_code == 201
    assert explicit.json()["slug"] == "genkai"


async def test_reserved_slugs_are_refused(client: AsyncClient) -> None:
    response = await client.post(
        "/api/players", json={"username": "Impostor", "slug": "deleted-player"}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 409


async def test_renaming_a_player_leaves_their_slug_alone(client: AsyncClient) -> None:
    """The whole point of storing the slug separately: existing links survive."""
    created = (
        await client.post("/api/players", json={"username": "Original Name"}, headers=ADMIN_HEADERS)
    ).json()
    assert created["slug"] == "original-name"

    renamed = await client.patch(
        f"/api/players/{created['id']}", json={"username": "Brand New Name"}, headers=ADMIN_HEADERS
    )
    assert renamed.status_code == 200
    assert renamed.json()["username"] == "Brand New Name"
    assert renamed.json()["slug"] == "original-name"

    # And the old link still resolves.
    assert (await client.get("/api/players/original-name")).status_code == 200


async def test_a_slug_can_be_changed_deliberately(client: AsyncClient) -> None:
    created = (
        await client.post("/api/players", json={"username": "Deliberate"}, headers=ADMIN_HEADERS)
    ).json()

    updated = await client.patch(
        f"/api/players/{created['id']}", json={"slug": "chosen-slug"}, headers=ADMIN_HEADERS
    )
    assert updated.status_code == 200
    assert updated.json()["slug"] == "chosen-slug"
    assert (await client.get("/api/players/chosen-slug")).status_code == 200


async def test_changing_a_slug_to_a_taken_one_is_refused(client: AsyncClient) -> None:
    await client.post("/api/players", json={"username": "Holder"}, headers=ADMIN_HEADERS)
    other = (
        await client.post("/api/players", json={"username": "Mover"}, headers=ADMIN_HEADERS)
    ).json()

    response = await client.patch(
        f"/api/players/{other['id']}", json={"slug": "holder"}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 409


# ---------------------------------------------------------------- slug lookup


async def test_a_player_resolves_by_slug_and_by_legacy_uuid(client: AsyncClient) -> None:
    created = (
        await client.post("/api/players", json={"username": "Both Ways"}, headers=ADMIN_HEADERS)
    ).json()

    by_slug = await client.get("/api/players/both-ways")
    by_uuid = await client.get(f"/api/players/{created['id']}")

    assert by_slug.status_code == by_uuid.status_code == 200
    # The legacy URL resolves to exactly the same player, which is what lets the
    # frontend redirect it to the canonical route.
    assert by_slug.json()["id"] == by_uuid.json()["id"] == created["id"]
    assert by_slug.json()["slug"] == "both-ways"


async def test_an_unknown_slug_is_a_404_not_a_500(client: AsyncClient) -> None:
    assert (await client.get("/api/players/nobody-by-that-name")).status_code == 404


async def test_slug_lookup_exposes_no_private_fields(client: AsyncClient) -> None:
    """A new lookup path must not become a new leak path."""
    await client.post(
        "/api/players",
        json={"username": "Private Person", "discord_id": "secret#0001"},
        headers=ADMIN_HEADERS,
    )

    body = (await client.get("/api/players/private-person")).json()

    assert "discord_id" not in body
    assert "initial_elo_rating" not in body
    assert "secret#0001" not in str(body)


async def test_a_season_resolves_by_slug_and_by_legacy_uuid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = make_season(name="Season 6", start_date=date(2025, 1, 1))
    db_session.add(season)
    await db_session.commit()

    by_slug = await client.get("/api/seasons/6")
    by_uuid = await client.get(f"/api/seasons/{season.id}")

    assert by_slug.status_code == by_uuid.status_code == 200
    assert by_slug.json()["id"] == by_uuid.json()["id"] == str(season.id)
    assert by_slug.json()["slug"] == "6"


# ------------------------------------------------------- current season route


async def test_current_season_prefers_the_active_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    today = date.today()
    db_session.add_all(
        [
            make_season(
                name="Season 1",
                start_date=today - timedelta(days=400),
                end_date=today - timedelta(days=300),
            ),
            make_season(
                name="Season 2",
                start_date=today - timedelta(days=10),
                end_date=today + timedelta(days=10),
            ),
        ]
    )
    await db_session.commit()

    body = (await client.get("/api/seasons/current")).json()

    assert body["name"] == "Season 2"
    assert body["is_active"] is True


async def test_between_seasons_current_is_the_most_recently_started(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    today = date.today()
    db_session.add_all(
        [
            make_season(
                name="Season 1",
                start_date=today - timedelta(days=400),
                end_date=today - timedelta(days=300),
            ),
            make_season(
                name="Season 2",
                start_date=today - timedelta(days=100),
                end_date=today - timedelta(days=30),
            ),
        ]
    )
    await db_session.commit()

    body = (await client.get("/api/seasons/current")).json()

    assert body["name"] == "Season 2"
    # False is what tells the page to label the context rather than imply play
    # is under way.
    assert body["is_active"] is False


async def test_current_season_with_no_seasons_is_a_404(client: AsyncClient) -> None:
    assert (await client.get("/api/seasons/current")).status_code == 404


# ----------------------------------------------------------------- biography


async def test_a_biography_round_trips_to_the_public_profile(client: AsyncClient) -> None:
    biography = "Two-time finalist.\n\nKnown for the Sunday night sweep."
    created = (
        await client.post(
            "/api/players",
            json={"username": "Storyteller", "biography": biography},
            headers=ADMIN_HEADERS,
        )
    ).json()
    assert created["biography"] == biography

    public = (await client.get("/api/players/storyteller")).json()
    # Newlines survive the round trip: the frontend renders them with
    # white-space: pre-wrap rather than converting them to markup.
    assert public["biography"] == biography


async def test_a_biography_can_be_edited_and_cleared(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/api/players", json={"username": "Editable", "biography": "First draft."}, headers=ADMIN_HEADERS
        )
    ).json()

    edited = await client.patch(
        f"/api/players/{created['id']}", json={"biography": "Second draft."}, headers=ADMIN_HEADERS
    )
    assert edited.json()["biography"] == "Second draft."

    cleared = await client.patch(
        f"/api/players/{created['id']}", json={"biography": None}, headers=ADMIN_HEADERS
    )
    assert cleared.json()["biography"] is None


async def test_an_over_long_biography_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/players",
        json={"username": "TooMuch", "biography": "x" * 4001},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


async def test_biography_is_absent_from_nested_player_summaries(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A twenty-player roster must not ship twenty biographies."""
    player = make_player(username="Nested", biography="A long life story.")
    season = make_season(name="Season 3", start_date=date(2024, 1, 1))
    db_session.add_all([player, season])
    await db_session.flush()
    from app.models.season_entry import SeasonEntry

    db_session.add(SeasonEntry(season_id=season.id, player_id=player.id))
    await db_session.commit()

    body = (await client.get("/api/seasons/3")).json()

    summary = body["roster"][0]["player"]
    assert summary["slug"] == "nested"
    assert "biography" not in summary


# --------------------------------------------------------------- championships


async def test_a_champion_gets_their_seasons_on_their_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    champion = make_player(username="Renk")
    db_session.add(champion)
    await db_session.flush()
    db_session.add_all(
        [
            make_season(name="Season 3", start_date=date(2025, 2, 22), champion_id=champion.id),
            make_season(name="Season 4", start_date=date(2025, 6, 14), champion_id=champion.id),
            make_season(name="Season 7", start_date=date(2026, 8, 13)),
        ]
    )
    await db_session.commit()

    body = (await client.get("/api/players/renk")).json()

    # Newest first, and derived purely from seasons.champion_id.
    assert [c["season_name"] for c in body["championships"]] == ["Season 4", "Season 3"]
    assert [c["season_slug"] for c in body["championships"]] == ["4", "3"]


async def test_a_player_who_has_won_nothing_has_no_championships(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add(make_player(username="Runner Up"))
    await db_session.commit()

    assert (await client.get("/api/players/runner-up")).json()["championships"] == []


async def test_the_placeholder_player_is_never_shown_as_a_champion(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deleting a champion transfers their title to the tombstone so the bracket
    still shows a winner - but "Deleted Player" must not be decorated for it."""
    champion = (
        await client.post("/api/players", json={"username": "Doomed Champion"}, headers=ADMIN_HEADERS)
    ).json()
    season = make_season(name="Season 5", start_date=date(2025, 1, 1))
    db_session.add(season)
    await db_session.commit()

    await client.patch(
        f"/api/seasons/{season.id}", json={"champion_id": champion["id"]}, headers=ADMIN_HEADERS
    )
    assert (await client.delete(f"/api/players/{champion['id']}", headers=ADMIN_HEADERS)).status_code == 204

    placeholder = (await client.get("/api/players/deleted-player")).json()
    assert placeholder["championships"] == []
