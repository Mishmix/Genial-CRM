"""Todoist Sync Manager API.

Endpoints driven by an Anthropic Routine that runs once a day. Reads a snapshot
of CRM Orders + Todoist tasks + recent conversations, decides a batch of
actions, and applies them through here. Real-time `order_detector` is left
untouched — this is a slower, fuller-context cleaner.

All endpoints require X-Routine-Token (re-using the AI-Manager auth from
routes_digest).
"""
import html
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.routes_digest import (
    _admin_chat_id,
    _chunk_html,
    _markdown_to_telegram_html,
    require_routine_token,
)
from app.crud import get_setting
from app.db import get_db
from app.integrations.todoist import (
    SERVICE_NAMES,
    batch_execute,
    list_active_tasks,
    list_completed_tasks,
)
from app.models import Client, Message, Order, TodoistSyncLog
from app.telegram.bot import get_bot
from app.utils.logging import get_logger
from app.utils.timezone import now_georgia

logger = get_logger(__name__)
router = APIRouter()


DELETE_REASON_MIN_LEN = 10
MASS_DELETE_THRESHOLD = 5  # > this requires actions[].confirm_mass_delete=True


def _todoist_config(db: Session) -> Dict[str, Optional[str]]:
    return {
        "api_token": get_setting(db, "todoist_api_token"),
        "project_id": get_setting(db, "todoist_project_id"),
        "section_today_id": get_setting(db, "todoist_section_today_id"),
        "section_not_today_id": get_setting(db, "todoist_section_not_today_id"),
        "enabled": get_setting(db, "todoist_enabled") == "true",
    }


def _need_todoist(cfg: Dict[str, Optional[str]]) -> None:
    if not cfg.get("api_token") or not cfg.get("project_id"):
        raise HTTPException(status_code=400, detail="Todoist not configured (api_token/project_id missing)")


# ----------------------------- snapshot ------------------------------------


def _serialize_message_brief(msg: Message) -> Dict[str, Any]:
    return {
        "direction": msg.direction,
        "type": msg.message_type or "text",
        "content": (msg.transcription if msg.message_type == "voice" else msg.text) or "",
        "created_at": msg.sent_at.isoformat() if msg.sent_at else None,
    }


@router.get("/todoist/sync/snapshot", dependencies=[Depends(require_routine_token)])
async def sync_snapshot(db: Session = Depends(get_db)):
    cfg = _todoist_config(db)
    _need_todoist(cfg)
    now = now_georgia()
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    activity_since = now - timedelta(hours=48)

    # --- Todoist side
    tasks = await list_active_tasks(cfg["api_token"], cfg["project_id"])
    completed = await list_completed_tasks(cfg["api_token"], cfg["project_id"], yesterday_start)

    # --- CRM side: pending orders
    pending = (
        db.query(Order)
        .filter(Order.status == "pending")
        .order_by(Order.created_at.desc())
        .all()
    )
    pending_orders: List[Dict[str, Any]] = []
    client_ids: set[int] = set()
    for o in pending:
        client_ids.add(o.client_id)
        pending_orders.append({
            "id": o.id,
            "client_id": o.client_id,
            "service_type": o.service_type,
            "service_ru": SERVICE_NAMES.get(o.service_type, o.service_type),
            "quantity": o.quantity or 1,
            "deadline_date": o.deadline_date.isoformat() if o.deadline_date else None,
            "deadline_text": o.deadline_custom or o.deadline_range,
            "status": o.status,
            "todoist_task_id": o.todoist_task_id,
            "ai_confidence": o.ai_confidence,
            "source": o.source,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "notes": o.notes,
        })

    # --- Active clients (have a pending order or recent activity)
    active_q = (
        db.query(Client)
        .filter(
            (Client.id.in_(client_ids) if client_ids else False)
            | (Client.last_client_message_at >= activity_since)
        )
        .filter(Client.is_archived == False)  # noqa: E712
        .all()
    )
    active_clients: List[Dict[str, Any]] = []
    for c in active_q:
        msgs = (
            db.query(Message)
            .filter(Message.client_id == c.id)
            .order_by(desc(Message.sent_at))
            .limit(25)
            .all()
        )
        msgs.reverse()
        active_clients.append({
            "id": c.id,
            "name": " ".join(filter(None, [c.first_name, c.last_name])).strip() or "Unknown",
            "telegram_user_id": c.telegram_user_id if c.telegram_user_id and c.telegram_user_id > 0 else None,
            "telegram_username": c.username,
            "status": c.status,
            "last_client_message_at": c.last_client_message_at.isoformat() if c.last_client_message_at else None,
            "messages": [_serialize_message_brief(m) for m in msgs],
        })

    # --- Map todoist tasks → orders/clients (best-effort by task_id)
    order_by_task_id = {o["todoist_task_id"]: o for o in pending_orders if o["todoist_task_id"]}
    client_by_id = {c["id"]: c for c in active_clients}
    enriched_tasks: List[Dict[str, Any]] = []
    for t in tasks:
        mapped_order = order_by_task_id.get(t["id"])
        mapped_client = client_by_id.get(mapped_order["client_id"]) if mapped_order else None
        enriched_tasks.append({
            **t,
            "mapped_order_id": mapped_order["id"] if mapped_order else None,
            "mapped_client_id": mapped_order["client_id"] if mapped_order else None,
            "mapped_client_name": mapped_client["name"] if mapped_client else None,
        })

    return {
        "now": now.isoformat(),
        "now_human": _now_human(now),
        "tz": "Asia/Tbilisi (UTC+4)",
        "todoist_tasks": enriched_tasks,
        "completed_yesterday": completed,
        "pending_orders": pending_orders,
        "active_clients": active_clients,
    }


