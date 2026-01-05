"""Tags API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.crud import get_tags, create_tag
from app.schemas import TagCreate, TagResponse
from app.api.deps import get_current_user
from app.models import Tag

router = APIRouter()


@router.get("")
async def list_tags(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all tags."""
    tags = get_tags(db)
    return {
        "items": [TagResponse.model_validate(t) for t in tags],
    }


@router.post("", response_model=TagResponse)
async def create_tag_endpoint(
    data: TagCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new tag."""
    # Check if tag exists
    existing = db.query(Tag).filter(Tag.name == data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag already exists",
        )
    
    tag = create_tag(db, data.name, data.color)
    return TagResponse.model_validate(tag)


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a tag."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )
    
    db.delete(tag)
    db.commit()
    
    return {"success": True}
