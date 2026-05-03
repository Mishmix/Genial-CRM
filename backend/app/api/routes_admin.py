"""Admin / one-shot operations callable via routine token (or admin session)."""
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes_digest import require_routine_token
from app.db import get_db
from app.models import Conversation
from app.scripts.cleanup_orphan_orders import cleanup
from app.scripts.classify_existing_rejections import cleanup_or_classify
from app.utils.logging import get_logger
from app.utils.timezone import now_georgia

logger = get_logger(__name__)
router = APIRouter()


@router.post("/admin/cleanup-orphan-orders", dependencies=[Depends(require_routine_token)])
async def admin_cleanup_orphan_orders(apply: bool = Query(False)):
    counts = await cleanup(apply=apply)
    return {"applied": apply, "counts": counts}


@router.post("/admin/classify-rejections", dependencies=[Depends(require_routine_token)])
async def admin_classify_rejections(apply: bool = Query(False)):
    """Backfill `Conversation.rejection_normalized_category` for old rejections.
    Default dry-run; ?apply=true mutates."""
    counts = await cleanup_or_classify(apply=apply)
    return {"applied": apply, "counts": counts}


@router.get("/admin/reactivation-candidates")
async def admin_reactivation_candidates(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Same detector as morning digest, exposed for the Mini App's ReactivationPage."""
    from app.services.rejection_reactivation import detect_reactivation_candidates
    return await detect_reactivation_candidates(db, now_georgia(), top_n=200)


@router.post("/reactivation/mark-attempt")
async def mark_reactivation_attempt(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Increment reactivation_attempts on a Conversation. Used from Mini App."""
    conv_id = payload.get("conversation_id")
    if not conv_id:
        raise HTTPException(status_code=400, detail="conversation_id required")
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.reactivation_attempts = (conv.reactivation_attempts or 0) + 1
    conv.last_reactivation_at = now_georgia()
    db.commit()
    return {
        "ok": True,
        "conversation_id": conv.id,
        "reactivation_attempts": conv.reactivation_attempts,
        "last_reactivation_at": conv.last_reactivation_at.isoformat(),
    }
