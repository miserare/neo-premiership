import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SiteCreatorBadge from "./SiteCreatorBadge";

describe("SiteCreatorBadge", () => {
  it("has a visible accessible name", () => {
    render(<SiteCreatorBadge />);
    expect(screen.getByLabelText("Site Creator")).toHaveTextContent("Site Creator");
  });
});
