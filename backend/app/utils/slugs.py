"""Canonical URL slugs for players and seasons.

A slug is stored data, not a rendering of the display name. It is derived once
- when the row is created or backfilled - and then only ever changes because an
administrator changed it deliberately. Renaming a player therefore does not
break their existing links.

The stored form is always lowercase ASCII, so the column's plain unique
constraint *is* case-insensitive uniqueness. Callers normalize administrator
input through :func:`normalize_slug` before comparing or writing.
"""

import re
import unicodedata

MAX_SLUG_LENGTH = 64

# Lowercase ASCII letters and digits, single hyphens between them, no leading or
# trailing hyphen. Deliberately stricter than "what a URL permits": these appear
# in shareable links and want to stay readable.
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")
# A leading "Season" word, so "Season 6" backfills to "6" rather than "season-6".
_SEASON_PREFIX = re.compile(r"^\s*seasons?\b[\s:.-]*", re.IGNORECASE)


def slugify(value: str) -> str:
    """Best-effort slug for a display name. May return "" for an unusable name.

    Accented characters decompose to their ASCII base ("Renè" -> "rene");
    anything with no ASCII equivalent at all is dropped, which is why the
    result can legitimately be empty and callers must handle that rather than
    writing a blank slug.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    hyphenated = _NON_SLUG_CHARS.sub("-", ascii_only.lower()).strip("-")
    # Truncating can leave a trailing hyphen ("ab-" from "ab-c"), so strip again.
    return hyphenated[:MAX_SLUG_LENGTH].strip("-")


def slugify_season_name(name: str) -> str:
    """Slug for a season name, preferring the part that identifies the season.

    "Season 6" -> "6" and "Season Summer 2027" -> "summer-2027", because the
    word "season" is already in the URL path. A name that is *only* the word
    season, or that has no usable prefix to strip, falls back to slugifying the
    whole thing. Nothing here parses or requires a number.
    """
    stripped = slugify(_SEASON_PREFIX.sub("", name, count=1))
    return stripped or slugify(name)


# Slugs that would collide with something else at the same position in a URL,
# or with the tombstone player. Deliberately short: every entry here is a real
# collision, not a precaution.
RESERVED_PLAYER_SLUGS = frozenset({"admin", "deleted-player"})
RESERVED_SEASON_SLUGS = frozenset({"current"})


def is_valid_slug(value: str) -> bool:
    return bool(value) and len(value) <= MAX_SLUG_LENGTH and SLUG_PATTERN.match(value) is not None


def normalize_slug(value: str) -> str:
    """Fold administrator input to the stored form, without repairing it.

    Case and surrounding whitespace are normalized because "Psykick " and
    "psykick" are plainly the same slug. Anything else - spaces in the middle,
    punctuation, an empty result - is left alone so validation rejects it with
    a message instead of silently storing something the administrator did not
    type.
    """
    return value.strip().lower()
