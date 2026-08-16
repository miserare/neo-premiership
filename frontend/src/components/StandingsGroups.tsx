import { Link } from "react-router-dom";

import { playerPath } from "../lib/routes";
import type { StandingsGroup } from "../types";

interface StandingsGroupsProps {
  groups: StandingsGroup[];
  empty?: string;
}

/**
 * The group standings tables.
 *
 * Rendered in exactly the order the API returned, both for the groups and for
 * the rows inside them - the server has already applied the league's tiebreak
 * rules, and re-sorting here would quietly replace them.
 */
export default function StandingsGroups({
  groups,
  empty = "No standings available yet.",
}: StandingsGroupsProps) {
  if (groups.length === 0) {
    return <p>{empty}</p>;
  }

  return (
    <>
      {groups.map((group) => (
        <div key={group.group_label ?? "ungrouped"} className="standings-group">
          {group.group_label && <h3>{group.group_label}</h3>}
          <div className="table-scroll">
            <table className="standings-table">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Wins</th>
                  <th>Losses</th>
                  <th>Pokémon Diff</th>
                </tr>
              </thead>
              <tbody>
                {group.standings.map((entry) => (
                  <tr key={entry.player.id}>
                    <td>
                      <Link to={playerPath(entry.player.slug)}>{entry.player.username}</Link>
                    </td>
                    <td>{entry.wins}</td>
                    <td>{entry.losses}</td>
                    <td>
                      {entry.pokemon_differential_complete && entry.pokemon_differential !== null
                        ? entry.pokemon_differential > 0
                          ? `+${entry.pokemon_differential}`
                          : entry.pokemon_differential
                        : "Not recorded"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </>
  );
}
