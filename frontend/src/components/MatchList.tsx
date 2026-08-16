import type { MatchRead } from "../types";
import MatchRow from "./MatchRow";

interface MatchListProps {
  matches: MatchRead[];
  perspectiveId?: string;
  /** What to say when there are none. */
  empty: string;
  /** Per-match label, e.g. the round name or the group/matchday. */
  labelFor?: (match: MatchRead) => string | null;
  /** Marks a match as administrator-featured. */
  featuredFor?: (match: MatchRead) => boolean;
}

/** A list of matches, or a plain sentence when there are none.
 *
 * The empty state is a real answer rather than an absent section - "no matches
 * this week" tells a visitor something; a missing list does not.
 */
export default function MatchList({
  matches,
  perspectiveId,
  empty,
  labelFor,
  featuredFor,
}: MatchListProps) {
  if (matches.length === 0) {
    return <p className="match-list__empty">{empty}</p>;
  }

  return (
    <ul className="match-list">
      {matches.map((match) => (
        <MatchRow
          key={match.id}
          match={match}
          perspectiveId={perspectiveId}
          label={labelFor?.(match) ?? null}
          featured={featuredFor?.(match) ?? false}
        />
      ))}
    </ul>
  );
}
