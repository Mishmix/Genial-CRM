"""Money-at-Risk: warm conversations where money is stuck silent."""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.crud import get_setting
from app.models import Client, ClientEnrichment, Conversation, Message
from app.utils.logging import get_logger

logger = get_logger(__name__)


PRICING_KEYWORDS = [
    "цен", "стоит", "сколько", "оплат", "счёт", "счет", "договорим",
    "запиши", "слот", "когда сможете", "когда смож", "оффер", "пакет",
    "скидк", "предлож", "бюджет",
    "price", "cost", "how much", "quote", "rate", "package", "discount",
    "offer", "budget", "invoice", "payment",
    "ціна", "вартість", "скільки",
]


@dataclass
class MoneyAtRiskItem:
    client_id: int
    client_name: str
    deep_link: Optional[str]
    risk_type: str
    last_outbound_at: Optional[str]
    last_inbound_at: Optional[str]
    hours_silent: int
    conversation_excerpt: str
    pricing_signal_text: str
    estimated_amount: Optional[float]
    suggested_action: str
    suggested_message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _deep_link(c: Client) -> Optional[str]:
    if c.telegram_user_id and c.telegram_user_id > 0:
        return f"tg://user?id={c.telegram_user_id}"
    if c.username:
        return f"https://t.me/{c.username}"
    return None


def _has_pricing_signal(text: Optional[str]) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(kw in low for kw in PRICING_KEYWORDS)


def _excerpt_messages(msgs: List[Message]) -> str:
    """Last 3-5 messages compactly: 'Я: ... / Клиент: ...'."""
    parts: List[str] = []
    for m in msgs[-5:]:
        who = "Я" if m.direction == "out" else "Клиент"
        text = (m.transcription if m.message_type == "voice" else m.text) or ""
        text = text.replace("\n", " ").strip()
        if len(text) > 120:
            text = text[:120] + "…"
        parts.append(f"{who}: {text}")
    return " / ".join(parts)


def _working_hours_silent(since: datetime, now: datetime) -> int:
    """Count clock hours between since→now but only in 09:00-21:00 local window."""
    if not since or since >= now:
        return 0
    total = 0
    cur = since
    while cur < now:
        if 9 <= cur.hour < 21:
            total += 1
        cur += timedelta(hours=1)
    return total


def _avg_check(c: Client) -> Optional[float]:
    if not c.total_orders or not c.total_spent:
        return None
    return round(float(c.total_spent) / max(c.total_orders, 1), 2)


def _suggested_for_offer(first_name: str) -> str:
    return f"Привет, {first_name or 'друг'}! Составляю график на неделю — оставлять за тобой слот?"


def _suggested_for_pricing(first_name: str) -> str:
    return f"Привет, {first_name or 'друг'}! Только увидел — сейчас отвечу подробно по цене"


async def detect_money_at_risk(
    db: Session, now: datetime, top_n: int = 7,
) -> List[Dict[str, Any]]:
    """See module docstring. Returns serialized list ready for digest_data."""
    no_reply_hours_threshold = int(get_setting(db, "money_at_risk_no_reply_hours") or 12)

    # Pool: conversations not closed
    pool = (
        db.query(Conversation)
        .filter(Conversation.status.notin_(["ordered", "rejected", "archived", "completed"]))
        .filter(Conversation.is_deleted == False)  # noqa: E712
        .all()
    )

    items: List[MoneyAtRiskItem] = []
    for conv in pool:
        msgs = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.sent_at.asc())
            .all()
        )
        if len(msgs) < 5:
            continue

        last_out = next((m for m in reversed(msgs) if m.direction == "out"), None)
        last_in = next((m for m in reversed(msgs) if m.direction == "in"), None)
        if not (last_out or last_in):
            continue

        client = db.query(Client).filter(Client.id == conv.client_id).first()
        if not client or client.is_archived:
            continue

        last10 = msgs[-10:]
        pricing_msg = next(
            (m for m in reversed(last10) if _has_pricing_signal(m.text or m.transcription)),
            None,
        )
        if not pricing_msg:
            continue

        risk_type: Optional[str] = None
        suggested = ""
        action = ""
        hours = 0

        # Type A: I sent the offer 48-96h ago and client hasn't replied since
        if last_out and (not last_in or last_in.sent_at <= last_out.sent_at):
            age_h = int((now - last_out.sent_at).total_seconds() / 3600)
            if 48 <= age_h <= 96:
                risk_type = "no_reply_after_offer"
                hours = age_h
                action = "напомнить про слот"
                suggested = _suggested_for_offer(client.first_name or "")

        # Type B: client asked about price, I haven't replied (>X working hours)
        if (
            risk_type is None
            and last_in
            and (not last_out or last_out.sent_at < last_in.sent_at)
            and _has_pricing_signal(last_in.text or last_in.transcription)
        ):
            wh = _working_hours_silent(last_in.sent_at, now)
            if wh >= no_reply_hours_threshold:
                risk_type = "no_owner_reply_to_pricing"
                hours = wh
                action = "ответить на ценовой вопрос"
                suggested = _suggested_for_pricing(client.first_name or "")

        if risk_type is None:
            continue

        excerpt = _excerpt_messages(msgs)
        pricing_text = (pricing_msg.text or pricing_msg.transcription or "")[:200]

        items.append(MoneyAtRiskItem(
            client_id=client.id,
            client_name=" ".join(filter(None, [client.first_name, client.last_name])).strip() or "Unknown",
            deep_link=_deep_link(client),
            risk_type=risk_type,
            last_outbound_at=last_out.sent_at.isoformat() if last_out else None,
            last_inbound_at=last_in.sent_at.isoformat() if last_in else None,
            hours_silent=hours,
            conversation_excerpt=excerpt,
            pricing_signal_text=pricing_text,
            estimated_amount=_avg_check(client),
            suggested_action=action,
            suggested_message=suggested,
        ))

    # Ranking: hot enrichment > LTV > conversation depth
    enrich_temp_by_client = {
        e.client_id: e.temperature
        for e in db.query(ClientEnrichment).all()
    }

    def _rank(it: MoneyAtRiskItem) -> tuple:
        c = db.query(Client).filter(Client.id == it.client_id).first()
        ltv = float(c.total_spent or 0) if c else 0
        is_hot = enrich_temp_by_client.get(it.client_id) == "hot"
        msg_count = (
            db.query(Message).filter(Message.client_id == it.client_id).count()
        )
        return (-int(is_hot), -ltv, -msg_count)

    items.sort(key=_rank)
    return [it.to_dict() for it in items[:top_n]]
