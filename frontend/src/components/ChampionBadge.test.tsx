import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithRouter } from "../test/render";
import type { ChampionshipRead } from "../types";
import ChampionBadge from "./ChampionBadge";

function championship(overrides: Partial<ChampionshipRead> = {}): ChampionshipRead {
  return {
    season_id: "s1",
    season_slug: "4",
    season_name: "Season 4",
    start_date: "2025-06-14",
    end_date: "2025-08-02",
    ...overrides,
  };
}

describe("ChampionBadge", () => {
  it("says Champion in words, not just with a star", () => {
    renderWithRouter(<ChampionBadge championships={[championship()]} />);

    expect(screen.getByText("Champion")).toBeInTheDocument();
  });

  it("counts multiple titles", () => {
    renderWithRouter(
      <ChampionBadge
        championships={[
          championship({ season_id: "a", season_slug: "4", season_name: "Season 4" }),
          championship({ season_id: "b", season_slug: "3", season_name: "Season 3" }),
          championship({ season_id: "c", season_slug: "1", season_name: "Season 1" }),
        ]}
      />,
    );

    expect(screen.getByText("3× Champion")).toBeInTheDocument();
  });

  it("hides the star from assistive technology", () => {
    const { container } = renderWithRouter(<ChampionBadge championships={[championship()]} />);

    const star = container.querySelector(".champion-badge__star");
    // The star is decoration; the text beside it carries the meaning, so a
    // screen reader should not announce it as content.
    expect(star).toHaveAttribute("aria-hidden", "true");
  });

  it("links each season won to its standings", () => {
    renderWithRouter(
      <ChampionBadge
        championships={[
          championship({ season_id: "a", season_slug: "4", season_name: "Season 4" }),
          championship({ season_id: "b", season_slug: "3", season_name: "Season 3" }),
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: "Season 4" })).toHaveAttribute(
      "href",
      "/seasons/4/standings",
    );
    expect(screen.getByRole("link", { name: "Season 3" })).toHaveAttribute(
      "href",
      "/seasons/3/standings",
    );
  });

  it("renders nothing for a player who has won nothing", () => {
    const { container } = renderWithRouter(<ChampionBadge championships={[]} />);

    // This is also how the placeholder player avoids a misleading badge: the
    // API returns no championships for it, so there is nothing to render.
    expect(container).toBeEmptyDOMElement();
  });
});
