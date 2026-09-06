"""Admin-only demo controls. Not a formal FRP requirement — added so a live
demo can restart clean without a backend restart."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.services import demo_reset as svc
from app.services.auth_deps import require_role
from app.services.security import Principal

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset-demo-data")
def reset_demo_data(
    principal: Principal = Depends(require_role(Role.admin)),
    db: Session = Depends(get_db),
) -> dict:
    """Wipe every case-lifecycle table and restore hospitals'/blood banks'
    live counters to their seeded values. Static rosters (users, and the
    hospital/blood-bank/waypoint rows themselves) are left untouched."""
    return svc.reset_demo_data(db)
