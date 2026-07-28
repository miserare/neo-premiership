from fastapi import APIRouter, Depends

from app.auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/session", dependencies=[Depends(require_admin)])
async def verify_admin_session() -> dict[str, bool]:
    """Token check for the admin UI's sign-in form.

    require_admin does all the work: 401 for a wrong/missing token, 503 when the
    server has no ADMIN_TOKEN configured at all. Without this the UI would have
    to accept any string and only discover a bad token on the first failed save.
    """
    return {"ok": True}
