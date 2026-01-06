"""API routes for conversations."""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_, or_

from app.db import get_db
from app.models import Conversation, Client, Order, Message
from app.schemas import (
    ConversationCreate, ConversationUpdate, ConversationResponse,
    ConversationListResponse, ConversationDetailResponse
)
from app.utils.timezone import now_georgia

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
def get_conversations(
    status: Optional[str] = None,
    category: Optional[str] = None,
    period: Optional[str] = None,  # 24h, 48h, 7d, 30d
    has_unread: Optional[bool] = None,
    include_deleted: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get list of conversations with filters."""
    query = db.query(Conversation).options(
        joinedload(Conversation.client).joinedload(Client.tags),
        joinedload(Conversation.orders)
    )
    
    # Filter deleted
    if not include_deleted:
        query = query.filter(Conversation.is_deleted == False)
    
    # Filter by status
    if status:
        query = query.filter(Conversation.status == status)
    
    # Filter by category
    if category:
        query = query.filter(Conversation.category == category)
    
    # Filter by period
    if period:
        now = now_georgia()
        if period == "24h":
            since = now - timedelta(hours=24)
        elif period == "48h":
            since = now - timedelta(hours=48)
        elif period == "7d":
            since = now - timedelta(days=7)
        elif period == "30d":
            since = now - timedelta(days=30)
        else:
            since = None
        
        if since:
            query = query.filter(Conversation.created_at >= since)
    
    # Filter by unread
    if has_unread:
        query = query.filter(Conversation.unread_count > 0)
    
    # Get total count
    total = query.count()
    
    # Order by most recent and paginate
    conversations = query.order_by(desc(Conversation.updated_at)).offset(skip).limit(limit).all()
    
    return ConversationListResponse(
        items=[_conversation_to_response(c) for c in conversations],
        total=total
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Get conversation details with messages and orders."""
    conversation = db.query(Conversation).options(
        joinedload(Conversation.client).joinedload(Client.tags),
        joinedload(Conversation.orders),
        joinedload(Conversation.reminders)
    ).filter(Conversation.id == conversation_id).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get messages for this conversation
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sent_at).all()
    
    return ConversationDetailResponse(
        **_conversation_to_response(conversation).dict(),
        messages=[{
            "id": m.id,
            "direction": m.direction,
            "text": m.text,
            "message_type": m.message_type,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None
        } for m in messages]
    )


@router.post("", response_model=ConversationResponse)
def create_conversation(data: ConversationCreate, db: Session = Depends(get_db)):
    """Create a new conversation manually."""
    # Verify client exists
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    conversation = Conversation(
        client_id=data.client_id,
        source=data.source or "manual",
        category=data.category,
        status="new",
        started_at=now_georgia()
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return _conversation_to_response(conversation)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    db: Session = Depends(get_db)
):
    """Update conversation status, category, or rejection reason."""
    conversation = db.query(Conversation).options(
        joinedload(Conversation.client)
    ).filter(Conversation.id == conversation_id).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Update fields
    if data.status is not None:
        conversation.status = data.status
        
        # If status is rejected, require rejection reason
        if data.status == "rejected" and data.rejection_reason:
            conversation.rejection_reason = data.rejection_reason
            conversation.rejection_custom = data.rejection_custom
    
    if data.category is not None:
        conversation.category = data.category
    
    if data.rejection_reason is not None:
        conversation.rejection_reason = data.rejection_reason
        conversation.rejection_custom = data.rejection_custom
    
    conversation.updated_at = now_georgia()
    db.commit()
    db.refresh(conversation)
    
    return _conversation_to_response(conversation)


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Soft delete a conversation."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation.is_deleted = True
    conversation.deletion_reason = reason
    conversation.updated_at = now_georgia()
    
    db.commit()
    
    return {"success": True, "message": "Conversation deleted"}


