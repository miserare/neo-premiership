"""Double-submit CSRF protection.

Each session carries its own random CSRF secret. It is published in a
*readable* cookie (deliberately not HttpOnly) so the SPA can echo it back in a
header. An attacker's cross-site page can cause the browser to send the session
cookie, but same-origin policy stops it reading the CSRF cookie, so it cannot
produce the matching header.

SameSite=Lax already blocks the common cross-site POST, so this is defence in
depth rather than the only control.
"""

import secrets

from fastapi import HTTPException, Request, status

from app.models.admin import AdminSession
from app.security.sessions import CSRF_HEADER_NAME

# Methods that may change state and therefore require the token.
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def require_csrf(request: Request, session: AdminSession) -> None:
    if request.method.upper() not in UNSAFE_METHODS:
        return

    supplied = request.headers.get(CSRF_HEADER_NAME)
    if not supplied or not secrets.compare_digest(supplied, session.csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid CSRF token",
        )
