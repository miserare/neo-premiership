from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SiteLinksRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stream_url: str | None
    stream_label: str | None
    document_url: str | None
    document_label: str | None
    table_url: str | None
    table_label: str | None


class SiteLinksUpdate(BaseModel):
    """Full replacement of the overrides. Send null for a field to hand it back
    to the derived default."""

    stream_url: HttpUrl | None = None
    stream_label: str | None = Field(default=None, max_length=120)
    document_url: HttpUrl | None = None
    document_label: str | None = Field(default=None, max_length=120)
    table_url: HttpUrl | None = None
    table_label: str | None = Field(default=None, max_length=120)
