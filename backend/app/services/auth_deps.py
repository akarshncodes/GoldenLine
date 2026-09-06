"""FastAPI dependencies for FR-11 auth + FR-12 rate-limit flagging."""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.case import Case
from app.services.access import require_case_access, require_roles
from app.services.security import Principal, TokenError, decode_token

_UNAUTHENTICATED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)


def principal_from_request(request: Request) -> Principal | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    try:
        return decode_token(header.split(" ", 1)[1].strip())
    except TokenError:
        return None


def get_principal(request: Request) -> Principal:
    principal = principal_from_request(request)
    if principal is None:
        raise _UNAUTHENTICATED
    return principal


def get_principal_optional(request: Request) -> Principal | None:
    return principal_from_request(request)


def require_role(*roles: Role):
    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        require_roles(principal, *roles)
        return principal

    return _dep


def case_access(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Case:
    """Load the case and enforce FR-11 role scoping. Use in place of a bare lookup."""
    principal = get_principal(request)
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    return require_case_access(db, principal, case)