def _now_human(dt: datetime) -> str:
    weekdays = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    months = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    return f"{weekdays[dt.weekday()]}, {dt.day} {months[dt.month - 1]} {dt.year}, {dt.strftime('%H:%M')}"


# ----------------------------- execute -------------------------------------


class ExecuteBody(BaseModel):
    actions: List[Dict[str, Any]]


def _validate_actions(actions: List[Dict[str, Any]]) -> None:
    delete_count = sum(1 for a in actions if a.get("type") == "delete")
    mass_confirmed = any(a.get("confirm_mass_delete") for a in actions)
    if delete_count > MASS_DELETE_THRESHOLD and not mass_confirmed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Refusing batch with {delete_count} deletes (>{MASS_DELETE_THRESHOLD}). "
                "Add confirm_mass_delete=true on at least one action to override."
            ),
        )
    for a in actions:
        if a.get("type") == "delete":
            reason = (a.get("reason") or "").strip()
            if len(reason) < DELETE_REASON_MIN_LEN:
                raise HTTPException(
                    status_code=400,
                    detail=f"delete action requires reason ≥ {DELETE_REASON_MIN_LEN} chars: {a}",
                )


@router.post("/todoist/sync/execute", dependencies=[Depends(require_routine_token)])
async def sync_execute(
    payload: ExecuteBody,
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
):
    cfg = _todoist_config(db)
    _need_todoist(cfg)
    _validate_actions(payload.actions)

    result = await batch_execute(
        cfg["api_token"],
        cfg["project_id"],
        payload.actions,
        section_today_id=cfg["section_today_id"],
        section_not_today_id=cfg["section_not_today_id"],
        dry_run=dry_run,
    )

    if not dry_run:
        # Reflect changes in CRM Order rows where we can.
        for entry in result["applied"]:
            action = entry["action"]
            atype = action.get("type")
            try:
                if atype == "create" and action.get("client_id"):
                    # Best-effort: link the newest pending Order of this service+client.
                    o = (
                        db.query(Order)
                        .filter(Order.client_id == action["client_id"])
                        .filter(Order.service_type == action.get("service_type"))
                        .filter(Order.status == "pending")
                        .order_by(Order.created_at.desc())
                        .first()
                    )
                    if o and not o.todoist_task_id:
                        o.todoist_task_id = entry.get("task_id")
                elif atype == "complete":
                    o = db.query(Order).filter(Order.todoist_task_id == action.get("task_id")).first()
                    if o:
                        o.status = "completed"
                        o.completed_at = now_georgia()
                elif atype == "delete":
                    o = db.query(Order).filter(Order.todoist_task_id == action.get("task_id")).first()
                    if o:
                        o.todoist_task_id = None
            except Exception as exc:
                logger.warning(f"Could not mirror action to Order: {exc}")
        db.commit()

    return result


# ------------------------------ report -------------------------------------


class ReportBody(BaseModel):
    summary_md: str
    applied_count: int = 0
    failed_count: int = 0
    actions_json: Optional[Any] = None
    routine_session_url: Optional[str] = None


@router.post("/todoist/sync/report", dependencies=[Depends(require_routine_token)])
async def sync_report(payload: ReportBody, db: Session = Depends(get_db)):
    chat_id = _admin_chat_id(db)
    if not chat_id:
        raise HTTPException(status_code=400, detail="No admin_telegram_ids configured")
    bot = get_bot()
    if bot is None:
        raise HTTPException(status_code=500, detail="Telegram bot not initialized")

    header = f"🤖 <b>Todoist Sync</b> — {now_georgia().strftime('%d.%m %H:%M')}\n\n"
    body_html = _markdown_to_telegram_html(payload.summary_md or "")
    full_text = header + body_html
    chunks = _chunk_html(full_text)

    first_id: Optional[int] = None
    for i, chunk in enumerate(chunks):
        try:
            sent = await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            if i == 0:
                first_id = sent.message_id
        except Exception as exc:
            logger.error(f"Todoist sync report chunk {i} failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Telegram send failed: {exc}") from exc

    log = TodoistSyncLog(
        summary_md=payload.summary_md,
        applied_count=payload.applied_count,
        failed_count=payload.failed_count,
        actions_json=payload.actions_json,
        routine_session_url=payload.routine_session_url,
        telegram_message_id=first_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"delivered": True, "telegram_message_id": first_id, "log_id": log.id, "chunks": len(chunks)}


# ----------------------------- recent logs ---------------------------------


@router.get("/todoist/sync/recent-logs", dependencies=[Depends(require_routine_token)])
async def sync_recent_logs(n: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    rows = (
        db.query(TodoistSyncLog)
        .order_by(desc(TodoistSyncLog.started_at))
        .limit(n)
        .all()
    )
    return [
        {
            "id": r.id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "applied_count": r.applied_count,
            "failed_count": r.failed_count,
            "summary": (r.summary_md or "")[:500],
            "telegram_message_id": r.telegram_message_id,
            "routine_session_url": r.routine_session_url,
        }
        for r in rows
    ]
