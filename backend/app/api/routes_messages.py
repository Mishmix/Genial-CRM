"""Messages API routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.crud import get_client_messages
from app.schemas import MessageResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/{client_id}")
async def get_messages(
    client_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get messages for a client."""
    messages = get_client_messages(db, client_id, limit)
    return {
        "items": [MessageResponse.model_validate(m) for m in messages],
        "client_id": client_id,
    }
