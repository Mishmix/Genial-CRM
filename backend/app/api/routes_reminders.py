"""Reminders API routes."""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.crud import (
    get_reminders, get_pending_reminders, create_reminder,
    update_reminder, complete_reminder, delete_reminder,
)
from app.schemas import ReminderCreate, ReminderUpdate, ReminderResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=list[ReminderResponse])
async def list_reminders(
    client_id: Optional[int] = None,
    is_completed: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get reminders with optional filters."""
    reminders = get_reminders(db, client_id=client_id, is_completed=is_completed)
    return [ReminderResponse.model_validate(r) for r in reminders]


@router.get("/pending", response_model=list[ReminderResponse])
async def list_pending_reminders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all pending reminders that are due."""
    reminders = get_pending_reminders(db)
    return [ReminderResponse.model_validate(r) for r in reminders]


@router.post("", response_model=ReminderResponse)
async def create_reminder_endpoint(
    data: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new reminder."""
    reminder = create_reminder(db, data)
    return ReminderResponse.model_validate(reminder)


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder_endpoint(
    reminder_id: int,
    data: ReminderUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a reminder."""
    reminder = update_reminder(db, reminder_id, data)
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found",
        )
    return ReminderResponse.model_validate(reminder)


@router.post("/{reminder_id}/complete", response_model=ReminderResponse)
async def complete_reminder_endpoint(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark a reminder as completed."""
    reminder = complete_reminder(db, reminder_id)
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found",
        )
    return ReminderResponse.model_validate(reminder)


@router.delete("/{reminder_id}")
async def delete_reminder_endpoint(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a reminder."""
    success = delete_reminder(db, reminder_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found",
        )
    return {"success": True}
