from fastapi import Header, HTTPException, status

from app.config import settings


async def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Admin API is not configured")
    if x_admin_token != settings.admin_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing admin token")
