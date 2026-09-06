"""Health-check endpoint: confirms the API process and the database are reachable."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> JSONResponse:
    settings = get_settings()

    db_ok = True
    db_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report any connectivity failure
        db_ok = False
        db_error = str(exc)

    body = {
        "status": "ok" if db_ok else "degraded",
        "api": "up",
        "database": "up" if db_ok else "down",
        "app": settings.app_name,
        "env": settings.env,
        "time": datetime.now(timezone.utc).isoformat(),
    }
    if db_error:
        body["database_error"] = db_error

    return JSONResponse(status_code=200 if db_ok else 503, content=body)
