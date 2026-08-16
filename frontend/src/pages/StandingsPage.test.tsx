import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { playerSummary, seasonDetail } from "../test/factories";
import { renderAtRoute } from "../test/render";
import type { SeasonDetail } from "../types";
import StandingsPage from "./StandingsPage";

const get = vi.fn();
const current = vi.fn();

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      seasons: {
        get: (...args: unknown[]) => get(...args),
        current: () => current(),
      },
    },
  };
});

afterEach(() => vi.clearAllMocks());

function withStandings(overrides: Partial<SeasonDetail> = {}): SeasonDetail {
  const alice = playerSummary({ slug: "alice", username: "Alice" });
  const bob = playerSummary({ slug: "bob", username: "Bob" });
  return seasonDetail({
    standings: [
      {
        group_label: "Group A",
        standings: [
          { player: alice, wins: 3, losses: 0, pokemon_differential: 8, pokemon_differential_complete: true, tiebreaker_value: null },
          { player: bob, wins: 0, losses: 3, pokemon_differential: -8, pokemon_differential_complete: true, tiebreaker_value: null },
        ],
      },
    ],
    roster: [{ player: alice, group_label: "Group A", pokemon: [], former_pokemon: [] }],
    ...overrides,
  });
}

describe("StandingsPage", () => {
  it("resolves the current season on /standings", async () => {
    current.mockResolvedValue(withStandings({ name: "Season 7" }));
    renderAtRoute("/standings", <StandingsPage />, { route: "/standings" });

    await screen.findByRole("heading", { name: "Season 7 Standings", level: 1 });
    expect(current).toHaveBeenCalled();
    expect(get).not.toHaveBeenCalled();
  });

  it("looks a specific season up by slug", async () => {
    get.mockResolvedValue(withStandings({ slug: "4", name: "Season 4" }));
    renderAtRoute("/seasons/:seasonRef/standings", <StandingsPage />, {
      route: "/seasons/4/standings",
    });

    await screen.findByRole("heading", { name: "Season 4 Standings", level: 1 });
    expect(get).toHaveBeenCalledWith("4");
  });

  it("titles the page with the season", async () => {
    get.mockResolvedValue(withStandings({ slug: "6", name: "Season 6" }));
    renderAtRoute("/seasons/:seasonRef/standings", <StandingsPage />, {
      route: "/seasons/6/standings",
    });

    await waitFor(() =>
      expect(document.title).toBe("Season 6 Standings | Pokémon Premiership"),
    );
  });

  it("puts Group Standings above the Roster", async () => {
    current.mockResolvedValue(withStandings());
    renderAtRoute("/standings", <StandingsPage />, { route: "/standings" });

    const headings = await screen.findAllByRole("heading", { level: 2 });
    const order = headings.map((h) => h.textContent);
    expect(order).toEqual(["Group Standings", "Roster"]);
  });

  it("renders the standings rows in the order the API gave them", async () => {
    current.mockResolvedValue(withStandings());
    renderAtRoute("/standings", <StandingsPage />, { route: "/standings" });

    const rows = await screen.findAllByRole("row");
    // Header, then Alice (3-0) before Bob (0-3) - the server's tiebreak order.
    expect(rows[1].textContent).toContain("Alice");
    expect(rows[2].textContent).toContain("Bob");
  });

  it("links players by their canonical slug", async () => {
    current.mockResolvedValue(withStandings());
    renderAtRoute("/standings", <StandingsPage />, { route: "/standings" });

    const table = await screen.findByRole("table");
    expect(within(table).getByRole("link", { name: "Alice" })).toHaveAttribute(
      "href",
      "/player/alice",
    );
  });

  it("says when it is showing a finished season between seasons", async () => {
    current.mockResolvedValue(withStandings({ name: "Season 4", is_active: false }));
    renderAtRoute("/standings", <StandingsPage />, { route: "/standings" });

    expect(await screen.findByText(/between seasons/)).toBeInTheDocument();
    expect(screen.getByText(/final standings of Season 4/)).toBeInTheDocument();
  });

  it("does not add that note for an active season", async () => {
    current.mockResolvedValue(withStandings({ is_active: true }));
    renderAtRoute("/standings", <StandingsPage />, { route: "/standings" });

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(/between seasons/)).not.toBeInTheDocument();
  });

  it("redirects a legacy UUID standings URL to the slug form", async () => {
    const uuid = "caaab4c1-8546-4408-8075-2af509255808";
    get.mockResolvedValue(withStandings({ slug: "1", name: "Season 1" }));
    renderAtRoute("/seasons/:seasonRef/standings", <StandingsPage />, {
      route: `/seasons/${uuid}/standings`,
    });

    await waitFor(() =>
      expect(screen.getByTestId("landed-at")).toHaveTextContent("/seasons/1/standings"),
    );
  });

  it("reports an empty season honestly", async () => {
    current.mockResolvedValue(seasonDetail({ standings: [], roster: [] }));
    renderAtRoute("/standings", <StandingsPage />, { route: "/standings" });

    expect(await screen.findByText("No standings available yet.")).toBeInTheDocument();
    expect(screen.getByText("No roster recorded yet.")).toBeInTheDocument();
  });
});
