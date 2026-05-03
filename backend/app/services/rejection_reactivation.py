"""Rejection Re-engagement: surface rejected conversations ripe to retry."""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.crud import get_setting
from app.llm.rejection_classifier import CATEGORY_LABEL_RU
from app.models import Client, Conversation, Order, Template
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReactivationItem:
    conversation_id: int
    client_id: int
    client_name: str
    deep_link: Optional[str]
    rejected_at: str
    days_since_rejection: int
    normalized_category: str
    category_label: str
    raw_reason_excerpt: str
    reactivation_attempts: int
    last_attempt_at: Optional[str]
    suggested_template_id: Optional[int]
    suggested_template_preview: str
    avg_check: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _deep_link(c: Client) -> Optional[str]:
    if c.telegram_user_id and c.telegram_user_id > 0:
        return f"tg://user?id={c.telegram_user_id}"
    if c.username:
        return f"https://t.me/{c.username}"
    return None


def _pick_template(db: Session, category: str, language: Optional[str]) -> Optional[Template]:
    target_cat = f"reactivation_{category}"
    q = db.query(Template).filter(Template.category == target_cat, Template.is_active == True)  # noqa: E712
    if language:
        t = q.filter(Template.language == language).first()
        if t:
            return t
    # Fallback: ru → en
    for lang in ("ru", "en"):
        t = (
            db.query(Template)
            .filter(Template.category == target_cat, Template.is_active == True, Template.language == lang)  # noqa: E712
            .first()
        )
        if t:
            return t
    return None


async def detect_reactivation_candidates(
    db: Session, now: datetime, top_n: int = 5,
) -> List[Dict[str, Any]]:
    cooldown_days = int(get_setting(db, "reactivation_cooldown_days") or 14)
    max_attempts = int(get_setting(db, "reactivation_max_attempts") or 2)

    # Conversations that are (a) rejected (b) classified non-other (c) old enough (d) cool
    convs = (
        db.query(Conversation)
        .filter(Conversation.status == "rejected")
        .filter(Conversation.rejection_normalized_category.isnot(None))
        .filter(Conversation.rejection_normalized_category != "other")
        .filter(Conversation.is_deleted == False)  # noqa: E712
        .filter(Conversation.reactivation_attempts < max_attempts)
        .all()
    )

    items: List[ReactivationItem] = []
    for conv in convs:
        rejected_at = conv.updated_at or conv.created_at
        if not rejected_at:
            continue
        days_since = (now - rejected_at).days
        if days_since < cooldown_days or days_since > 90:
            continue
        if conv.last_reactivation_at and (now - conv.last_reactivation_at) < timedelta(days=30):
            continue

        # Skip if client placed any new order after rejection
        new_order = (
            db.query(Order)
            .filter(Order.client_id == conv.client_id)
            .filter(Order.created_at > rejected_at)
            .first()
        )
        if new_order:
            continue

        client = db.query(Client).filter(Client.id == conv.client_id).first()
        if not client or client.is_archived:
            continue

        cat = conv.rejection_normalized_category
        tmpl = _pick_template(db, cat, client.language_code)
        preview = ""
        tmpl_id = None
        if tmpl:
            tmpl_id = tmpl.id
            content = (tmpl.content or "").replace("{first_name}", client.first_name or "друг")
            preview = content[:120] + ("…" if len(content) > 120 else "")

        avg_check = (
            round(float(client.total_spent) / max(client.total_orders, 1), 2)
            if client.total_spent and client.total_orders
            else None
        )

        items.append(ReactivationItem(
            conversation_id=conv.id,
            client_id=client.id,
            client_name=" ".join(filter(None, [client.first_name, client.last_name])).strip() or "Unknown",
            deep_link=_deep_link(client),
            rejected_at=rejected_at.isoformat(),
            days_since_rejection=days_since,
            normalized_category=cat,
            category_label=CATEGORY_LABEL_RU.get(cat, cat),
            raw_reason_excerpt=(conv.rejection_custom or conv.rejection_reason or "")[:160],
            reactivation_attempts=conv.reactivation_attempts or 0,
            last_attempt_at=conv.last_reactivation_at.isoformat() if conv.last_reactivation_at else None,
            suggested_template_id=tmpl_id,
            suggested_template_preview=preview,
            avg_check=avg_check,
        ))

    # Ranking: confidence DESC implicit (already non-other), avg_check DESC, attempts ASC
    items.sort(key=lambda it: (-(it.avg_check or 0), it.reactivation_attempts))
    return [it.to_dict() for it in items[:top_n]]
