"""FR-11 request-layer hardening: HTTPS-only + role-scoped access to /cases/*.

Case-scoping lives here (one place) rather than being repeated on ~25 routes.
"""
import re

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.database import get_db
from app.models.case import Case
from app.services.access import can_see_case
from app.services.security import Principal, TokenError, decode_token

# Paths under /cases/{id} that do NOT require an authenticated principal
# (token-gated in the handler instead).
_PUBLIC_CASE_SUBPATHS = re.compile(r"^/cases/[^/]+/feedback$")
# /cases/{case_id}... but not /cases/sos and not the bare /cases
_CASE_SCOPED = re.compile(r"^/cases/(?P<case_id>[^/]+)(?:/.*)?$")


def _principal(request: Request) -> Principal | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    try:
        return decode_token(header.split(" ", 1)[1].strip())
    except TokenError:
        return None


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # --- FR-11: HTTPS only (when enabled) ---
        if settings.force_https:
            proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if proto != "https":
                return JSONResponse(
                    status_code=426,
                    content={"detail": "HTTPS required — plain HTTP is not accepted for this API"},
                )

        principal = _principal(request)
        request.state.principal = principal

        path = request.url.path
        m = _CASE_SCOPED.match(path)
        if m and path not in ("/cases", "/cases/sos") and not _PUBLIC_CASE_SUBPATHS.match(path):
            case_id = m.group("case_id")
            if case_id != "sos":
                if principal is None:
                    return JSONResponse(status_code=401, content={"detail": "authentication required"})
                # Use the request's DB (respects the test dependency override).
                gen = request.app.dependency_overrides.get(get_db, get_db)()
                db = next(gen)
                try:
                    case = db.get(Case, case_id)
                    if case is None:
                        return JSONResponse(status_code=404, content={"detail": f"case '{case_id}' does not exist"})
                    if not can_see_case(db, principal, case):
                        return JSONResponse(status_code=403, content={"detail": "not authorised for this case"})
                finally:
                    gen.close()

        return await call_next(request)
