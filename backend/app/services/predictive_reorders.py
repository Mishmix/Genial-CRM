"""Predictive Reorders: regulars whose interval is stable and due now."""
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.crud import get_setting
from app.models import Client, Order
from app.utils.logging import get_logger

logger = get_logger(__name__)

SERVICE_RU = {
    "thumbnail": "превью",
    "banner": "баннер",
    "logo": "лого",
    "channel_design": "оформление канала",
    "avatar": "аватар",
    "cover": "обложка",
    "template": "шаблоны",
    "other": "что-то",
}


@dataclass
class PredictiveReorderItem:
    client_id: int
    client_name: str
    deep_link: Optional[str]
    completed_orders: int
    avg_interval_days: float
    cv: float
    last_order_at: str
    days_since_last_order: int
    expected_at: str
    overdue_pct: float
    avg_check: Optional[float]
    typical_service: Optional[str]
    suggested_message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _deep_link(c: Client) -> Optional[str]:
    if c.telegram_user_id and c.telegram_user_id > 0:
        return f"tg://user?id={c.telegram_user_id}"
    if c.username:
        return f"https://t.me/{c.username}"
    return None


def _suggested_message(first_name: str, avg_days: float, days_since: int, service: Optional[str]) -> str:
    name = first_name or "друг"
    svc = SERVICE_RU.get(service or "other", "превью")
    return (
        f"Привет, {name}! Обычно делаем {svc} раз в {int(round(avg_days))} дней — "
        f"уже {days_since} прошло. Готовить слот на ближайшие дни?"
    )


async def detect_predictive_reorders(
    db: Session, now: datetime, top_n: int = 7,
) -> List[Dict[str, Any]]:
    min_orders = int(get_setting(db, "predictive_min_orders") or 3)
    max_cv = float(get_setting(db, "predictive_max_cv") or 0.4)
    quiet_window = timedelta(days=7)

    candidates: List[PredictiveReorderItem] = []

    for client in db.query(Client).filter(Client.is_archived == False).all():  # noqa: E712
        completed = (
            db.query(Order)
            .filter(Order.client_id == client.id)
            .filter(Order.status == "completed")
            .order_by(Order.created_at.asc())
            .all()
        )
        if len(completed) < min_orders:
            continue

        timestamps = [o.created_at for o in completed if o.created_at]
        if len(timestamps) < min_orders:
            continue

        intervals_days = [
            (timestamps[i + 1] - timestamps[i]).total_seconds() / 86400.0
            for i in range(len(timestamps) - 1)
        ]
        if not intervals_days or any(d <= 0 for d in intervals_days):
            continue
        avg = statistics.mean(intervals_days)
        if avg <= 0:
            continue
        std = statistics.pstdev(intervals_days) if len(intervals_days) > 1 else 0.0
        cv = std / avg
        if cv > max_cv:
            continue

        last_order_at = timestamps[-1]
        days_since = (now - last_order_at).days
        overdue_pct = (days_since - avg) / avg
        if overdue_pct < -0.2 or overdue_pct > 1.5:
            continue

        # Quiet window: no recent in/out activity (avoid pinging during live convo)
        if client.last_client_message_at and (now - client.last_client_message_at) < quiet_window:
            continue
        if client.last_message_at and (now - client.last_message_at) < quiet_window:
            continue

        # Typical service = mode of completed Order.service_type
        services = [o.service_type for o in completed if o.service_type]
        typical = max(set(services), key=services.count) if services else None

        avg_check = (
            round(float(client.total_spent) / max(client.total_orders, 1), 2)
            if client.total_spent and client.total_orders
            else None
        )

        candidates.append(PredictiveReorderItem(
            client_id=client.id,
            client_name=" ".join(filter(None, [client.first_name, client.last_name])).strip() or "Unknown",
            deep_link=_deep_link(client),
            completed_orders=len(completed),
            avg_interval_days=round(avg, 1),
            cv=round(cv, 3),
            last_order_at=last_order_at.isoformat(),
            days_since_last_order=days_since,
            expected_at=(last_order_at + timedelta(days=avg)).isoformat(),
            overdue_pct=round(overdue_pct, 3),
            avg_check=avg_check,
            typical_service=typical,
            suggested_message=_suggested_message(client.first_name or "", avg, days_since, typical),
        ))

    candidates.sort(key=lambda it: (-(it.avg_check or 0), -it.overdue_pct))
    return [it.to_dict() for it in candidates[:top_n]]
