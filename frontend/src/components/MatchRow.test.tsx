import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { completedMatch, match, playerSummary } from "../test/factories";
import { renderWithRouter } from "../test/render";
import MatchRow from "./MatchRow";

const home = playerSummary({ slug: "psykick", username: "Psykick" });
const away = playerSummary({ slug: "renk", username: "Renk" });

function renderRow(node: React.ReactNode) {
  return renderWithRouter(<ul>{node}</ul>);
}

describe("MatchRow", () => {
  it("tells the story from the given player's side", () => {
    const played = completedMatch({
      home_player: home,
      away_player: away,
      winner_id: home.id,
      series: { home_series_wins: 2, away_series_wins: 1, game_count: 3, wins_required: 2 },
    });

    renderRow(<MatchRow match={played} perspectiveId={home.id} />);

    expect(screen.getByText(/vs/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Renk" })).toHaveAttribute("href", "/player/renk");
    expect(screen.getByText(/Win · Series: 2–1/)).toBeInTheDocument();
  });

  it("flips the score for the away player", () => {
    const played = completedMatch({
      home_player: home,
      away_player: away,
      winner_id: home.id,
      series: { home_series_wins: 2, away_series_wins: 1, game_count: 3, wins_required: 2 },
    });

    renderRow(<MatchRow match={played} perspectiveId={away.id} />);

    expect(screen.getByText(/Loss · Series: 1–2/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Psykick" })).toBeInTheDocument();
  });

  it("reads neutrally when no perspective is given", () => {
    renderRow(<MatchRow match={match({ home_player: home, away_player: away })} />);

    // Both players are linked, and neither is "the" player.
    expect(screen.getByRole("link", { name: "Psykick" })).toHaveAttribute("href", "/player/psykick");
    expect(screen.getByRole("link", { name: "Renk" })).toHaveAttribute("href", "/player/renk");
    expect(screen.queryByText(/^Win/)).not.toBeInTheDocument();
  });

  it("reads as a bare Win when no score was recorded", () => {
    const played = completedMatch({
      home_player: home,
      away_player: away,
      winner_id: home.id,
      series: { home_series_wins: 0, away_series_wins: 0, game_count: 0, wins_required: 2 },
    });

    renderRow(<MatchRow match={played} perspectiveId={home.id} />);

    expect(screen.getByText(/Win · Series: 0–0/)).toBeInTheDocument();
  });

  it("shows scheduled status for an upcoming match", () => {
    renderRow(<MatchRow match={match({ home_player: home, away_player: away })} />);

    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("marks a featured match with a word, not only a colour", () => {
    renderRow(
      <MatchRow match={match({ featured_on_homepage: true })} featured label="Group A" />,
    );

    expect(screen.getByText("Featured")).toBeInTheDocument();
    expect(screen.getByText("Group A")).toBeInTheDocument();
  });

  it("links every game replay and the stream", () => {
    const played = completedMatch({
      home_player: home,
      away_player: away,
      youtube_url: "https://example.invalid/vod",
      games: [
        { id: "g1", game_number: 1, completed_at: "2025-01-01T00:00:00Z", winner_id: home.id, home_pokemon_score: 6, away_pokemon_score: 0, replay_url: "https://example.invalid/g1" },
        { id: "g2", game_number: 2, completed_at: "2025-01-01T00:10:00Z", winner_id: away.id, home_pokemon_score: 0, away_pokemon_score: 1, replay_url: "https://example.invalid/g2" },
        { id: "g3", game_number: 3, completed_at: "2025-01-01T00:20:00Z", winner_id: home.id, home_pokemon_score: 2, away_pokemon_score: 0, replay_url: "https://example.invalid/g3" },
      ],
    });

    renderRow(<MatchRow match={played} perspectiveId={home.id} />);

    expect(screen.getAllByRole("link", { name: "Replay" })[0]).toHaveAttribute(
      "href",
      "https://example.invalid/g1",
    );
    expect(screen.getAllByRole("link", { name: "Replay" })).toHaveLength(3);
    expect(screen.getByRole("link", { name: /Video/ })).toHaveAttribute(
      "href",
      "https://example.invalid/vod",
    );
  });
});
