import { Link } from "react-router-dom";

import { seasonStandingsPath } from "../lib/routes";
import type { ChampionshipRead } from "../types";

interface ChampionBadgeProps {
  championships: ChampionshipRead[];
}

/** "Champion", or "3× Champion" once there is more than one. */
function championLabel(count: number): string {
  return count > 1 ? `${count}× Champion` : "Champion";
}

/**
 * A player's championship marker.
 *
 * The star is decorative - `aria-hidden`, with the count spelled out in text
 * beside it - because an icon alone tells a screen reader nothing and tells a
 * sighted visitor only that *something* is special. The seasons won are listed
 * and linked, so the badge is checkable rather than asserted.
 *
 * Renders nothing when the list is empty, which is also how a placeholder
 * player (whose championships the API returns as empty) ends up with no badge.
 */
export default function ChampionBadge({ championships }: ChampionBadgeProps) {
  if (championships.length === 0) {
    return null;
  }

  return (
    <div className="champion-badge">
      <p className="champion-badge__title">
        <span className="champion-badge__star" aria-hidden="true">
          ★
        </span>
        <strong>{championLabel(championships.length)}</strong>
      </p>
      <ul className="champion-badge__seasons">
        {championships.map((championship) => (
          <li key={championship.season_id}>
            <Link to={seasonStandingsPath(championship.season_slug)}>
              {championship.season_name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
