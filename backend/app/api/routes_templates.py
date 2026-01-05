"""Templates API routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.crud import get_templates, create_template, update_template
from app.schemas import TemplateCreate, TemplateUpdate, TemplateResponse
from app.api.deps import get_current_user
from app.models import Template

router = APIRouter()


@router.get("")
async def list_templates(
    language: Optional[str] = None,
    is_auto_reply: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all templates."""
    templates = get_templates(db, language, is_auto_reply)
    return {
        "items": [TemplateResponse.model_validate(t) for t in templates],
    }


@router.post("", response_model=TemplateResponse)
async def create_template_endpoint(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new template."""
    template = create_template(db, data)
    return TemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a template by ID."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return TemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template_endpoint(
    template_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a template."""
    template = update_template(db, template_id, data)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a template."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    
    db.delete(template)
    db.commit()
    
    return {"success": True}
