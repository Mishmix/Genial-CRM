"""Client enrichment API.

Daily routine pulls a small batch of clients (<=30) and asks the LLM to fill
out a structured profile. Results stored in `client_enrichments`.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes_digest import require_routine_token
from app.db import get_db
from app.models import Client, ClientEnrichment, Message
from app.utils.logging import get_logger
from app.utils.timezone import now_georgia

logger = get_logger(__name__)
router = APIRouter()


# ----------------------------- candidates ----------------------------------


@router.get("/enrichment/candidates", dependencies=[Depends(require_routine_token)])
async def candidates(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    """Return prioritized client_ids that need a fresh AI profile.

    Priority order:
      1. Active in the last 24h AND no enrichment yet.
      2. Created in the last 7 days AND no enrichment yet.
      3. Enrichment older than 60 days.
    Each client surfaces at most once per day (reviewed_at gating).
    """
    now = now_georgia()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    activity_since = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    stale_before = now - timedelta(days=60)

    # Map of existing enrichments
    existing = {
        e.client_id: e
        for e in db.query(ClientEnrichment).all()
    }

    seen: set[int] = set()
    out: List[Dict[str, Any]] = []

    def _take(client: Client, why: str) -> None:
        if client.id in seen or len(out) >= limit:
            return
        # Skip if reviewed today already
        e = existing.get(client.id)
        if e and e.reviewed_at and e.reviewed_at >= today_start:
            return
        msg_count = (
            db.query(func.count(Message.id))
            .filter(Message.client_id == client.id)
            .scalar()
            or 0
        )
        seen.add(client.id)
        out.append({
            "client_id": client.id,
            "name": " ".join(filter(None, [client.first_name, client.last_name])).strip() or "Unknown",
            "telegram_user_id": client.telegram_user_id if client.telegram_user_id and client.telegram_user_id > 0 else None,
            "last_messages_count": int(msg_count),
            "why_priority": why,
        })

    # 1. Active 24h + no enrichment
    rows = (
        db.query(Client)
        .filter(Client.last_client_message_at.isnot(None))
        .filter(Client.last_client_message_at >= activity_since)
        .filter(Client.is_archived == False)  # noqa: E712
        .order_by(desc(Client.last_client_message_at))
        .limit(limit * 3)
        .all()
    )
    for c in rows:
        if c.id not in existing:
            _take(c, "active_24h_no_enrichment")

    # 2. Created last 7 days + no enrichment
    if len(out) < limit:
        rows = (
            db.query(Client)
            .filter(Client.created_at >= week_ago)
            .filter(Client.is_archived == False)  # noqa: E712
            .order_by(desc(Client.created_at))
            .limit(limit * 3)
            .all()
        )
        for c in rows:
            if c.id not in existing:
                _take(c, "new_within_7d")

    # 3. Stale enrichment (>60d)
    if len(out) < limit:
        stale = (
            db.query(ClientEnrichment)
            .filter(ClientEnrichment.reviewed_at.isnot(None))
            .filter(ClientEnrichment.reviewed_at < stale_before)
            .order_by(ClientEnrichment.reviewed_at.asc())
            .limit(limit * 3)
            .all()
        )
        for e in stale:
            client = db.query(Client).filter(Client.id == e.client_id).first()
            if client and not client.is_archived:
                _take(client, "stale_enrichment_60d")

    return out


# ----------------------------- context -------------------------------------


@router.get("/enrichment/client/{client_id}/context", dependencies=[Depends(require_routine_token)])
async def client_context(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    msgs = (
        db.query(Message)
        .filter(Message.client_id == client_id)
        .order_by(desc(Message.sent_at))
        .limit(30)
        .all()
    )
    msgs.reverse()
    enrichment = db.query(ClientEnrichment).filter(ClientEnrichment.client_id == client_id).first()
    return {
        "profile": {
            "id": client.id,
            "name": " ".join(filter(None, [client.first_name, client.last_name])).strip() or "Unknown",
            "username": client.username,
            "telegram_user_id": client.telegram_user_id if client.telegram_user_id and client.telegram_user_id > 0 else None,
            "language_code": client.language_code,
            "status": client.status,
            "total_orders": client.total_orders or 0,
            "total_spent": client.total_spent or 0,
            "tags": [t.name for t in (client.tags or [])],
            "first_seen_at": client.first_seen_at.isoformat() if client.first_seen_at else None,
            "last_client_message_at": client.last_client_message_at.isoformat() if client.last_client_message_at else None,
            "notes": client.notes,
        },
        "last_messages": [
            {
                "direction": m.direction,
                "type": m.message_type or "text",
                "content": (m.transcription if m.message_type == "voice" else m.text) or "",
                "created_at": m.sent_at.isoformat() if m.sent_at else None,
            }
            for m in msgs
        ],
        "existing_enrichment": _serialize_enrichment(enrichment) if enrichment else None,
    }


# ------------------------------ save ---------------------------------------


class EnrichmentSave(BaseModel):
    client_id: int
    niche: Optional[str] = None
    channel_name: Optional[str] = None
    channel_size_bucket: Optional[str] = None
    temperature: Optional[str] = None
    communication_style: Optional[str] = None
    price_sensitivity: Optional[str] = None
    decision_speed: Optional[str] = None
    last_summary: Optional[str] = None
    pain_points: Optional[List[str]] = None
    value_drivers: Optional[List[str]] = None
    next_best_action: Optional[str] = None
    ai_notes: Optional[str] = None


@router.post("/enrichment/save", dependencies=[Depends(require_routine_token)])
async def save_enrichment(payload: EnrichmentSave, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    e = db.query(ClientEnrichment).filter(ClientEnrichment.client_id == payload.client_id).first()
    if not e:
        e = ClientEnrichment(client_id=payload.client_id)
        db.add(e)
    for field in (
        "niche", "channel_name", "channel_size_bucket", "temperature",
        "communication_style", "price_sensitivity", "decision_speed",
        "last_summary", "pain_points", "value_drivers", "next_best_action",
        "ai_notes",
    ):
        val = getattr(payload, field)
        if val is not None:
            setattr(e, field, val)
    e.reviewed_at = now_georgia()
    db.commit()
    db.refresh(e)
    return {"ok": True, "client_id": payload.client_id, "id": e.id, "reviewed_at": e.reviewed_at.isoformat()}


# -------------------------- read for Mini App ------------------------------


@router.get("/enrichment/{client_id}")
async def get_enrichment(
    client_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    e = db.query(ClientEnrichment).filter(ClientEnrichment.client_id == client_id).first()
    if not e:
        return None
    return _serialize_enrichment(e)


@router.post("/enrichment/{client_id}/refresh")
async def refresh_enrichment(
    client_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Bump this client to the front of the next enrichment run by clearing reviewed_at."""
    e = db.query(ClientEnrichment).filter(ClientEnrichment.client_id == client_id).first()
    if e:
        e.reviewed_at = None
        db.commit()
    return {"ok": True, "queued": True}


def _serialize_enrichment(e: ClientEnrichment) -> Dict[str, Any]:
    return {
        "client_id": e.client_id,
        "niche": e.niche,
        "channel_name": e.channel_name,
        "channel_size_bucket": e.channel_size_bucket,
        "temperature": e.temperature,
        "communication_style": e.communication_style,
        "price_sensitivity": e.price_sensitivity,
        "decision_speed": e.decision_speed,
        "last_summary": e.last_summary,
        "pain_points": e.pain_points or [],
        "value_drivers": e.value_drivers or [],
        "next_best_action": e.next_best_action,
        "ai_notes": e.ai_notes,
        "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }
