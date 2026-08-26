from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditRun
from app.schemas import AuditRunItem

router = APIRouter(tags=["audit"])


@router.get("/audit/runs", response_model=list[AuditRunItem])
def list_audit_runs(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AuditRun]:
    rows = db.scalars(select(AuditRun).order_by(AuditRun.created_at.desc()).limit(limit)).all()
    return list(rows)
