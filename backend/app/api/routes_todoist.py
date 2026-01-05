"""Todoist API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.db import get_db
from app.crud import get_setting, set_setting
from app.api.deps import get_current_user
from app.integrations.todoist import TodoistClient, get_project_sections

router = APIRouter()


def get_todoist_token(db: Session) -> str:
    """Get Todoist API token from settings."""
    token = get_setting(db, "todoist_api_token")
    if not token:
        raise HTTPException(status_code=400, detail="Todoist API токен не настроен")
    return token


def get_todoist_config(db: Session) -> dict:
    """Get full Todoist configuration."""
    return {
        "api_token": get_setting(db, "todoist_api_token") or "",
        "project_id": get_setting(db, "todoist_project_id") or "",
        "section_today_id": get_setting(db, "todoist_section_today_id") or "",
        "section_not_today_id": get_setting(db, "todoist_section_not_today_id") or "",
        "enabled": get_setting(db, "todoist_enabled") == "true"
    }


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get Todoist configuration."""
    config = get_todoist_config(db)
    # Mask token for display
    if config["api_token"]:
        token = config["api_token"]
        config["api_token_masked"] = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
        config["api_token_set"] = True
    else:
        config["api_token_masked"] = ""
        config["api_token_set"] = False
    del config["api_token"]
    return config


class ConfigUpdate(BaseModel):
    api_token: Optional[str] = None
    project_id: Optional[str] = None
    section_today_id: Optional[str] = None
    section_not_today_id: Optional[str] = None
    enabled: Optional[bool] = None


@router.put("/config")
async def update_config(
    data: ConfigUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update Todoist configuration."""
    if data.api_token is not None:
        set_setting(db, "todoist_api_token", data.api_token)
    if data.project_id is not None:
        set_setting(db, "todoist_project_id", data.project_id)
    if data.section_today_id is not None:
        set_setting(db, "todoist_section_today_id", data.section_today_id)
    if data.section_not_today_id is not None:
        set_setting(db, "todoist_section_not_today_id", data.section_not_today_id)
    if data.enabled is not None:
        set_setting(db, "todoist_enabled", "true" if data.enabled else "false")
    
    return {"success": True}


@router.get("/test")
async def test_connection(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Test Todoist API connection."""
    token = get_todoist_token(db)
    client = TodoistClient(token)
    
    is_valid = await client.test_connection()
    if is_valid:
        return {"success": True, "message": "Подключение успешно"}
    else:
        raise HTTPException(status_code=400, detail="Не удалось подключиться к Todoist")


@router.get("/projects")
async def list_projects(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all Todoist projects."""
    token = get_todoist_token(db)
    client = TodoistClient(token)
    
    projects = await client.get_projects()
    return {"items": projects}


@router.get("/sections/{project_id}")
async def list_sections(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get sections for a project."""
    token = get_todoist_token(db)
    sections = await get_project_sections(token, project_id)
    return {"items": sections}


@router.get("/tasks")
async def list_tasks(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get Todoist tasks."""
    token = get_todoist_token(db)
    client = TodoistClient(token)
    tasks = await client.get_tasks(project_id)
    return {"items": tasks}


@router.post("/tasks/{task_id}/close")
async def close_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark task as complete."""
    token = get_todoist_token(db)
    client = TodoistClient(token)
    
    success = await client.close_task(task_id)
    if success:
        return {"success": True}
    else:
        raise HTTPException(status_code=400, detail="Не удалось завершить задачу")


@router.post("/sync")
async def sync_completed_tasks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Синхронизация с Todoist - помечает заказы как выполненные,
    если соответствующие задачи закрыты в Todoist.
    """
    from app.models import Order
    
    token = get_todoist_token(db)
    project_id = get_setting(db, "todoist_project_id")
    
    if not project_id:
        raise HTTPException(status_code=400, detail="Todoist проект не настроен")
    
    client = TodoistClient(token)
    
    # Получаем активные задачи из Todoist
    active_tasks = await client.get_tasks(project_id)
    active_task_ids = {t["id"] for t in active_tasks}
    
    # Находим заказы с todoist_task_id которые ещё pending
    orders_with_todoist = db.query(Order).filter(
        Order.todoist_task_id.isnot(None),
        Order.status == "pending"
    ).all()
    
    completed_count = 0
    for order in orders_with_todoist:
        # Если задачи нет в активных - значит она выполнена
        if order.todoist_task_id not in active_task_ids:
            order.status = "completed"
            order.completed_at = datetime.utcnow()
            completed_count += 1
    
    db.commit()
    
    return {
        "success": True,
        "completed_count": completed_count,
        "message": f"Синхронизировано: {completed_count} заказов помечены как выполненные"
    }


from datetime import datetime
