"""Google Sheets export API: trigger run, read last-run status."""
import asyncio
import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes_digest import require_routine_token
from app.crud import get_setting
from app.db import get_db
from app.services.sheets_export import LAST_RUN_KEY, export_all
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _run_blocking() -> Dict[str, Any]:
    return export_all()


@router.post("/sheets/export/run", dependencies=[Depends(require_routine_token)])
async def run_export_routine():
    """Routine-token entrypoint. Exports take ~30s-2min; we run in a thread
    so the FastAPI worker stays responsive."""
    return await asyncio.to_thread(_run_blocking)


@router.post("/sheets/export/run-manual")
async def run_export_manual(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Mini App entrypoint — same export, admin-session auth."""
    return await asyncio.to_thread(_run_blocking)


@router.get("/sheets/export/status")
async def export_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    raw = get_setting(db, LAST_RUN_KEY)
    sheet_id = get_setting(db, "google_sheets_spreadsheet_id")
    creds_set = bool(get_setting(db, "google_sheets_credentials_json"))
    last = json.loads(raw) if raw else None
    sheet_url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit" if sheet_id else None
    )
    return {
        "configured": creds_set and bool(sheet_id),
        "credentials_set": creds_set,
        "spreadsheet_id": sheet_id,
        "sheet_url": sheet_url,
        "last_run": last,
    }
