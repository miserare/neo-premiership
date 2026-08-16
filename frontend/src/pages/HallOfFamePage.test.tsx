import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { completedMatch, hallOfFameEntry, playerSummary } from "../test/factories";
import { renderWithRouter } from "../test/render";
import type { HallOfFameEntry } from "../types";
import HallOfFamePage from "./HallOfFamePage";

const get = vi.fn();

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { hallOfFame: { get: () => get() } } };
});

afterEach(() => vi.clearAllMocks());

function renderHall(entries: HallOfFameEntry[]) {
  get.mockResolvedValue({ entries });
  return renderWithRouter(<HallOfFamePage />);
}

describe("HallOfFamePage", () => {
  it("sets the document title", async () => {
    renderHall([]);
    await waitFor(() => expect(document.title).toBe("Hall of Fame | Pokémon Premiership"));
  });

  it("explains an empty hall rather than rendering nothing", async () => {
    renderHall([]);

    expect(await screen.findByText(/No champion has been recorded yet/)).toBeInTheDocument();
  });

  it("lists champions in the order the API returned", async () => {
    renderHall([
      hallOfFameEntry({
        season_id: "s4",
        season_slug: "4",
        season_name: "Season 4",
        champion: playerSummary({ slug: "renk", username: "Renk" }),
      }),
      hallOfFameEntry({
        season_id: "s1",
        season_slug: "1",
        season_name: "Season 1",
        champion: playerSummary({ slug: "doodle", username: "Doodle" }),
      }),
    ]);

    const champions = await screen.findAllByRole("heading", { level: 2 });
    expect(champions.map((h) => h.textContent)).toEqual(["★Renk", "★Doodle"]);
  });

  it("links the champion and the season standings", async () => {
    renderHall([
      hallOfFameEntry({
        season_slug: "4",
        season_name: "Season 4",
        champion: playerSummary({ slug: "renk", username: "Renk" }),
      }),
    ]);

    expect(await screen.findByRole("link", { name: "Renk" })).toHaveAttribute(
      "href",
      "/player/renk",
    );
    expect(screen.getAllByRole("link", { name: /Season 4/ })[0]).toHaveAttribute(
      "href",
      "/seasons/4/standings",
    );
  });

  it("says how many titles a repeat champion has", async () => {
    renderHall([hallOfFameEntry({ championship_count: 3 })]);

    expect(await screen.findByText(/3× Champion/)).toBeInTheDocument();
  });

  it("renders the championship run in the order given", async () => {
    const champion = playerSummary({ slug: "renk", username: "Renk" });
    renderHall([
      hallOfFameEntry({
        champion,
        championship_run: [
          completedMatch({
            home_player: champion,
            away_player: playerSummary({ slug: "a", username: "Quarter Foe" }),
            winner_id: champion.id,
            round_label: "Quarterfinal",
          }),
          completedMatch({
            home_player: champion,
            away_player: playerSummary({ slug: "b", username: "Semi Foe" }),
            winner_id: champion.id,
            round_label: "Semifinal",
          }),
          completedMatch({
            home_player: champion,
            away_player: playerSummary({ slug: "c", username: "Final Foe" }),
            winner_id: champion.id,
            round_label: "Final",
          }),
        ],
      }),
    ]);

    const run = (await screen.findByRole("heading", { name: "Championship run" })).closest(
      "section",
    );
    const labels = Array.from(
      (run as HTMLElement).querySelectorAll(".match-row__label"),
      (el) => el.textContent,
    );
    // Alphabetically "Final" would come first; the API's order is kept.
    expect(labels).toEqual(["Quarterfinal", "Semifinal", "Final"]);
  });

  it("carries the replay and stream links through", async () => {
    const champion = playerSummary({ slug: "renk", username: "Renk" });
    renderHall([
      hallOfFameEntry({
        champion,
        championship_run: [
          completedMatch({
            home_player: champion,
            away_player: playerSummary({ slug: "x", username: "Foe" }),
            winner_id: champion.id,
            youtube_url: "https://example.invalid/vod",
            games: [
              { id: "g1", game_number: 1, completed_at: "2025-01-01T00:00:00Z", winner_id: champion.id, home_pokemon_score: null, away_pokemon_score: null, replay_url: "https://example.invalid/g1" },
              { id: "g2", game_number: 2, completed_at: "2025-01-01T00:10:00Z", winner_id: champion.id, home_pokemon_score: null, away_pokemon_score: null, replay_url: "https://example.invalid/g2" },
            ],
          }),
        ],
      }),
    ]);

    expect((await screen.findAllByRole("link", { name: "Replay" }))[0]).toHaveAttribute(
      "href",
      "https://example.invalid/g1",
    );
    expect(screen.getByRole("link", { name: /Video/ })).toHaveAttribute(
      "href",
      "https://example.invalid/vod",
    );
  });

  it("says when a run has no matches recorded", async () => {
    renderHall([hallOfFameEntry({ championship_run: [] })]);

    expect(
      await screen.findByText("No playoff matches were recorded for this run."),
    ).toBeInTheDocument();
  });

  it("keeps the line breaks in a championship write-up", async () => {
    const description = "Wire to wire.\n\nNever trailed a series.";
    renderHall([hallOfFameEntry({ description })]);

    expect((await screen.findByText(/Wire to wire/)).textContent).toBe(description);
  });

  it("labels a description borrowed from the season overview", async () => {
    renderHall([
      hallOfFameEntry({ description: "The first season.", description_is_fallback: true }),
    ]);

    expect(await screen.findByText(/From the season overview/)).toBeInTheDocument();
  });

  it("says so when there is no write-up at all", async () => {
    renderHall([hallOfFameEntry({ description: null })]);

    expect(await screen.findByText(/No write-up has been added/)).toBeInTheDocument();
  });
});
