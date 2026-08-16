import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PlainText from "./PlainText";

describe("PlainText", () => {
  it("keeps the newlines an administrator typed", () => {
    const body = "Matchday 1\nSaturday 20:00\nSunday 18:00";
    render(<PlainText>{body}</PlainText>);

    // textContent, not the accessible name: getByText collapses whitespace, so
    // it would pass even if the newlines had been stripped.
    expect(screen.getByText(/Matchday 1/).textContent).toBe(body);
  });

  it("preserves blank lines between paragraphs", () => {
    const body = "First paragraph.\n\nSecond paragraph.";
    render(<PlainText>{body}</PlainText>);

    expect(screen.getByText(/First paragraph/).textContent).toBe(body);
  });

  it("renders with pre-wrap so the newlines are actually visible", () => {
    render(<PlainText>{"a\nb"}</PlainText>);

    // The class carries `white-space: pre-wrap`; without it the DOM would hold
    // the newline but the browser would collapse it to a space.
    expect(screen.getByText(/a/)).toHaveClass("plain-text");
  });

  it("does not turn administrator input into markup", () => {
    const body = "<script>alert(1)</script> **not bold**";
    const { container } = render(<PlainText>{body}</PlainText>);

    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/alert/).textContent).toBe(body);
  });

  it("accepts an extra class without losing the pre-wrap one", () => {
    render(<PlainText className="player-page__biography">text</PlainText>);

    const element = screen.getByText("text");
    expect(element).toHaveClass("plain-text");
    expect(element).toHaveClass("player-page__biography");
  });
});
