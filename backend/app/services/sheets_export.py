"""Google Sheets export — full rewrite-strategy.

Three sheets:
  - Clients         — overwritten each run, full snapshot
  - Orders          — overwritten each run, full snapshot
  - Daily Snapshot  — append-only, one row per calendar day

Configuration lives in `Setting`:
  - google_sheets_credentials_json (the entire service-account JSON as a string)
  - google_sheets_spreadsheet_id

Run cadence: once per day from a routine; can be triggered manually from
Mini App (admin-session). One run takes ~30s for ~1k clients, ~2 min for 10k.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.crud import get_setting, set_setting
from app.db import SessionLocal
from app.models import Client, ClientEnrichment, Message, Order
from app.utils.logging import get_logger
from app.utils.timezone import now_georgia

logger = get_logger(__name__)


CLIENTS_SHEET = "Clients"
ORDERS_SHEET = "Orders"
SNAPSHOT_SHEET = "Daily Snapshot"

CLIENTS_HEADERS = [
    "telegram_id", "username", "deep_link", "first_name", "last_name", "language",
    "first_contact_at", "last_inbound_at", "last_outbound_at", "days_since_last_contact",
    "total_orders", "completed_orders", "total_spent", "avg_check", "last_order_at", "days_since_last_order",
    "response_time_avg_hours", "conversion_rate", "repeat_customer", "churn_risk", "ltv_estimate",
    "niche", "channel_name", "channel_size_bucket", "temperature", "communication_style",
    "price_sensitivity", "decision_speed", "last_summary", "pain_points", "value_drivers",
    "next_best_action", "ai_reviewed_at", "status", "tags", "manual_notes", "ai_notes",
]

ORDERS_HEADERS = [
    "order_id", "client_name", "client_deep_link", "service_type", "quantity",
    "deadline_date", "created_at", "completed_at", "duration_days", "status",
    "source", "amount", "notes", "todoist_task_id", "thumbnail_url",
]

SNAPSHOT_HEADERS = [
    "date", "total_clients", "active_clients_30d", "new_clients_24h",
    "orders_24h", "completed_24h", "pending_orders", "avg_response_time_h", "top_niche_today",
]

# Cache key for last-run status, lives in Setting.
LAST_RUN_KEY = "google_sheets_last_run"


def _get_client(db: Session):
    """Build an authorized gspread client. Imports here so the rest of the app
    boots even if google libs are unavailable in dev."""
    import gspread
    from google.oauth2.service_account import Credentials

    creds_raw = get_setting(db, "google_sheets_credentials_json")
    if not creds_raw:
        raise RuntimeError("google_sheets_credentials_json is not set")
    creds_dict = json.loads(creds_raw)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def _open_sheet(db: Session):
    sheet_id = get_setting(db, "google_sheets_spreadsheet_id")
    if not sheet_id:
        raise RuntimeError("google_sheets_spreadsheet_id is not set")
    gc = _get_client(db)
    return gc.open_by_key(sheet_id)


def _ensure_worksheet(spreadsheet, title: str, headers: List[str]):
    try:
        ws = spreadsheet.worksheet(title)
    except Exception:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=max(len(headers), 26))
        ws.update("A1", [headers])
    return ws


# ----------------------------- helpers --------------------------------------


def _build_deep_link(c: Client) -> Optional[str]:
    if c.telegram_user_id and c.telegram_user_id > 0:
        return f"tg://user?id={c.telegram_user_id}"
    if c.username:
        return f"https://t.me/{c.username}"
    return None


def _churn_risk(days_since_contact: Optional[int], completed_orders: int) -> str:
    if days_since_contact is None:
        return "unknown"
    if days_since_contact < 14:
        return "low"
    if days_since_contact < 45:
        return "medium"
    if completed_orders >= 1:
        return "high"
    return "medium"


def _ltv_estimate(total_spent: float, avg_check: float, total_orders: int) -> float:
    if total_orders < 2:
        return round(total_spent or 0.0, 2)
    expected_lifetime = total_orders * 1.5
    future = max(0.0, (expected_lifetime - total_orders)) * (avg_check or 0.0)
    return round((total_spent or 0.0) + future, 2)


def _safe_dt(dt: Optional[datetime]) -> str:
    return dt.isoformat(timespec="seconds") if dt else ""


def _days_since(dt: Optional[datetime], now: datetime) -> Optional[int]:
    if not dt:
        return None
    return (now - dt).days


# ----------------------------- exports --------------------------------------


def _build_client_row(c: Client, enrich: Optional[ClientEnrichment], orders: List[Order],
                      first_inbound: Optional[datetime], avg_response_h: Optional[float], now: datetime) -> List[Any]:
    completed_orders = [o for o in orders if o.status == "completed"]
    completed_count = len(completed_orders)
    total_orders = c.total_orders or len(orders)
    total_spent = float(c.total_spent or 0.0)
    avg_check = (total_spent / completed_count) if completed_count else 0.0
    last_order_at = max((o.created_at for o in orders if o.created_at), default=None)
    last_inbound = c.last_client_message_at
    last_outbound = c.last_message_at if (c.last_message_at and c.last_message_at != c.last_client_message_at) else None
    last_contact = max(filter(None, [last_inbound, last_outbound]), default=None)
    days_since_contact = _days_since(last_contact, now)
    days_since_order = _days_since(last_order_at, now)
    conv_rate = (completed_count / total_orders) if total_orders else 0.0

    return [
        c.telegram_user_id if c.telegram_user_id and c.telegram_user_id > 0 else "",
        c.username or "",
        _build_deep_link(c) or "",
        c.first_name or "",
        c.last_name or "",
        c.language_code or "",
        _safe_dt(first_inbound or c.first_seen_at),
        _safe_dt(last_inbound),
        _safe_dt(last_outbound),
        days_since_contact if days_since_contact is not None else "",
        total_orders,
        completed_count,
        round(total_spent, 2),
        round(avg_check, 2),
        _safe_dt(last_order_at),
        days_since_order if days_since_order is not None else "",
        round(avg_response_h, 2) if avg_response_h is not None else "",
        round(conv_rate, 3),
        completed_count >= 2,
        _churn_risk(days_since_contact, completed_count),
        _ltv_estimate(total_spent, avg_check, total_orders),
        (enrich.niche if enrich else "") or "",
        (enrich.channel_name if enrich else "") or "",
        (enrich.channel_size_bucket if enrich else "") or "",
        (enrich.temperature if enrich else "") or "",
        (enrich.communication_style if enrich else "") or "",
        (enrich.price_sensitivity if enrich else "") or "",
        (enrich.decision_speed if enrich else "") or "",
        (enrich.last_summary if enrich else "") or "",
        ", ".join((enrich.pain_points if enrich else []) or []),
        ", ".join((enrich.value_drivers if enrich else []) or []),
        (enrich.next_best_action if enrich else "") or "",
        _safe_dt(enrich.reviewed_at if enrich else None),
        c.status or "",
        ", ".join(t.name for t in (c.tags or [])),
        c.notes or "",
        (enrich.ai_notes if enrich else "") or "",
    ]


def _build_order_row(o: Order, client_name_by_id: Dict[int, str], deep_link_by_id: Dict[int, str]) -> List[Any]:
    duration = ""
    if o.completed_at and o.created_at:
        duration = (o.completed_at - o.created_at).days
    return [
        o.id,
        client_name_by_id.get(o.client_id, ""),
        deep_link_by_id.get(o.client_id, "") or "",
        o.service_type or "",
        o.quantity or 1,
        _safe_dt(o.deadline_date),
        _safe_dt(o.created_at),
        _safe_dt(o.completed_at),
        duration,
        o.status or "",
        o.source or "",
        float(o.amount) if o.amount else "",
        o.notes or "",
        o.todoist_task_id or "",
        "",  # thumbnail_url placeholder for v1.2 media support
    ]


def export_clients_to_sheet(db: Session, spreadsheet) -> int:
    clients: List[Client] = db.query(Client).all()
    enrichments = {e.client_id: e for e in db.query(ClientEnrichment).all()}

    # Pre-aggregate per-client stats with one query each — cheap on Postgres.
    orders_by_client: Dict[int, List[Order]] = {}
    for o in db.query(Order).all():
        orders_by_client.setdefault(o.client_id, []).append(o)

    # First inbound per client
    first_inbound_q = (
        db.query(Message.client_id, func.min(Message.sent_at))
        .filter(Message.direction == "in")
        .group_by(Message.client_id)
        .all()
    )
    first_inbound = {cid: ts for cid, ts in first_inbound_q}

    # Avg response time: AVG(out_msg.sent_at - prev_in_msg.sent_at) — keep it
    # simple: per-client, average the time between consecutive in→out pairs.
    avg_response_h: Dict[int, float] = {}
    msgs = (
        db.query(Message.client_id, Message.direction, Message.sent_at)
        .order_by(Message.client_id, Message.sent_at)
        .all()
    )
    by_client: Dict[int, List[tuple]] = {}
    for cid, direction, ts in msgs:
        by_client.setdefault(cid, []).append((direction, ts))
    for cid, items in by_client.items():
        deltas: List[float] = []
        last_in_ts: Optional[datetime] = None
        for direction, ts in items:
            if direction == "in":
                last_in_ts = ts
            elif direction == "out" and last_in_ts:
                delta_h = (ts - last_in_ts).total_seconds() / 3600.0
                if 0 < delta_h < 24 * 14:  # cap at 14 days to drop crazy gaps
                    deltas.append(delta_h)
                last_in_ts = None
        if deltas:
            avg_response_h[cid] = sum(deltas) / len(deltas)

    now = now_georgia()
    rows: List[List[Any]] = [CLIENTS_HEADERS]
    for c in clients:
        rows.append(_build_client_row(
            c,
            enrichments.get(c.id),
            orders_by_client.get(c.id, []),
            first_inbound.get(c.id),
            avg_response_h.get(c.id),
            now,
        ))

    ws = _ensure_worksheet(spreadsheet, CLIENTS_SHEET, CLIENTS_HEADERS)
    ws.clear()
    ws.update("A1", rows, value_input_option="RAW")
    return len(rows) - 1


def export_orders_to_sheet(db: Session, spreadsheet) -> int:
    orders: List[Order] = db.query(Order).all()
    clients = {c.id: c for c in db.query(Client).all()}
    name_by_id = {
        cid: (" ".join(filter(None, [c.first_name, c.last_name])).strip() or c.username or f"client#{cid}")
        for cid, c in clients.items()
    }
    deep_link_by_id = {cid: (_build_deep_link(c) or "") for cid, c in clients.items()}

    rows: List[List[Any]] = [ORDERS_HEADERS]
    for o in orders:
        rows.append(_build_order_row(o, name_by_id, deep_link_by_id))

    ws = _ensure_worksheet(spreadsheet, ORDERS_SHEET, ORDERS_HEADERS)
    ws.clear()
    ws.update("A1", rows, value_input_option="RAW")
    return len(rows) - 1


def append_daily_snapshot(db: Session, spreadsheet) -> bool:
    now = now_georgia()
    today = now.date().isoformat()
    day_ago = now - timedelta(hours=24)
    month_ago = now - timedelta(days=30)

    total_clients = db.query(func.count(Client.id)).scalar() or 0
    active_clients_30d = (
        db.query(func.count(Client.id))
        .filter(Client.last_client_message_at >= month_ago)
        .scalar()
        or 0
    )
    new_clients_24h = (
        db.query(func.count(Client.id))
        .filter(Client.created_at >= day_ago)
        .scalar()
        or 0
    )
    orders_24h = (
        db.query(func.count(Order.id))
        .filter(Order.created_at >= day_ago)
        .scalar()
        or 0
    )
    completed_24h = (
        db.query(func.count(Order.id))
        .filter(Order.completed_at >= day_ago)
        .scalar()
        or 0
    )
    pending_orders = (
        db.query(func.count(Order.id))
        .filter(Order.status == "pending")
        .scalar()
        or 0
    )

    # Approx avg response time from last 24h messages
    avg_resp_q = (
        db.query(Message.client_id, Message.direction, Message.sent_at)
        .filter(Message.sent_at >= day_ago)
        .order_by(Message.client_id, Message.sent_at)
        .all()
    )
    deltas: List[float] = []
    seen_in: Dict[int, datetime] = {}
    for cid, direction, ts in avg_resp_q:
        if direction == "in":
            seen_in[cid] = ts
        elif direction == "out" and cid in seen_in:
            d = (ts - seen_in[cid]).total_seconds() / 3600.0
            if 0 < d < 24:
                deltas.append(d)
            seen_in.pop(cid, None)
    avg_response_h = round(sum(deltas) / len(deltas), 2) if deltas else ""

    # Top niche today
    niche_counts: Dict[str, int] = {}
    enrich_today = (
        db.query(ClientEnrichment.niche)
        .filter(ClientEnrichment.reviewed_at >= day_ago)
        .all()
    )
    for (n,) in enrich_today:
        if n:
            niche_counts[n] = niche_counts.get(n, 0) + 1
    top_niche = max(niche_counts.items(), key=lambda kv: kv[1])[0] if niche_counts else ""

    ws = _ensure_worksheet(spreadsheet, SNAPSHOT_SHEET, SNAPSHOT_HEADERS)
    # Skip if today's row already present.
    existing_dates = ws.col_values(1)[1:]
    if today in existing_dates:
        return False
    ws.append_row([
        today, total_clients, active_clients_30d, new_clients_24h,
        orders_24h, completed_24h, pending_orders, avg_response_h, top_niche,
    ], value_input_option="RAW")
    return True


def export_all() -> Dict[str, Any]:
    started = time.time()
    db = SessionLocal()
    try:
        ss = _open_sheet(db)
        clients_count = export_clients_to_sheet(db, ss)
        orders_count = export_orders_to_sheet(db, ss)
        snapshot_appended = append_daily_snapshot(db, ss)
        duration = round(time.time() - started, 2)
        result = {
            "ok": True,
            "clients_count": clients_count,
            "orders_count": orders_count,
            "snapshot_appended": snapshot_appended,
            "duration_sec": duration,
            "ran_at": now_georgia().isoformat(timespec="seconds"),
        }
        set_setting(db, LAST_RUN_KEY, json.dumps(result, ensure_ascii=False))
        return result
    except Exception as exc:
        duration = round(time.time() - started, 2)
        err = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "duration_sec": duration,
            "ran_at": now_georgia().isoformat(timespec="seconds"),
        }
        try:
            set_setting(db, LAST_RUN_KEY, json.dumps(err, ensure_ascii=False))
        except Exception:
            pass
        logger.exception("Sheets export failed")
        raise
    finally:
        db.close()
