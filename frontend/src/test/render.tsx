import { render, type RenderResult } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

/** Render inside a router, since almost everything here contains a <Link>. */
export function renderWithRouter(
  ui: React.ReactNode,
  { route = "/" }: { route?: string } = {},
): RenderResult {
  return render(<MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>);
}

/**
 * Render a page at a real route, with a catch-all that reports where a redirect
 * landed. Tests for the legacy-URL redirects assert on that marker rather than
 * on router internals.
 */
export function renderAtRoute(
  path: string,
  element: React.ReactNode,
  { route, extraRoutes }: { route: string; extraRoutes?: React.ReactNode },
): RenderResult {
  return render(
    <MemoryRouter initialEntries={[route]}>
      {/* Outside <Routes>, so it reports the location whatever matched -
          including a redirect to a different URL under the same pattern. */}
      <LandedAt />
      <Routes>
        <Route path={path} element={element} />
        {extraRoutes}
      </Routes>
    </MemoryRouter>,
  );
}

/** Reports the path a navigation ended on, for redirect assertions.
 *
 * Reads the router's own location rather than window.location: MemoryRouter
 * keeps its history in memory and never touches the address bar. */
export function LandedAt() {
  const location = useLocation();
  return <div data-testid="landed-at">{location.pathname}</div>;
}
