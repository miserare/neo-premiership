"""Production logging.

Every line carries the request id so a user-reported failure can be traced.
Nothing here logs headers, cookies, query strings or request bodies, because
that is where credentials and private data live.
"""

import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    from app.config import settings

    level = logging.DEBUG if settings.is_development else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn's own access log duplicates our request middleware and includes
    # the full query string; ours is the one that redacts.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    # Only echo SQL when explicitly in development.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.sql_echo else logging.WARNING
    )
