def stringify_urls(data: dict, fields: tuple[str, ...]) -> dict:
    """Pydantic's HttpUrl fields come out of model_dump() (python mode) as Url
    objects, not str - convert the given fields in place so they bind cleanly
    to a String column. (mode="json" would do this too, but it also turns
    UUID/date fields into strings, which asyncpg doesn't accept when binding
    directly via the ORM.)"""
    for field in fields:
        if field in data and data[field] is not None:
            data[field] = str(data[field])
    return data
