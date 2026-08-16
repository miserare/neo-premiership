import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";

import ErrorBoundary from "./components/ErrorBoundary";
import NavSearch from "./components/NavSearch";
import { HALL_OF_FAME_PATH, STANDINGS_PATH } from "./lib/routes";
import AdminAccountPage from "./pages/AdminAccountPage";
import AdminLayout from "./pages/AdminLayout";
import AdminMatchesPage from "./pages/AdminMatchesPage";
import AdminPlayoffRoundsPage from "./pages/AdminPlayoffRoundsPage";
import AdminPlayersPage from "./pages/AdminPlayersPage";
import AdminSeasonRosterPage from "./pages/AdminSeasonRosterPage";
import AdminSeasonsPage from "./pages/AdminSeasonsPage";
import AdminSitePage from "./pages/AdminSitePage";
import HallOfFamePage from "./pages/HallOfFamePage";
import HomePage from "./pages/HomePage";
import LegacyPlayerRedirect from "./pages/LegacyPlayerRedirect";
import NotFoundPage from "./pages/NotFoundPage";
import PlayerDetailPage from "./pages/PlayerDetailPage";
import PlayersPage from "./pages/PlayersPage";
import SeasonDetailPage from "./pages/SeasonDetailPage";
import SeasonsPage from "./pages/SeasonsPage";
import StandingsPage from "./pages/StandingsPage";

export default function App() {
  const location = useLocation();
  // The admin area is deliberately not linked from the public nav; search has
  // nothing to act on there either.
  const isAdminRoute = location.pathname.startsWith("/admin");

  return (
    <div className="app">
      <nav className="app__nav">
        <div className="app__nav-links">
          <Link to="/" className="app__brand">
            {/* alt="" - the wordmark beside it already names the league, so
                announcing the mark too would just repeat it. */}
            <img src="/logo.png" alt="" className="app__brand-mark" width={38} height={40} />
            <span>Pokémon Premiership</span>
          </Link>
          <Link to="/players">Players</Link>
          <Link to="/seasons">Seasons</Link>
          <Link to={STANDINGS_PATH}>Standings</Link>
          <Link to={HALL_OF_FAME_PATH}>Hall of Fame</Link>
        </div>
        {!isAdminRoute && <NavSearch />}
      </nav>
      <main className="app__main">
        {/* Inside the router so the boundary's recovery links can navigate. */}
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/players" element={<PlayersPage />} />
            {/* Canonical player route. Singular, because it addresses one
                player; /players remains the index. */}
            <Route path="/player/:playerSlug" element={<PlayerDetailPage />} />
            {/* Legacy UUID links, kept working: resolves the player and
                redirects to their canonical slug rather than 404ing. */}
            <Route path="/players/:playerId" element={<LegacyPlayerRedirect />} />
            <Route path="/seasons" element={<SeasonsPage />} />
            <Route path={STANDINGS_PATH} element={<StandingsPage />} />
            {/* Accepts a slug or a legacy UUID; the page redirects a UUID to
                the canonical slug form. */}
            <Route path="/seasons/:seasonRef/standings" element={<StandingsPage />} />
            <Route path="/seasons/:seasonRef" element={<SeasonDetailPage />} />
            <Route path={HALL_OF_FAME_PATH} element={<HallOfFamePage />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="players" replace />} />
              <Route path="players" element={<AdminPlayersPage />} />
              <Route path="seasons" element={<AdminSeasonsPage />} />
              <Route path="seasons/:seasonId" element={<AdminSeasonRosterPage />} />
              <Route path="matches" element={<AdminMatchesPage />} />
              <Route path="playoff-rounds" element={<AdminPlayoffRoundsPage />} />
              <Route path="site" element={<AdminSitePage />} />
              <Route path="account" element={<AdminAccountPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
      </main>
      <footer className="app__footer">
        <p>
          Pokémon and Pokémon character names are trademarks of Nintendo, Creatures Inc. and
          GAME FREAK Inc. This is an unofficial, non-commercial fan project and is not affiliated
          with or endorsed by them.
        </p>
        <p>
          Sprites courtesy of{" "}
          <a href="https://pokeapi.co/" target="_blank" rel="noreferrer noopener">
            PokeAPI
          </a>
          .
        </p>
      </footer>
    </div>
  );
}
