import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { completedMatch, playerDetail, playerSummary } from "../test/factories";
import { renderAtRoute } from "../test/render";
import type { EloRatingHistoryEntry, PlayerDetail } from "../types";
import PlayerDetailPage from "./PlayerDetailPage";

const get = vi.fn();

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { players: { get: (...args: unknown[]) => get(...args) } } };
});

afterEach(() => vi.clearAllMocks());

function eloEvent(index: number): EloRatingHistoryEntry {
  return {
    match_id: `m${index}`,
    opponent_id: `o${index}`,
    opponent_slug: `rival-${index}`,
    opponent_username: `Rival ${index}`,
    occurred_at: `2025-0${(index % 9) + 1}-01T20:00:00Z`,
    result: index % 2 === 0 ? 1 : 0,
    expected_score: 0.5,
    rating_before: 1000,
    rating_after: 1032,
    rating_change: 32,
  };
}

/** A player who actually played the matches, so the rows render from their
 * perspective and name the opponent. */
function withMatches(count: number): PlayerDetail {
  const detail = playerDetail({ slug: "psykick", username: "Psykick" });
  const self = playerSummary({ id: detail.id, slug: detail.slug, username: detail.username });
  return {
    ...detail,
    completed_matches: Array.from({ length: count }, (_, i) =>
      completedMatch({
        home_player: self,
        away_player: playerSummary({ slug: `r${i}`, username: `Rival ${i}` }),
        winner_id: detail.id,
      }),
    ),
  };
}

function renderPlayer(detail: PlayerDetail) {
  get.mockResolvedValue(detail);
  return renderAtRoute("/player/:playerSlug", <PlayerDetailPage />, {
    route: `/player/${detail.slug}`,
  });
}

describe("PlayerDetailPage", () => {
  it("looks the player up by the slug in the URL", async () => {
    renderPlayer(playerDetail({ slug: "psykick", username: "Psykick" }));

    await screen.findByRole("heading", { name: "Psykick", level: 1 });
    expect(get).toHaveBeenCalledWith("psykick");
  });

  it("sets the document title from the player's name", async () => {
    renderPlayer(playerDetail({ username: "Psykick" }));

    await waitFor(() => expect(document.title).toBe("Psykick | Pokémon Premiership"));
  });

  it("shows the biography with its line breaks near the top", async () => {
    const biography = "Two-time finalist.\n\nKnown for the Sunday night sweep.";
    renderPlayer(playerDetail({ biography }));

    const rendered = await screen.findByText(/Two-time finalist/);
    expect(rendered.textContent).toBe(biography);
    expect(rendered).toHaveClass("plain-text");
  });

  it("omits the biography section entirely when there is none", async () => {
    renderPlayer(playerDetail({ biography: null }));

    await screen.findByRole("heading", { level: 1 });
    expect(document.querySelector(".player-page__biography")).toBeNull();
  });

  it("shows a champion marker with readable text", async () => {
    renderPlayer(
      playerDetail({
        championships: [
          {
            season_id: "s4",
            season_slug: "4",
            season_name: "Season 4",
            start_date: "2025-06-14",
            end_date: "2025-08-02",
          },
          {
            season_id: "s3",
            season_slug: "3",
            season_name: "Season 3",
            start_date: "2025-02-22",
            end_date: "2025-04-19",
          },
        ],
      }),
    );

    expect(await screen.findByText("2× Champion")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Season 4" })).toHaveAttribute(
      "href",
      "/seasons/4/standings",
    );
  });

  it("shows no champion marker for a player who has won nothing", async () => {
    renderPlayer(playerDetail({ championships: [] }));

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(/Champion/)).not.toBeInTheDocument();
  });

  it("puts Recent Matches above the season history and full match list", async () => {
    renderPlayer(withMatches(7));

    const headings = await screen.findAllByRole("heading", { level: 2 });
    const order = headings.map((h) => h.textContent);
    expect(order.indexOf("Recent Matches")).toBeLessThan(order.indexOf("Match History"));
  });

  it("shows at most five recent matches", async () => {
    renderPlayer(withMatches(8));

    const recent = (await screen.findByRole("heading", { name: "Recent Matches" })).closest(
      "section",
    );
    expect(within(recent as HTMLElement).getAllByRole("listitem")).toHaveLength(5);
  });

  it("reveals the full match history without another request", async () => {
    const user = userEvent.setup();
    renderPlayer(withMatches(8));

    await user.click(await screen.findByRole("button", { name: "View all matches (8)" }));

    expect(screen.getByRole("link", { name: "Rival 7" })).toBeInTheDocument();
    // The same array feeds both views - the page fetched once.
    expect(get).toHaveBeenCalledTimes(1);
  });

  describe("Elo history", () => {
    it("shows only five entries collapsed", async () => {
      const history = Array.from({ length: 24 }, (_, i) => eloEvent(i));
      renderPlayer(playerDetail({ elo_history: history }));

      const section = (await screen.findByRole("heading", { name: "Elo History" })).closest(
        "section",
      );
      expect(within(section as HTMLElement).getAllByRole("row")).toHaveLength(6); // header + 5
    });

    it("names the full count on the control", async () => {
      renderPlayer(playerDetail({ elo_history: Array.from({ length: 24 }, (_, i) => eloEvent(i)) }));

      const toggle = await screen.findByRole("button", {
        name: "Show full Elo history (24 matches)",
      });
      expect(toggle).toHaveAttribute("aria-expanded", "false");
    });

    it("expands to the whole history and back", async () => {
      const user = userEvent.setup();
      renderPlayer(playerDetail({ elo_history: Array.from({ length: 24 }, (_, i) => eloEvent(i)) }));

      await user.click(
        await screen.findByRole("button", { name: "Show full Elo history (24 matches)" }),
      );

      const section = screen.getByRole("heading", { name: "Elo History" }).closest("section");
      expect(within(section as HTMLElement).getAllByRole("row")).toHaveLength(25);

      const collapse = screen.getByRole("button", { name: "Show recent five" });
      expect(collapse).toHaveAttribute("aria-expanded", "true");
      await user.click(collapse);
      expect(within(section as HTMLElement).getAllByRole("row")).toHaveLength(6);
    });

    it("shows no expansion control when five or fewer events exist", async () => {
      renderPlayer(playerDetail({ elo_history: Array.from({ length: 5 }, (_, i) => eloEvent(i)) }));

      const section = (await screen.findByRole("heading", { name: "Elo History" })).closest(
        "section",
      );
      // A control that reveals nothing is worse than no control.
      expect(within(section as HTMLElement).queryByRole("button")).not.toBeInTheDocument();
      expect(within(section as HTMLElement).getAllByRole("row")).toHaveLength(6);
    });

    it("keeps before, change and after for each event", async () => {
      renderPlayer(playerDetail({ elo_history: [eloEvent(0)] }));

      const row = (await screen.findByRole("link", { name: "Rival 0" })).closest("tr");
      const cells = within(row as HTMLElement).getAllByRole("cell");
      expect(cells.map((c) => c.textContent)).toEqual(
        expect.arrayContaining(["1000", "+32", "1032"]),
      );
    });
  });
});
