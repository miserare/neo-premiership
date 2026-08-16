import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { completedMatch, match } from "../test/factories";
import { renderWithRouter } from "../test/render";
import type { MatchRead } from "../types";
import AdminMatchesPage from "./AdminMatchesPage";

// vi.mock factories are hoisted above module-level consts, so anything they
// close over has to be hoisted too - otherwise the factory runs while these are
// still in their temporal dead zone.
const { home, away, listBySeason, setResult, updateMatch } = vi.hoisted(() => ({
  home: {
    id: "player-home",
    slug: "psykick",
    username: "Psykick",
    elo_rating: 1000,
    is_active: true,
  },
  away: {
    id: "player-away",
    slug: "renk",
    username: "Renk",
    elo_rating: 1000,
    is_active: true,
  },
  listBySeason: vi.fn(),
  setResult: vi.fn(),
  updateMatch: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      seasons: {
        list: async () => [
          { id: "s1", slug: "7", name: "Season 7", start_date: "2026-08-13", end_date: null, champion: null },
        ],
        roster: {
          list: async () => [
            { id: "e1", player: home, group_label: null, tiebreaker_value: null, pokemon: [], former_pokemon: [] },
            { id: "e2", player: away, group_label: null, tiebreaker_value: null, pokemon: [], former_pokemon: [] },
          ],
        },
        playoffRounds: { list: async () => [] },
      },
      matches: {
        listBySeason: (...args: unknown[]) => listBySeason(...args),
        setResult: (...args: unknown[]) => setResult(...args),
        update: (...args: unknown[]) => updateMatch(...args),
        create: vi.fn(),
        delete: vi.fn(),
      },
    },
  };
});

function scheduledMatch(overrides: Partial<MatchRead> = {}): MatchRead {
  return match({
    id: "m1",
    season_id: "s1",
    home_player: home,
    away_player: away,
    round_label: "Group A - Matchday 1",
    ...overrides,
  });
}

beforeEach(() => {
  listBySeason.mockResolvedValue([scheduledMatch()]);
});

afterEach(() => vi.clearAllMocks());

/** Open the match's editor. */
async function openEditor(user: ReturnType<typeof userEvent.setup>) {
  renderWithRouter(<AdminMatchesPage />);
  await screen.findByText("Psykick vs Renk");
  await user.click(screen.getByRole("button", { name: "Edit" }));
}

async function addGame(user: ReturnType<typeof userEvent.setup>, winner: string, index: number) {
  await user.click(screen.getByRole("button", { name: "Add game" }));
  await user.selectOptions(screen.getByLabelText(`Game ${index} winner`), winner);
}

