"""Field types shared by more than one schema module."""

from typing import Annotated

from pydantic import AfterValidator

from app.utils.slugs import MAX_SLUG_LENGTH, is_valid_slug, normalize_slug

_SLUG_HELP = (
    "must be lowercase letters, numbers and single hyphens "
    f"(for example \"psykick\" or \"summer-2027\"), at most {MAX_SLUG_LENGTH} characters"
)


def _validate_slug(value: str) -> str:
    normalized = normalize_slug(value)
    if not is_valid_slug(normalized):
        raise ValueError(f"slug {_SLUG_HELP}")
    return normalized


# Case and outer whitespace are folded, because "Psykick " and "psykick" are the
# same slug; anything else is rejected rather than repaired, so an administrator
# is told what is wrong instead of getting a slug they did not type.
SlugStr = Annotated[str, AfterValidator(_validate_slug)]
