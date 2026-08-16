from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import ADMIN_HEADERS, make_season


async def test_site_links_start_empty(client: AsyncClient) -> None:
    response = await client.get("/api/site-links")

    assert response.status_code == 200
    assert response.json() == {
        "stream_url": None,
        "stream_label": None,
        "document_url": None,
        "document_label": None,
        "table_url": None,
        "table_label": None,
    }


async def test_setting_links_requires_admin(client: AsyncClient) -> None:
    response = await client.put("/api/site-links", json={"stream_url": "https://twitch.tv/league"})
    assert response.status_code == 401


async def test_overrides_replace_the_derived_home_links(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = make_season(
        name="Override Season",
        start_date=date(2024, 1, 1),
        sheet_url="https://docs.google.com/spreadsheets/derived",
    )
    db_session.add(season)
    await db_session.commit()

    # Derived first: document comes from the season sheet, table points inward.
    before = (await client.get("/api/home")).json()
    assert before["document"]["url"] == "https://docs.google.com/spreadsheets/derived"
    assert before["table"]["url"] == f"/seasons/{season.id}"
    assert before["table"]["external"] is False

    await client.put(
        "/api/site-links",
        json={
            "stream_url": "https://twitch.tv/league",
            "stream_label": "Live now",
            "document_url": "https://docs.google.com/spreadsheets/pinned",
            "table_url": "https://liquipedia.net/standings",
            "table_label": "Full table",
        },
        headers=ADMIN_HEADERS,
    )

    after = (await client.get("/api/home")).json()
    assert after["latest_stream"] == {
        "url": "https://twitch.tv/league",
        "label": "Live now",
        "external": True,
    }
    assert after["document"]["url"] == "https://docs.google.com/spreadsheets/pinned"
    # A pinned table link becomes outbound, so the client renders an anchor.
    assert after["table"]["url"] == "https://liquipedia.net/standings"
    assert after["table"]["external"] is True


async def test_url_without_label_gets_a_readable_fallback(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A blank label must not produce a link with no text."""
    await client.put(
        "/api/site-links", json={"stream_url": "https://twitch.tv/league"}, headers=ADMIN_HEADERS
    )

    home = (await client.get("/api/home")).json()
    assert home["latest_stream"]["label"] == "Watch the latest stream"


async def test_clearing_an_override_restores_the_derived_link(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = make_season(
        name="Restore Season",
        start_date=date(2024, 1, 1),
        sheet_url="https://docs.google.com/spreadsheets/derived",
    )
    db_session.add(season)
    await db_session.commit()

    await client.put(
        "/api/site-links",
        json={"document_url": "https://docs.google.com/spreadsheets/pinned"},
        headers=ADMIN_HEADERS,
    )
    assert (await client.get("/api/home")).json()["document"]["url"].endswith("pinned")

    # PUT is a full replacement, so an omitted field hands control back.
    await client.put("/api/site-links", json={}, headers=ADMIN_HEADERS)

    home = (await client.get("/api/home")).json()
    assert home["document"]["url"] == "https://docs.google.com/spreadsheets/derived"
