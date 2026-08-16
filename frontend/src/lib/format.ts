import type { MatchRead } from "../types";

/** Date and time rendering, in one place.
 *
 * These were duplicated across the player, season and home pages, which is how
 * the same timestamp ended up formatted three slightly different ways. All of
 * them render in the *viewer's* locale and zone deliberately: the league week
 * is computed server-side in the league's zone, but a visitor reading "when is
 * my match" wants their own clock.
 */

const DATE_ONLY: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "short",
  day: "numeric",
};

const DATE_AND_TIME: Intl.DateTimeFormatOptions = {
  ...DATE_ONLY,
  hour: "numeric",
  minute: "2-digit",
};

export function formatDate(iso: string | null, fallback = "TBD"): string {
  if (!iso) return fallback;
  return new Date(iso).toLocaleDateString(undefined, DATE_ONLY);
}

export function formatDateTime(iso: string | null, fallback = "TBD"): string {
  if (!iso) return fallback;
  return new Date(iso).toLocaleString(undefined, DATE_AND_TIME);
}

/** A date range like "31 May 2024 - present". */
export function formatDateRange(start: string, end: string | null): string {
  return `${formatDate(start)} - ${end ? formatDate(end) : "present"}`;
}

/** The timestamp that matters for a match: when it finished if it has, when it
 * is due otherwise. */
export function matchTimestamp(match: MatchRead): string | null {
  return match.status === "completed" ? match.completed_at : match.scheduled_at;
}
