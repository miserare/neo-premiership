import { useEffect } from "react";

export const SITE_NAME = "Pokémon Premiership";

/** "Players | Pokémon Premiership", or just the site name at the root. */
export function pageTitle(title?: string | null): string {
  const trimmed = title?.trim();
  return trimmed ? `${trimmed} | ${SITE_NAME}` : SITE_NAME;
}

/**
 * Set the document title for as long as this component is mounted.
 *
 * Passing `null` means "not known yet" and leaves the title alone, so a page
 * that has to load before it knows its title does not flash the site name and
 * then replace it. Passing `undefined` (or nothing) sets the bare site name,
 * which is what the home page wants.
 *
 * The previous title is restored on unmount. During client-side navigation
 * React mounts the next route before unmounting the previous one, so restoring
 * unconditionally would let the old page's cleanup clobber the new page's
 * title; the guard below only restores if nothing else has set it since.
 */
export function useDocumentTitle(title?: string | null): void {
  useEffect(() => {
    if (title === null) {
      return;
    }
    const previous = document.title;
    const next = pageTitle(title);
    document.title = next;

    return () => {
      if (document.title === next) {
        document.title = previous;
      }
    };
  }, [title]);
}
