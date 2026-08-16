import { screen } from "@testing-library/react";
import { Route } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { playerDetail } from "../test/factories";
import { renderAtRoute } from "../test/render";
import LegacyPlayerRedirect from "./LegacyPlayerRedirect";
import PlayerDetailPage from "./PlayerDetailPage";

const get = vi.fn();

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, api: { players: { get: (...args: unknown[]) => get(...args) } } };
});

afterEach(() => vi.clearAllMocks());

const UUID = "8dc3af6a-e1d2-41f6-a8bb-b5c354dda7ee";

describe("LegacyPlayerRedirect", () => {
  it("sends an old UUID link to the canonical slug route", async () => {
    get.mockResolvedValue(playerDetail({ slug: "psykick", username: "Psykick" }));

    renderAtRoute("/players/:playerId", <LegacyPlayerRedirect />, {
      route: `/players/${UUID}`,
      extraRoutes: <Route path="/player/:playerSlug" element={<PlayerDetailPage />} />,
    });

    // It lands on the real player page, not a 404 and not a loop.
    expect(await screen.findByRole("heading", { name: "Psykick", level: 1 })).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith(UUID);
  });

  it("reports a UUID that resolves to nothing rather than redirecting", async () => {
    get.mockRejectedValue(
      new (await vi.importActual<typeof import("../lib/api")>("../lib/api")).ApiError(
        404,
        "Player not found",
      ),
    );

    renderAtRoute("/players/:playerId", <LegacyPlayerRedirect />, {
      route: "/players/00000000-0000-4000-8000-000000000000",
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Player not found");
  });
});
