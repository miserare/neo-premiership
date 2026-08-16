import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

/** Proves the harness itself works: jsdom renders, jest-dom matchers are
 * registered, and cleanup runs between tests. Everything else tests real
 * components. */
describe("test harness", () => {
  it("renders a component into jsdom", () => {
    render(<p>rendered</p>);
    expect(screen.getByText("rendered")).toBeInTheDocument();
  });

  it("cleans the DOM up between tests", () => {
    expect(screen.queryByText("rendered")).not.toBeInTheDocument();
  });
});
