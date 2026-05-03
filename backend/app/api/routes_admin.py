"""Admin / one-shot operations callable via routine token.

Currently exposes the orphan-orders cleanup that previously could only be run
through `python -m app.scripts.cleanup_orphan_orders` (which requires Railway
shell access).
"""
import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from app.api.routes_digest import require_routine_token
from app.scripts.cleanup_orphan_orders import cleanup
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/admin/cleanup-orphan-orders", dependencies=[Depends(require_routine_token)])
async def admin_cleanup_orphan_orders(apply: bool = Query(False)):
    """Run the orphan-orders cleanup script. Default is dry-run.

    Returns the same per-decision counts the CLI prints, plus a flag indicating
    whether mutations were applied.
    """
    counts = await cleanup(apply=apply)
    return {"applied": apply, "counts": counts}
