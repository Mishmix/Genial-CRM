"""Clients API routes."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.crud import (
    get_clients, get_client, update_client, mark_client_read,
    search_clients, create_message, archive_client, unarchive_client, delete_client, merge_clients,
    create_manual_client,
)
from app.models import Message, Client
from app.schemas import (
    ClientListItem, ClientDetail, ClientUpdate, ClientsListResponse,
    MessageCreate, MessageResponse, MergeClientsRequest, ManualClientCreate,
)
from app.api.deps import get_current_user
from app.telegram.bot import send_message
from app.telegram.avatars import get_or_fetch_avatar, get_avatar_url
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_clients_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get client statistics."""
    total = db.query(func.count(Client.id)).filter(Client.is_archived == False).scalar() or 0
    new_count = db.query(func.count(Client.id)).filter(Client.status == 'new', Client.is_archived == False).scalar() or 0
    sent_price = db.query(func.count(Client.id)).filter(Client.status == 'sent_price', Client.is_archived == False).scalar() or 0
    rejected = db.query(func.count(Client.id)).filter(Client.status == 'rejected', Client.is_archived == False).scalar() or 0
    unread = db.query(func.count(Client.id)).filter(Client.unread_count > 0, Client.is_archived == False).scalar() or 0
    
    # Count active orders (not deleted, not cancelled)
    from app.models import Order
    orders_count = db.query(func.count(Order.id)).filter(
        Order.status.notin_(['deleted', 'cancelled'])
    ).scalar() or 0
    
    return {
        "total": total,
        "new": new_count,
        "sent_price": sent_price,
        "ordered": orders_count,  # Now counts actual orders, not client status
        "rejected": rejected,
        "unread": unread,
    }


def add_message_counts(db: Session, clients: list) -> list:
    """Add message_count to each client."""
    if not clients:
        return clients
    
    client_ids = [c.id for c in clients]
    counts = db.query(
        Message.client_id,
        func.count(Message.id).label('count')
    ).filter(
        Message.client_id.in_(client_ids),
        Message.direction == 'in'
    ).group_by(Message.client_id).all()
    
    count_map = {c.client_id: c.count for c in counts}
    
    result = []
    for c in clients:
        item = ClientListItem.model_validate(c)
        item.message_count = count_map.get(c.id, 0)
        result.append(item)
    
    return result


@router.get("", response_model=ClientsListResponse)
async def list_clients(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    has_unread: Optional[bool] = None,
    tag_ids: Optional[str] = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get paginated list of clients."""
    skip = (page - 1) * per_page
    
    # Parse tag_ids if provided
    tag_id_list = None
    if tag_ids:
        tag_id_list = [int(x) for x in tag_ids.split(",") if x.strip()]
    
    clients, total = get_clients(
        db,
        skip=skip,
        limit=per_page,
        status=status,
        has_unread=has_unread,
        tag_ids=tag_id_list,
        include_archived=include_archived,
    )
    
    items = add_message_counts(db, clients)
    
    return ClientsListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/search")
async def search_clients_endpoint(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Search clients with fuzzy matching."""
    clients = search_clients(db, q)
    items = add_message_counts(db, clients)
    return {
        "items": items,
        "query": q,
    }


@router.get("/{client_id}", response_model=ClientDetail)
async def get_client_detail(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get client details with messages."""
    client = get_client(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return ClientDetail.model_validate(client)


@router.patch("/{client_id}", response_model=ClientDetail)
async def update_client_endpoint(
    client_id: int,
    data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update client CRM fields (status, notes, tags)."""
    client = update_client(db, client_id, data)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    # Reload with relationships
    client = get_client(db, client_id)
    
    # Broadcast client update to WebSocket clients
    try:
        import asyncio
        from app.api.websocket import broadcast_update
        asyncio.create_task(broadcast_update("client_updated", {
            "client": {
                "id": client.id,
                "telegram_user_id": client.telegram_user_id,
                "first_name": client.first_name,
                "last_name": client.last_name,
                "username": client.username,
                "status": client.status,
                "unread_count": client.unread_count,
                "avatar_local_path": client.avatar_local_path,
                "is_archived": client.is_archived,
                "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in client.tags] if client.tags else [],
            }
        }))
    except Exception as e:
        logger.error(f"Failed to broadcast client update: {e}")
    
    return ClientDetail.model_validate(client)


@router.post("/{client_id}/read")
async def mark_as_read(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark all messages as read for client."""
    client = mark_client_read(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return {"success": True, "unread_count": 0}


@router.post("/{client_id}/send", response_model=MessageResponse)
async def send_message_to_client(
    client_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Send a message to client via Telegram."""
    client = get_client(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    # Send via Telegram
    message_id = await send_message(
        chat_id=client.telegram_user_id,
        text=data.text,
        business_connection_id=client.business_connection_id,
    )
    
    if not message_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message",
        )
    
    # Save to database
    message = create_message(
        db,
        client_id=client.id,
        direction="out",
        text=data.text,
        telegram_message_id=message_id,
    )
    
    logger.info(f"Sent message to client {client_id}")
    
    return MessageResponse.model_validate(message)


@router.post("/{client_id}/archive")
async def archive_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Archive a client."""
    client = archive_client(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return {"success": True, "archived": True}


@router.post("/{client_id}/unarchive")
async def unarchive_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Unarchive a client."""
    client = unarchive_client(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return {"success": True, "archived": False}


@router.delete("/{client_id}")
async def delete_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Permanently delete a client."""
    success = delete_client(db, client_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return {"success": True, "deleted": True}


@router.post("/merge")
async def merge_clients_endpoint(
    data: MergeClientsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Merge multiple clients into one."""
    client = merge_clients(db, data.source_client_ids, data.target_client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target client not found",
        )
    
    return ClientDetail.model_validate(client)


@router.post("/manual", response_model=ClientDetail)
async def create_manual_client_endpoint(
    data: ManualClientCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a client manually (WhatsApp, Instagram, etc.)."""
    client = create_manual_client(
        db,
        first_name=data.first_name,
        last_name=data.last_name,
        username=data.username,
        source=data.source,
        phone=data.phone,
        notes=data.notes,
    )
    
    # Reload with relationships
    client = get_client(db, client.id)
    return ClientDetail.model_validate(client)


@router.post("/{client_id}/fetch-avatar")
async def fetch_client_avatar(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Fetch and cache avatar for a client from Telegram."""
    client = get_client(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    # Skip manual clients (negative telegram_user_id)
    if client.telegram_user_id < 0:
        return {"success": False, "message": "Manual client, no Telegram avatar"}
    
    # Fetch avatar
    local_path = await get_or_fetch_avatar(client.telegram_user_id, force_refresh=True)
    
    if local_path:
        # Update client record
        client.avatar_local_path = get_avatar_url(client.telegram_user_id)
        db.commit()
        return {"success": True, "avatar_url": client.avatar_local_path}
    
    return {"success": False, "message": "No avatar found"}
