import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { pageTitle, useDocumentTitle } from "./useDocumentTitle";

function Titled({ title }: { title?: string | null }) {
  useDocumentTitle(title);
  return <p>page</p>;
}

describe("pageTitle", () => {
  it("suffixes the league name", () => {
    expect(pageTitle("Players")).toBe("Players | Pokémon Premiership");
    expect(pageTitle("Season 6 Standings")).toBe("Season 6 Standings | Pokémon Premiership");
  });

  it("is just the league name at the root", () => {
    expect(pageTitle()).toBe("Pokémon Premiership");
    expect(pageTitle("   ")).toBe("Pokémon Premiership");
  });
});

describe("useDocumentTitle", () => {
  it("sets the title while mounted", () => {
    render(<Titled title="Players" />);
    expect(document.title).toBe("Players | Pokémon Premiership");
  });

  it("updates when the title changes", () => {
    const { rerender } = render(<Titled title="Players" />);
    rerender(<Titled title="Psykick" />);
    expect(document.title).toBe("Psykick | Pokémon Premiership");
  });

  it("leaves the title alone while it is still unknown", () => {
    document.title = "Pokémon Premiership";
    // null means "still loading" - a page that guessed here would flash the
    // bare site name and then replace it.
    render(<Titled title={null} />);
    expect(document.title).toBe("Pokémon Premiership");
  });

  it("restores the previous title on unmount", () => {
    document.title = "Pokémon Premiership";
    const { unmount } = render(<Titled title="Players" />);
    expect(document.title).toBe("Players | Pokémon Premiership");

    unmount();
    expect(document.title).toBe("Pokémon Premiership");
  });

  it("does not clobber a title another route has already set", () => {
    // React mounts the incoming route before unmounting the outgoing one, so
    // the old page's cleanup runs last. It must not undo the new page's title.
    const first = render(<Titled title="Players" />);
    const second = render(<Titled title="Hall of Fame" />);
    expect(document.title).toBe("Hall of Fame | Pokémon Premiership");

    first.unmount();
    expect(document.title).toBe("Hall of Fame | Pokémon Premiership");

    second.unmount();
  });
});
