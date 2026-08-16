/** Canonical paths, in one place.
 *
 * Every link in the app goes through these, so the canonical form of a URL is
 * decided once. The legacy `/players/:uuid` and `/seasons/:uuid` routes still
 * resolve - they redirect - but nothing should be *building* them any more.
 */

export function playerPath(slug: string): string {
  return `/player/${slug}`;
}

export function seasonPath(slug: string): string {
  return `/seasons/${slug}`;
}

export function seasonStandingsPath(slug: string): string {
  return `/seasons/${slug}/standings`;
}

export const STANDINGS_PATH = "/standings";
export const HALL_OF_FAME_PATH = "/hall-of-fame";
