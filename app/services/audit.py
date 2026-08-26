import json
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy.orm import Session

from app.models import AuditRun


@contextmanager
def audited_action(
    db: Session,
    action: str,
    input_data: Any,
) -> Iterator[dict[str, Any]]:
    started = time.perf_counter()
    ctx: dict[str, Any] = {
        "output": {},
        "status": "ok",
        "error": None,
    }
    try:
        yield ctx
        db.add(
            AuditRun(
                action=action,
                input=json.dumps(input_data, ensure_ascii=False, default=str),
                output=json.dumps(ctx.get("output", {}), ensure_ascii=False, default=str),
                status=ctx.get("status", "ok"),
                error=ctx.get("error"),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        db.add(
            AuditRun(
                action=action,
                input=json.dumps(input_data, ensure_ascii=False, default=str),
                output=json.dumps(ctx.get("output", {}), ensure_ascii=False, default=str),
                status="error",
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        )
        db.commit()
        raise


def run_audited(
    db: Session,
    action: str,
    input_data: Any,
    fn: Callable[[], Any],
) -> Any:
    with audited_action(db, action, input_data) as ctx:
        result = fn()
        ctx["output"] = result if isinstance(result, (dict, list)) else {"result": result}
        return result