@router.post("/{conversation_id}/mark-read")
def mark_conversation_read(conversation_id: int, db: Session = Depends(get_db)):
    """Mark all messages in conversation as read."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation.unread_count = 0
    conversation.updated_at = now_georgia()
    
    # Also update client's unread count
    client = db.query(Client).filter(Client.id == conversation.client_id).first()
    if client:
        # Recalculate total unread from all conversations
        total_unread = db.query(Conversation).filter(
            Conversation.client_id == client.id,
            Conversation.is_deleted == False
        ).with_entities(Conversation.unread_count).all()
        client.unread_count = sum(c.unread_count for c in total_unread)
    
    db.commit()
    
    return {"success": True}


@router.post("/{conversation_id}/analyze-order")
async def analyze_order(conversation_id: int, db: Session = Depends(get_db)):
    """
    Запустить AI анализ переписки для определения заказа.
    Используется когда нужно вручную проанализировать обращение.
    """
    from app.llm.order_detector import detect_order
    from app.crud import create_ai_order, get_setting, get_client
    from app.integrations.todoist import create_task_from_order
    import logging
    logger = logging.getLogger(__name__)
    
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Получаем сообщения
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sent_at.asc()).all()
    
    if len(messages) < 1:
        return {
            "success": False,
            "message": "Нет сообщений для анализа"
        }
    
    # Форматируем для детектора
    messages_data = [
        {
            "direction": m.direction,
            "text": m.text,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None
        }
        for m in messages
    ]
    
    # Детектим заказ
    order_data = await detect_order(messages_data)
    
    if not order_data:
        return {
            "success": False,
            "message": "AI не обнаружил заказ в переписке"
        }
    
    # Создаём заказ
    order = create_ai_order(db, conversation.client_id, conversation_id, order_data)
    
    if order:
        # Создаём задачу в Todoist если интеграция включена
        try:
            todoist_enabled = get_setting(db, "todoist_enabled") == "true"
            if todoist_enabled:
                api_token = get_setting(db, "todoist_api_token")
                project_id = get_setting(db, "todoist_project_id")
                section_today_id = get_setting(db, "todoist_section_today_id")
                section_not_today_id = get_setting(db, "todoist_section_not_today_id")
                
                if api_token and project_id and section_today_id and section_not_today_id:
                    client = get_client(db, order.client_id)
                    if client:
                        client_name = f"{client.first_name} {client.last_name or ''}".strip()
                        
                        result = await create_task_from_order(
                            api_token=api_token,
                            project_id=project_id,
                            section_today_id=section_today_id,
                            section_not_today_id=section_not_today_id,
                            client_name=client_name,
                            service_type=order.service_type,
                            quantity=order.quantity,
                            deadline=order.deadline_date
                        )
                        if result:
                            # Сохраняем ID задачи Todoist
                            order.todoist_task_id = result.get("id")
                            db.commit()
                            logger.info(f"Created Todoist task {result.get('id')} for AI order {order.id}")
        except Exception as e:
            logger.error(f"Failed to create Todoist task: {e}")
        
        return {
            "success": True,
            "message": f"Создан заказ: {order.service_type} x{order.quantity}",
            "order": {
                "id": order.id,
                "service_type": order.service_type,
                "quantity": order.quantity,
                "deadline_date": order.deadline_date.isoformat() if order.deadline_date else None,
                "confidence": order.ai_confidence
            }
        }
    else:
        return {
            "success": False,
            "message": "Заказ не создан (возможно дубликат)"
        }


def _conversation_to_response(conversation: Conversation) -> ConversationResponse:
    """Convert Conversation model to response schema."""
    client = conversation.client
    all_orders = conversation.orders if conversation.orders else []
    
    # Filter out deleted and cancelled orders
    orders = [o for o in all_orders if o.status not in ('deleted', 'cancelled')]
    
    # Calculate total amount from active orders only
    total_amount = sum(o.amount or 0 for o in orders)
    
    return ConversationResponse(
        id=conversation.id,
        client_id=conversation.client_id,
        source=conversation.source,
        category=conversation.category,
        status=conversation.status,
        rejection_reason=conversation.rejection_reason,
        rejection_custom=conversation.rejection_custom,
        unread_count=conversation.unread_count,
        auto_reply_sent=conversation.auto_reply_sent,
        owner_replied=conversation.owner_replied,
        started_at=conversation.started_at.isoformat() if conversation.started_at else None,
        owner_replied_at=conversation.owner_replied_at.isoformat() if conversation.owner_replied_at else None,
        created_at=conversation.created_at.isoformat() if conversation.created_at else None,
        updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
        # Client info
        client={
            "id": client.id,
            "telegram_user_id": client.telegram_user_id,
            "username": client.username,
            "first_name": client.first_name,
            "last_name": client.last_name,
            "avatar_local_path": client.avatar_local_path,
            "status": client.status,
            "sticky_note": client.sticky_note,
            "total_orders": client.total_orders,
            "total_spent": client.total_spent,
            "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in client.tags] if client.tags else []
        } if client else None,
        # Orders summary
        orders_count=len(orders),
        total_amount=total_amount
    )
