"""Admin / one-shot operations callable via routine token.

Currently exposes the orphan-orders cleanup that previously could only be run
through `python -m app.scripts.cleanup_orphan_orders` (which requires Railway
shell access).
"""
import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from app.api.routes_digest import require_routine_token
from app.db import get_db
from app.scripts.cleanup_orphan_orders import cleanup
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/admin/cleanup-orphan-orders", dependencies=[Depends(require_routine_token)])
async def admin_cleanup_orphan_orders(apply: bool = Query(False)):
    """Run the orphan-orders cleanup script. Default is dry-run."""
    counts = await cleanup(apply=apply)
    return {"applied": apply, "counts": counts}


@router.get("/admin/detectors-smoke", dependencies=[Depends(require_routine_token)])
async def admin_detectors_smoke(db=Depends(get_db)):
    """Run all 3 v4 detectors and return raw output. PR#2 smoke endpoint.

    Each detector is wrapped — failure in one returns its error rather than
    crashing the whole call. Detectors are not yet wired into /digest/data.
    """
    from app.utils.timezone import now_georgia
    now = now_georgia()
    out: Dict[str, Any] = {}
    try:
        from app.services.money_at_risk import detect_money_at_risk
        out["money_at_risk"] = await detect_money_at_risk(db, now)
    except Exception as exc:
        out["money_at_risk_error"] = f"{type(exc).__name__}: {exc}"
    try:
        from app.services.predictive_reorders import detect_predictive_reorders
        out["predictive_reorders"] = await detect_predictive_reorders(db, now)
    except Exception as exc:
        out["predictive_reorders_error"] = f"{type(exc).__name__}: {exc}"
    try:
        from app.services.rejection_reactivation import detect_reactivation_candidates
        out["rejection_reactivation"] = await detect_reactivation_candidates(db, now)
    except Exception as exc:
        out["rejection_reactivation_error"] = f"{type(exc).__name__}: {exc}"
    return out
