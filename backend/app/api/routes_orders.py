"""Orders API routes."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.crud import (
    get_orders, get_order, create_order, update_order, delete_order,
    get_client_orders_stats, get_rejection_reasons, get_setting, get_client,
    get_orders_board,
)
from app.schemas import OrderCreate, OrderUpdate, OrderResponse, RejectionReasonResponse, OrderBoardResponse
from app.api.deps import get_current_user
from app.integrations.todoist import create_task_from_order
from app.utils.timezone import now_georgia

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/board")
async def get_board(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get orders board (Today/Not Today/Overdue). Auto-syncs with Todoist."""
    from app.integrations.todoist import TodoistClient
    from app.models import Order
    from datetime import datetime
    
    # Debug: log all orders
    all_orders = db.query(Order).all()
    logger.info(f"[BOARD DEBUG] Total orders in DB: {len(all_orders)}")
    for o in all_orders:
        logger.info(f"[BOARD DEBUG] Order {o.id}: status={o.status}, service={o.service_type}, deadline={o.deadline_date}")
    
    # Автоматическая синхронизация с Todoist
    try:
        api_token = get_setting(db, "todoist_api_token")
        project_id = get_setting(db, "todoist_project_id")
        
        if api_token and project_id:
            client = TodoistClient(api_token)
            active_tasks = await client.get_tasks(project_id)
            active_task_ids = {t["id"] for t in active_tasks}
            
            # Находим заказы с todoist_task_id которые ещё pending
            orders_with_todoist = db.query(Order).filter(
                Order.todoist_task_id.isnot(None),
                Order.status == "pending"
            ).all()
            
            for order in orders_with_todoist:
                # Если задачи нет в активных - значит она выполнена
                if order.todoist_task_id not in active_task_ids:
                    order.status = "completed"
                    order.completed_at = now_georgia()
                    logger.info(f"Auto-completed order {order.id} from Todoist sync")
            
            db.commit()
    except Exception as e:
        logger.error(f"Todoist auto-sync failed: {e}")
    
    data = get_orders_board(db)
    
    # Debug logging
    logger.info(f"[BOARD] overdue={len(data['overdue'])}, today={len(data['today'])}, later={len(data['later'])}, completed={len(data.get('completed', []))}")
    
    return {
        "overdue": [OrderBoardResponse.model_validate(o) for o in data["overdue"]],
        "today": [OrderBoardResponse.model_validate(o) for o in data["today"]],
        "later": [OrderBoardResponse.model_validate(o) for o in data["later"]],
        "completed": [OrderBoardResponse.model_validate(o) for o in data.get("completed", [])],
    }


@router.get("")
async def list_orders(
    client_id: Optional[int] = None,
    conversation_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get list of orders."""
    orders = get_orders(db, client_id=client_id, conversation_id=conversation_id, status=status, limit=limit)
    return {
        "items": [OrderResponse.model_validate(o) for o in orders],
        "total": len(orders),
    }


@router.post("")
async def create_new_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new order."""
    order = create_order(db, data)
    
    # Создаём задачу в Todoist если интеграция включена
    try:
        todoist_enabled = get_setting(db, "todoist_enabled") == "true"
        if todoist_enabled:
            api_token = get_setting(db, "todoist_api_token")
            project_id = get_setting(db, "todoist_project_id")
            section_today_id = get_setting(db, "todoist_section_today_id")
            section_not_today_id = get_setting(db, "todoist_section_not_today_id")
            
            if api_token and project_id and section_today_id and section_not_today_id:
                # Получаем имя клиента
                client = get_client(db, order.client_id)
                if client:
                    client_name = f"{client.first_name} {client.last_name or ''}".strip()
                    
                    await create_task_from_order(
                        api_token=api_token,
                        project_id=project_id,
                        section_today_id=section_today_id,
                        section_not_today_id=section_not_today_id,
                        client_name=client_name,
                        service_type=order.service_type,
                        quantity=order.quantity,
                        deadline=order.deadline_calculated or order.deadline_date
                    )
                    logger.info(f"Created Todoist task for order {order.id}")
    except Exception as e:
        logger.error(f"Failed to create Todoist task: {e}")
        # Не прерываем создание заказа если Todoist не сработал
    
    return OrderResponse.model_validate(order)


@router.get("/stats/{client_id}")
async def get_order_stats(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get order statistics for a client."""
    return get_client_orders_stats(db, client_id)


@router.get("/rejection-reasons")
async def list_rejection_reasons(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get list of rejection reasons."""
    reasons = get_rejection_reasons(db)
    return {
        "items": [RejectionReasonResponse.model_validate(r) for r in reasons],
    }


@router.get("/{order_id}")
async def get_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get order by ID."""
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.model_validate(order)


@router.put("/{order_id}")
async def update_existing_order(
    order_id: int,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update an order."""
    order = update_order(db, order_id, data)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.model_validate(order)


@router.patch("/{order_id}")
async def patch_order(
    order_id: int,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Partially update an order."""
    order = update_order(db, order_id, data)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.model_validate(order)


@router.delete("/{order_id}")
async def delete_existing_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete an order and its Todoist task."""
    from app.integrations.todoist import TodoistClient
    
    # Получаем заказ чтобы узнать todoist_task_id
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Удаляем задачу в Todoist если есть
    if order.todoist_task_id:
        try:
            api_token = get_setting(db, "todoist_api_token")
            if api_token:
                client = TodoistClient(api_token)
                await client.delete_task(order.todoist_task_id)
                logger.info(f"Deleted Todoist task {order.todoist_task_id} for order {order_id}")
        except Exception as e:
            logger.error(f"Failed to delete Todoist task: {e}")
    
    success = delete_order(db, order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"success": True}
