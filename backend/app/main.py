import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.logging_config import configure_logging, request_id_var
from app.routers import (
    admin,
    announcements,
    home,
    matches,
    players,
    seasons,
    site_links,
)

configure_logging()
logger = logging.getLogger("app.request")

# Swagger, ReDoc and openapi.json enumerate every admin route and its schema.
# Off in production unless deliberately re-enabled.
_docs = settings.show_docs

app = FastAPI(
    title=settings.project_name,
    version="1.0.0",
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

# Rejects requests whose Host header is not ours, which blunts host-header
# poisoning and stops the app answering on a bare IP address.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

# In same-origin production cors_origins is empty and this middleware is not
# added at all - there is no cross-origin request to permit.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request id and log one line per request.

    Deliberately logs no query strings, headers, cookies or bodies: those are
    where credentials and private data live.
    """
    incoming = request.headers.get("x-request-id", "")
    request_id = incoming[:64] if incoming else uuid.uuid4().hex[:16]
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "unhandled error", extra={"method": request.method, "path": request.url.path}
        )
        raise
    finally:
        request_id_var.reset(token)

    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(players.router, prefix="/api")
app.include_router(seasons.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(announcements.router, prefix="/api")
app.include_router(home.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(site_links.router, prefix="/api")


@app.get("/health", tags=["health"], include_in_schema=False)
async def liveness() -> dict[str, str]:
    """Liveness: is the process up and serving?

    Deliberately does not touch the database - a database outage should not
    cause the orchestrator to kill an otherwise healthy API process.
    """
    return {"status": "ok"}


@app.get("/ready", tags=["health"], include_in_schema=False)
async def readiness() -> JSONResponse:
    """Readiness: can this instance actually serve requests?

    Runs a trivial query, so the instance reports unhealthy while PostgreSQL is
    unavailable and stops receiving traffic.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("readiness probe failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unreachable"},
        )
    return JSONResponse(status_code=200, content={"status": "ready", "database": "ok"})