describe("AdminMatchesPage result form", () => {
  it("presents one result form with a single save button", async () => {
    const user = userEvent.setup();
    await openEditor(user);

    expect(screen.getByRole("heading", { name: "Enter result" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save result" })).toBeInTheDocument();
    // The old three-save workflow is gone.
    expect(screen.queryByRole("button", { name: "Save games" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save teams" })).not.toBeInTheDocument();
  });

  it("says Edit result for a match that already has one", async () => {
    const user = userEvent.setup();
    listBySeason.mockResolvedValue([
      completedMatch({ id: "m1", season_id: "s1", home_player: home, away_player: away }),
    ]);
    await openEditor(user);

    expect(screen.getByRole("heading", { name: "Edit result" })).toBeInTheDocument();
  });

  it("numbers games automatically as they are added and removed", async () => {
    const user = userEvent.setup();
    await openEditor(user);

    await user.click(screen.getByRole("button", { name: "Add game" }));
    await user.click(screen.getByRole("button", { name: "Add game" }));
    await user.click(screen.getByRole("button", { name: "Add game" }));
    expect(screen.getByLabelText("Game 3 winner")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Remove game 2/ }));
    // Renumbered, not left with a gap.
    expect(screen.queryByLabelText("Game 3 winner")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Game 2 winner")).toBeInTheDocument();
  });

  it("shows the derived series score and winner before saving", async () => {
    const user = userEvent.setup();
    await openEditor(user);

    await addGame(user, home.id, 1);
    await addGame(user, away.id, 2);
    await addGame(user, home.id, 3);

    const derived = document.querySelector(".admin-result-form__derived");
    expect(derived?.textContent).toContain("Psykick 2 - 1 Renk");
    expect(derived?.textContent).toContain("Winner: Psykick");
  });

  it("names a level series as undecided rather than picking one", async () => {
    const user = userEvent.setup();
    await openEditor(user);

    await addGame(user, home.id, 1);
    await addGame(user, away.id, 2);

    expect(document.querySelector(".admin-result-form__derived")?.textContent).toContain(
      "level at 1-1",
    );
  });

  it("refuses to complete a level series, before sending anything", async () => {
    const user = userEvent.setup();
    await openEditor(user);

    await addGame(user, home.id, 1);
    await addGame(user, away.id, 2);
    await user.click(screen.getByLabelText("This match is complete"));
    await user.click(screen.getByRole("button", { name: "Save result" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("level at 1-1");
    expect(setResult).not.toHaveBeenCalled();
  });

  it("refuses to complete with no games", async () => {
    const user = userEvent.setup();
    await openEditor(user);

    await user.click(screen.getByLabelText("This match is complete"));
    await user.click(screen.getByRole("button", { name: "Save result" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("at least one game");
    expect(setResult).not.toHaveBeenCalled();
  });

  it("refuses to complete while a game has no winner", async () => {
    const user = userEvent.setup();
    await openEditor(user);

    await addGame(user, home.id, 1);
    await user.click(screen.getByRole("button", { name: "Add game" }));
    await user.click(screen.getByLabelText("This match is complete"));
    await user.click(screen.getByRole("button", { name: "Save result" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Every game needs a winner");
    expect(setResult).not.toHaveBeenCalled();
  });

  it("sends games, both teams and status in one request", async () => {
    const user = userEvent.setup();
    setResult.mockResolvedValue(
      completedMatch({ id: "m1", season_id: "s1", home_player: home, away_player: away }),
    );
    await openEditor(user);

    await addGame(user, home.id, 1);
    await addGame(user, home.id, 2);
    await user.type(
      screen.getByLabelText("Game 1 replay URL"),
      "https://example.invalid/g1",
    );
    await user.click(screen.getByLabelText("This match is complete"));
    await user.type(screen.getByLabelText("Completed at"), "2026-08-15T20:00");
    await user.click(screen.getByRole("button", { name: "Save result" }));

    await waitFor(() => expect(setResult).toHaveBeenCalledTimes(1));
    const [matchId, payload] = setResult.mock.calls[0];
    expect(matchId).toBe("m1");
    expect(payload.status).toBe("completed");
    expect(payload.games).toEqual([
      { game_number: 1, winner_id: home.id, replay_url: "https://example.invalid/g1" },
      { game_number: 2, winner_id: home.id, replay_url: null },
    ]);
    expect(payload).toHaveProperty("home_team");
    expect(payload).toHaveProperty("away_team");
    // The score and winner are never sent - the server derives them.
    expect(payload).not.toHaveProperty("home_score");
    expect(payload).not.toHaveProperty("winner_id");
  });

  it("saves an in-progress series as still scheduled", async () => {
    const user = userEvent.setup();
    setResult.mockResolvedValue(scheduledMatch());
    await openEditor(user);

    await addGame(user, home.id, 1);
    await user.click(screen.getByRole("button", { name: "Save result" }));

    await waitFor(() => expect(setResult).toHaveBeenCalled());
    expect(setResult.mock.calls[0][1].status).toBe("scheduled");
    expect(setResult.mock.calls[0][1].completed_at).toBeNull();
  });

  it("keeps the entered games when the server rejects the save", async () => {
    const user = userEvent.setup();
    setResult.mockRejectedValue(new ApiError(422, "This series is level at 1-1."));
    await openEditor(user);

    await addGame(user, home.id, 1);
    await user.click(screen.getByRole("button", { name: "Save result" }));

    expect(await screen.findByText("This series is level at 1-1.")).toBeInTheDocument();
    // Nothing is re-entered.
    expect(screen.getByLabelText("Game 1 winner")).toHaveValue(home.id);
  });

  it("disables the save button while the request is in flight", async () => {
    const user = userEvent.setup();
    setResult.mockImplementation(() => new Promise(() => {}));
    await openEditor(user);

    await addGame(user, home.id, 1);
    await user.click(screen.getByRole("button", { name: "Save result" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled());
  });

  it("keeps scheduling separate, and does not touch the recorded result", async () => {
    const user = userEvent.setup();
    updateMatch.mockResolvedValue(scheduledMatch({ round_label: "Group B - Matchday 4" }));
    await openEditor(user);

    await user.click(screen.getByRole("button", { name: "Save scheduling" }));

    await waitFor(() => expect(updateMatch).toHaveBeenCalled());
    const payload = updateMatch.mock.calls[0][1];
    // Scheduling saves carry no games, teams, scores or winner.
    expect(payload).not.toHaveProperty("games");
    expect(payload).not.toHaveProperty("home_team");
    expect(payload).not.toHaveProperty("winner_id");
    expect(setResult).not.toHaveBeenCalled();
  });

  it("offers the homepage highlighting controls", async () => {
    const user = userEvent.setup();
    updateMatch.mockResolvedValue(scheduledMatch({ featured_on_homepage: true }));
    await openEditor(user);

    await user.click(screen.getByLabelText("Feature on the home page"));
    await user.type(screen.getByLabelText("Feature position"), "2");
    await user.click(screen.getByRole("button", { name: "Save scheduling" }));

    await waitFor(() => expect(updateMatch).toHaveBeenCalled());
    expect(updateMatch.mock.calls[0][1].featured_on_homepage).toBe(true);
    expect(updateMatch.mock.calls[0][1].homepage_feature_order).toBe(2);
  });

  it("keeps the editor open and the list intact after a save", async () => {
    const user = userEvent.setup();
    setResult.mockResolvedValue(
      completedMatch({ id: "m1", season_id: "s1", home_player: home, away_player: away }),
    );
    await openEditor(user);

    await addGame(user, home.id, 1);
    await user.click(screen.getByRole("button", { name: "Save result" }));

    await waitFor(() => expect(setResult).toHaveBeenCalled());
    // No reload, no collapse: the form is still open over the same list.
    expect(screen.getByRole("heading", { name: /result/i })).toBeInTheDocument();
    expect(screen.queryByText("Loading matches...")).not.toBeInTheDocument();
    expect(listBySeason).toHaveBeenCalledTimes(1);
  });

  it("marks a featured match in the list", async () => {
    listBySeason.mockResolvedValue([scheduledMatch({ featured_on_homepage: true })]);
    renderWithRouter(<AdminMatchesPage />);

    const card = (await screen.findByText("Psykick vs Renk")).closest(".admin-match-card");
    expect(within(card as HTMLElement).getByText(/featured/)).toBeInTheDocument();
  });
});
