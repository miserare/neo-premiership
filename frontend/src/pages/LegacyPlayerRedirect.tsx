import { Navigate, useParams } from "react-router-dom";

import { usePlayerDetail } from "../hooks/usePlayerDetail";
import { playerPath } from "../lib/routes";

/**
 * Keeps `/players/<uuid>` links working.
 *
 * Every player URL published before slugs existed used the UUID. Those links
 * are in Discord messages, spreadsheets and bookmarks, so they resolve rather
 * than 404: the API still accepts a UUID, and this redirects to the canonical
 * slug once it knows it.
 *
 * `replace` so the UUID does not sit in the history stack - a visitor pressing
 * Back would otherwise bounce straight forward again.
 */
export default function LegacyPlayerRedirect() {
  const { playerId } = useParams<{ playerId: string }>();
  const { data: player, isLoading, error } = usePlayerDetail(playerId ?? "");

  if (isLoading) {
    return <p role="status">Loading player...</p>;
  }

  if (error || !player) {
    // A UUID that resolves to nothing is a genuine 404, not a redirect.
    return (
      <p role="alert" className="player-page__error">
        {error ?? "Player not found."}
      </p>
    );
  }

  return <Navigate to={playerPath(player.slug)} replace />;
}
