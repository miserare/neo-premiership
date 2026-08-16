import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { completedMatch, homeResponse, match, playerSummary } from "../test/factories";
import { renderWithRouter } from "../test/render";
import type { HomeResponse } from "../types";
import HomePage from "./HomePage";

const get = vi.fn();

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { home: { get: () => get() } } };
});

afterEach(() => vi.clearAllMocks());

function renderHome(response: HomeResponse) {
  get.mockResolvedValue(response);
  return renderWithRouter(<HomePage />);
}

const psykick = playerSummary({ slug: "psykick", username: "Psykick" });
const renk = playerSummary({ slug: "renk", username: "Renk" });

describe("HomePage announcements", () => {
  it("keeps the newlines an administrator typed", async () => {
    const body = "Matchday 1\n\nSaturday 20:00 - Psykick vs Renk\nSunday 18:00 - Doodle vs Void";
    renderHome(
      homeResponse({
        announcements: [
          {
            id: "a1",
            title: "Matchday 1 Fixtures",
            body,
            published_at: "2026-08-15T16:46:34Z",
            link_url: null,
          },
        ],
      }),
    );

    // getByText collapses whitespace, so the assertion is on the element's own
    // textContent - which is what would actually lose the newlines.
    await screen.findByRole("heading", { name: "Matchday 1 Fixtures" });
    const rendered = document.querySelector(".announcement-card .plain-text");
    expect(rendered?.textContent).toBe(body);
  });

  it("does not render administrator input as markup", async () => {
    const body = "<b>bold?</b>";
    renderHome(
      homeResponse({
        announcements: [
          { id: "a1", title: "Test", body, published_at: "2026-08-15T00:00:00Z", link_url: null },
        ],
      }),
    );

    const rendered = await screen.findByText("<b>bold?</b>");
    expect(rendered.querySelector("b")).toBeNull();
  });
});

describe("HomePage fixtures", () => {
  it("sets the bare site name as the title", async () => {
    renderHome(homeResponse());
    await waitFor(() => expect(document.title).toBe("Pokémon Premiership"));
  });

  it("lists this week's matches", async () => {
    renderHome(
      homeResponse({
        fixtures: {
          ...homeResponse().fixtures,
          this_week: [
            match({ home_player: psykick, away_player: renk, round_label: "Group A - Matchday 1" }),
          ],
        },
      }),
    );

    const section = (await screen.findByRole("heading", { name: "Matchday" })).closest("section");
    expect(within(section as HTMLElement).getByText("Group A - Matchday 1")).toBeInTheDocument();
    expect(within(section as HTMLElement).getByRole("link", { name: "Psykick" })).toHaveAttribute(
      "href",
      "/player/psykick",
    );
  });

  it("shows a useful empty state for a quiet week", async () => {
    renderHome(
      homeResponse({
        current_season: {
          id: "s7",
          slug: "7",
          name: "Season 7",
          is_active: true,
          sheet_url: null,
          roster: [],
        },
      }),
    );

    expect(
      await screen.findByText("No Season 7 matches are scheduled this week."),
    ).toBeInTheDocument();
  });

  it("names the week it is showing", async () => {
    renderHome(homeResponse());

    // The window comes from the server in the league's zone; the page reports
    // it rather than recomputing it.
    const section = (await screen.findByRole("heading", { name: "Matchday" })).closest("section");
    expect(within(section as HTMLElement).getByText(/Aug/)).toBeInTheDocument();
  });

  it("shows featured matches under their own heading", async () => {
    renderHome(
      homeResponse({
        fixtures: {
          ...homeResponse().fixtures,
          featured: [
            completedMatch({
              home_player: psykick,
              away_player: renk,
              winner_id: psykick.id,
              featured_on_homepage: true,
              round_label: "Final",
            }),
          ],
        },
      }),
    );

    expect(await screen.findByRole("heading", { name: "Featured" })).toBeInTheDocument();
    expect(screen.getByText("Featured", { selector: "span" })).toBeInTheDocument();
  });

  it("marks a featured match with text, not colour alone", async () => {
    renderHome(
      homeResponse({
        fixtures: {
          ...homeResponse().fixtures,
          featured: [match({ home_player: psykick, away_player: renk, featured_on_homepage: true })],
        },
      }),
    );

    const flag = await screen.findByText("Featured", { selector: "span" });
    expect(flag).toHaveClass("match-row__featured-flag");
  });

  it("shows a completed featured match with its score", async () => {
    renderHome(
      homeResponse({
        fixtures: {
          ...homeResponse().fixtures,
          featured: [
            completedMatch({
              home_player: psykick,
              away_player: renk,
              winner_id: psykick.id,
              featured_on_homepage: true,
              series: { home_wins: 2, away_wins: 1, game_count: 3 },
            }),
          ],
        },
      }),
    );

    expect(await screen.findByText("2-1")).toBeInTheDocument();
  });

  it("renders no Featured heading when nothing is pinned", async () => {
    renderHome(homeResponse());

    await screen.findByRole("heading", { name: "Matchday" });
    expect(screen.queryByRole("heading", { name: "Featured" })).not.toBeInTheDocument();
  });

  it("links the current season by slug", async () => {
    renderHome(
      homeResponse({
        current_season: {
          id: "s7",
          slug: "7",
          name: "Season 7",
          is_active: true,
          sheet_url: null,
          roster: [psykick],
        },
      }),
    );

    const links = await screen.findAllByRole("link", { name: "Season 7" });
    expect(links[0]).toHaveAttribute("href", "/seasons/7");
    expect(screen.getByRole("link", { name: "Psykick" })).toHaveAttribute("href", "/player/psykick");
  });
});
