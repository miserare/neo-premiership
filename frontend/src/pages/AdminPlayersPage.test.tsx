import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { renderWithRouter } from "../test/render";
import type { PlayerAdmin } from "../types";
import AdminPlayersPage from "./AdminPlayersPage";

function admin(overrides: Partial<PlayerAdmin> = {}): PlayerAdmin {
  return {
    id: "p1",
    slug: "psykick",
    username: "Psykick",
    biography: null,
    join_date: "2024-01-01T00:00:00Z",
    is_active: true,
    elo_rating: 1000,
    discord_id: null,
    initial_elo_rating: 1000,
    ...overrides,
  };
}

const listAdmin = vi.fn();
const update = vi.fn();
const create = vi.fn();

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: {
      players: {
        listAdmin: (...args: unknown[]) => listAdmin(...args),
        update: (...args: unknown[]) => update(...args),
        create: (...args: unknown[]) => create(...args),
        delete: vi.fn(),
      },
    },
  };
});

beforeEach(() => {
  listAdmin.mockResolvedValue([admin(), admin({ id: "p2", slug: "renk", username: "Renk" })]);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminPlayersPage saves", () => {
  it("keeps the table on screen while a save is in flight", async () => {
    const user = userEvent.setup();
    let resolveUpdate!: (value: PlayerAdmin) => void;
    update.mockImplementation(() => new Promise<PlayerAdmin>((res) => (resolveUpdate = res)));

    renderWithRouter(<AdminPlayersPage />);
    await screen.findByText("Psykick");

    await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    await user.click(screen.getByRole("button", { name: "Save" }));

    // The whole point of section 7: a save must not replace the page with an
    // initial loading state.
    expect(screen.queryByText("Loading players...")).not.toBeInTheDocument();
    expect(screen.getByText("Renk")).toBeInTheDocument();

    resolveUpdate(admin({ username: "Psykick" }));
    await waitFor(() => expect(screen.getByText("Player saved.")).toBeInTheDocument());
  });

  it("puts only the submitted control into a pending state", async () => {
    const user = userEvent.setup();
    update.mockImplementation(() => new Promise<PlayerAdmin>(() => {}));

    renderWithRouter(<AdminPlayersPage />);
    await screen.findByText("Psykick");

    await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Saving..." })).toBeDisabled());
    // The create form's button is a different control and stays usable.
    expect(screen.getByRole("button", { name: "Create player" })).toBeEnabled();
  });

  it("updates the row from the save response without refetching", async () => {
    const user = userEvent.setup();
    update.mockResolvedValue(admin({ username: "Psykick Renamed" }));

    renderWithRouter(<AdminPlayersPage />);
    await screen.findByText("Psykick");
    expect(listAdmin).toHaveBeenCalledTimes(1);

    await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByText("Psykick Renamed")).toBeInTheDocument());
    // No second list request: the mutation's own response is the new state.
    expect(listAdmin).toHaveBeenCalledTimes(1);
  });

  it("announces success in a live region", async () => {
    const user = userEvent.setup();
    update.mockResolvedValue(admin());

    renderWithRouter(<AdminPlayersPage />);
    await screen.findByText("Psykick");

    await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    await user.click(screen.getByRole("button", { name: "Save" }));

    const live = await screen.findByText("Player saved.");
    expect(live).toHaveAttribute("aria-live", "polite");
  });

  it("keeps entered values when a save fails", async () => {
    const user = userEvent.setup();
    create.mockRejectedValue(new ApiError(409, "Username already taken"));

    renderWithRouter(<AdminPlayersPage />);
    await screen.findByText("Psykick");

    await user.type(screen.getByLabelText("Username"), "Doodle");
    await user.type(screen.getByLabelText("Biography"), "A long story.");
    await user.click(screen.getByRole("button", { name: "Create player" }));

    expect(await screen.findByText("Username already taken")).toBeInTheDocument();
    // Nothing is retyped: the form still holds what was entered.
    expect(screen.getByLabelText("Username")).toHaveValue("Doodle");
    expect(screen.getByLabelText("Biography")).toHaveValue("A long story.");
  });

  it("does not send a second request when Save is double-clicked", async () => {
    const user = userEvent.setup();
    update.mockImplementation(() => new Promise<PlayerAdmin>(() => {}));

    renderWithRouter(<AdminPlayersPage />);
    await screen.findByText("Psykick");

    await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    const save = screen.getByRole("button", { name: "Save" });
    await user.dblClick(save);

    expect(update).toHaveBeenCalledTimes(1);
  });

  it("omits an untouched slug so a rename cannot rewrite the URL", async () => {
    const user = userEvent.setup();
    create.mockResolvedValue(admin({ id: "p3", slug: "new-player", username: "New Player" }));

    renderWithRouter(<AdminPlayersPage />);
    await screen.findByText("Psykick");

    await user.type(screen.getByLabelText("Username"), "New Player");
    await user.click(screen.getByRole("button", { name: "Create player" }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0].slug).toBeUndefined();
  });

  it("shows each player's slug in the table", async () => {
    renderWithRouter(<AdminPlayersPage />);

    const row = (await screen.findByText("Psykick")).closest("tr");
    expect(within(row as HTMLElement).getByText("psykick")).toBeInTheDocument();
  });
});
