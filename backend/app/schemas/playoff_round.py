import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlayoffRoundRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    season_id: uuid.UUID
    label: str
    display_order: int
    match_count: int = 0


class PlayoffRoundCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)
    # Omitted means "append after the last existing round", which is what an
    # administrator building a bracket front-to-back wants. An explicit value
    # still has to be a real position, never 0 or negative.
    display_order: int | None = Field(default=None, gt=0)

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("label must not be blank")
        return stripped


class PlayoffRoundUpdate(BaseModel):
    """Renaming only. Position is changed through the reorder endpoint, so a
    rename can never move a round by accident."""

    label: str = Field(..., min_length=1, max_length=64)

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("label must not be blank")
        return stripped


class PlayoffRoundReorder(BaseModel):
    """The complete ordered list of a season's round ids.

    Whole-list rather than "move this one up": the server rewrites contiguous
    positions 1..N in a single transaction, so there is no window in which two
    rounds share a position and no way to end up half-reordered.
    """

    round_ids: list[uuid.UUID] = Field(..., min_length=1)

    @field_validator("round_ids")
    @classmethod
    def _no_duplicates(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("round_ids must not contain duplicates")
        return value
