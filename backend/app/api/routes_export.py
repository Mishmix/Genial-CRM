"""Export API routes."""
import csv
import json
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Order, Message

router = APIRouter(prefix="/export", tags=["export"])


@router.get("")
async def export_data(
    format: str = Query("csv", regex="^(csv|json)$"),
    data_type: str = Query("clients", regex="^(clients|orders|messages)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Export data in CSV or JSON format."""
    
    # Parse dates
    from_date = datetime.fromisoformat(date_from) if date_from else None
    to_date = datetime.fromisoformat(date_to) if date_to else None
    
    if data_type == "clients":
        data = export_clients(db, from_date, to_date, status)
    elif data_type == "orders":
        data = export_orders(db, from_date, to_date)
    else:
        data = export_messages(db, from_date, to_date)
    
    if format == "json":
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode('utf-8')),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=export_{data_type}.json"}
        )
    else:
        # CSV
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),  # BOM for Excel
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=export_{data_type}.csv"}
        )


def export_clients(db: Session, from_date: Optional[datetime], to_date: Optional[datetime], status: Optional[str]):
    """Export clients data."""
    query = db.query(Client)
    
    if from_date:
        query = query.filter(Client.created_at >= from_date)
    if to_date:
        query = query.filter(Client.created_at <= to_date)
    if status:
        query = query.filter(Client.status == status)
    
    clients = query.order_by(Client.created_at.desc()).all()
    
    return [
        {
            "id": c.id,
            "telegram_user_id": c.telegram_user_id,
            "username": c.username or "",
            "first_name": c.first_name,
            "last_name": c.last_name or "",
            "status": c.status,
            "tags": ", ".join(t.name for t in c.tags),
            "notes": c.notes or "",
            "unread_count": c.unread_count,
            "source": c.source or "telegram",
            "language_code": c.language_code or "",
            "lost_reason": c.lost_reason or "",
            "deadline": c.deadline.isoformat() if c.deadline else "",
            "first_seen_at": c.first_seen_at.isoformat() if c.first_seen_at else "",
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else "",
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "is_archived": c.is_archived,
        }
        for c in clients
    ]


def export_orders(db: Session, from_date: Optional[datetime], to_date: Optional[datetime]):
    """Export orders data."""
    query = db.query(Order).join(Client)
    
    if from_date:
        query = query.filter(Order.created_at >= from_date)
    if to_date:
        query = query.filter(Order.created_at <= to_date)
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    return [
        {
            "id": o.id,
            "client_id": o.client_id,
            "client_name": o.client.first_name if o.client else "",
            "client_username": o.client.username if o.client else "",
            "service_type": o.service_type,
            "quantity": o.quantity,
            "amount": o.amount / 100 if o.amount else 0,
            "currency": o.currency,
            "status": o.status,
            "deadline_type": o.deadline_type or "",
            "deadline_date": o.deadline_date.isoformat() if o.deadline_date else "",
            "deadline_range": o.deadline_range or "",
            "notes": o.notes or "",
            "created_at": o.created_at.isoformat() if o.created_at else "",
            "completed_at": o.completed_at.isoformat() if o.completed_at else "",
        }
        for o in orders
    ]


def export_messages(db: Session, from_date: Optional[datetime], to_date: Optional[datetime]):
    """Export messages data."""
    query = db.query(Message).join(Client)
    
    if from_date:
        query = query.filter(Message.sent_at >= from_date)
    if to_date:
        query = query.filter(Message.sent_at <= to_date)
    
    messages = query.order_by(Message.sent_at.desc()).limit(10000).all()
    
    return [
        {
            "id": m.id,
            "client_id": m.client_id,
            "client_name": m.client.first_name if m.client else "",
            "client_username": m.client.username if m.client else "",
            "direction": m.direction,
            "text": m.text or "",
            "telegram_message_id": m.telegram_message_id or "",
            "sent_at": m.sent_at.isoformat() if m.sent_at else "",
        }
        for m in messages
    ]
