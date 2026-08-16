import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderWithRouter } from "../test/render";
import Disclosure from "./Disclosure";

function Example() {
  return (
    <Disclosure showLabel="Show all (10)" hideLabel="Show fewer">
      {(expanded) => <p>{expanded ? "everything" : "a summary"}</p>}
    </Disclosure>
  );
}

describe("Disclosure", () => {
  it("starts collapsed and reports it", () => {
    renderWithRouter(<Example />);

    const toggle = screen.getByRole("button", { name: "Show all (10)" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("a summary")).toBeInTheDocument();
  });

  it("expands on click and swaps its label", async () => {
    const user = userEvent.setup();
    renderWithRouter(<Example />);

    await user.click(screen.getByRole("button", { name: "Show all (10)" }));

    const toggle = screen.getByRole("button", { name: "Show fewer" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("everything")).toBeInTheDocument();
  });

  it("is operable from the keyboard alone", async () => {
    const user = userEvent.setup();
    renderWithRouter(<Example />);

    await user.tab();
    expect(screen.getByRole("button", { name: "Show all (10)" })).toHaveFocus();

    // Enter and Space both activate a real <button>; a clickable div would do
    // neither, which is the reason this is a button.
    await user.keyboard("{Enter}");
    expect(screen.getByText("everything")).toBeInTheDocument();

    await user.keyboard(" ");
    expect(screen.getByText("a summary")).toBeInTheDocument();
  });

  it("points the toggle at the region it controls", () => {
    renderWithRouter(<Example />);

    const toggle = screen.getByRole("button", { name: "Show all (10)" });
    const controlled = toggle.getAttribute("aria-controls");

    expect(controlled).toBeTruthy();
    expect(document.getElementById(controlled as string)).toContainElement(
      screen.getByText("a summary"),
    );
  });
});
