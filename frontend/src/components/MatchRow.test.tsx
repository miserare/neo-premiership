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
      series: { home_wins: 2, away_wins: 1, game_count: 3 },
    });

    renderRow(<MatchRow match={played} perspectiveId={home.id} />);

    expect(screen.getByText(/vs/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Renk" })).toHaveAttribute("href", "/player/renk");
    expect(screen.getByText("Win 2-1")).toBeInTheDocument();
  });

  it("flips the score for the away player", () => {
    const played = completedMatch({
      home_player: home,
      away_player: away,
      winner_id: home.id,
      series: { home_wins: 2, away_wins: 1, game_count: 3 },
    });

    renderRow(<MatchRow match={played} perspectiveId={away.id} />);

    expect(screen.getByText("Loss 1-2")).toBeInTheDocument();
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
      series: { home_wins: 0, away_wins: 0, game_count: 0 },
      home_score: null,
      away_score: null,
    });

    renderRow(<MatchRow match={played} perspectiveId={home.id} />);

    expect(screen.getByText("Win")).toBeInTheDocument();
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
        { id: "g1", game_number: 1, winner_id: home.id, replay_url: "https://example.invalid/g1" },
        { id: "g2", game_number: 2, winner_id: away.id, replay_url: "https://example.invalid/g2" },
        { id: "g3", game_number: 3, winner_id: home.id, replay_url: "https://example.invalid/g3" },
      ],
    });

    renderRow(<MatchRow match={played} perspectiveId={home.id} />);

    expect(screen.getByRole("link", { name: /G1/ })).toHaveAttribute(
      "href",
      "https://example.invalid/g1",
    );
    expect(screen.getByRole("link", { name: /G3/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Video/ })).toHaveAttribute(
      "href",
      "https://example.invalid/vod",
    );
  });
});
