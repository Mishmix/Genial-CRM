"""CRUD operations for database models."""
import json
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models import Client, Message, Tag, Template, Setting, Admin, Reminder, Order, RejectionReason
from app.schemas import ClientCreate, ClientUpdate, TemplateCreate, TemplateUpdate, ReminderCreate, ReminderUpdate, OrderCreate, OrderUpdate
from app.search.normalize import normalize_text, generate_search_variants


# ============ Clients ============

def get_client_by_telegram_id(db: Session, telegram_user_id: int) -> Optional[Client]:
    """Get client by Telegram user ID."""
    return db.query(Client).filter(Client.telegram_user_id == telegram_user_id).first()


def get_client(db: Session, client_id: int) -> Optional[Client]:
    """Get client by ID with messages and tags."""
    return (
        db.query(Client)
        .options(joinedload(Client.tags), joinedload(Client.messages), joinedload(Client.reminders))
        .filter(Client.id == client_id)
        .first()
    )


def get_clients(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    has_unread: Optional[bool] = None,
    tag_ids: Optional[List[int]] = None,
    include_archived: bool = False,
) -> Tuple[List[Client], int]:
    """Get paginated list of clients with filters."""
    query = db.query(Client).options(joinedload(Client.tags))
    
    # By default, exclude archived
    if not include_archived:
        query = query.filter(Client.is_archived == False)
    
    if status:
        query = query.filter(Client.status == status)
    
    if has_unread is True:
        query = query.filter(Client.unread_count > 0)
    elif has_unread is False:
        query = query.filter(Client.unread_count == 0)
    
    if tag_ids:
        query = query.filter(Client.tags.any(Tag.id.in_(tag_ids)))
    
    total = query.count()
    
    clients = (
        query
        .order_by(Client.last_message_at.desc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return clients, total


def upsert_client(db: Session, data: ClientCreate) -> Client:
    """Create or update client from Telegram data."""
    client = get_client_by_telegram_id(db, data.telegram_user_id)
    
    if client:
        # Update existing
        client.username = data.username
        client.first_name = data.first_name
        client.last_name = data.last_name
        client.language_code = data.language_code
        if data.business_connection_id:
            client.business_connection_id = data.business_connection_id
        client.updated_at = datetime.utcnow()
    else:
        # Create new
        now = datetime.utcnow()
        client = Client(
            telegram_user_id=data.telegram_user_id,
            username=data.username,
            first_name=data.first_name,
            last_name=data.last_name,
            language_code=data.language_code,
            business_connection_id=data.business_connection_id,
            first_seen_at=now,
            created_at=now,
        )
        db.add(client)
    
    db.commit()
    db.refresh(client)
    return client


def update_client(db: Session, client_id: int, data: ClientUpdate) -> Optional[Client]:
    """Update client CRM fields."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return None
    
    if data.status is not None:
        client.status = data.status
    if data.notes is not None:
        client.notes = data.notes
    if data.tag_ids is not None:
        tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
        client.tags = tags
    if data.is_archived is not None:
        client.is_archived = data.is_archived
        client.archived_at = datetime.utcnow() if data.is_archived else None
    if data.lost_reason is not None:
        client.lost_reason = data.lost_reason
    if data.deadline is not None:
        client.deadline = data.deadline
    
    client.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(client)
    return client


def archive_client(db: Session, client_id: int) -> Optional[Client]:
    """Archive a client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        client.is_archived = True
        client.archived_at = datetime.utcnow()
        db.commit()
        db.refresh(client)
    return client


def unarchive_client(db: Session, client_id: int) -> Optional[Client]:
    """Unarchive a client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        client.is_archived = False
        client.archived_at = None
        db.commit()
        db.refresh(client)
    return client


def delete_client(db: Session, client_id: int) -> bool:
    """Permanently delete a client and all related data."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        db.delete(client)
        db.commit()
        return True
    return False


def merge_clients(db: Session, source_ids: List[int], target_id: int) -> Optional[Client]:
    """Merge multiple clients into one target client."""
    target = db.query(Client).filter(Client.id == target_id).first()
    if not target:
        return None
    
    sources = db.query(Client).filter(Client.id.in_(source_ids), Client.id != target_id).all()
    if not sources:
        return target
    
    # Track merged telegram IDs
    merged_ids = []
    if target.merged_from:
        try:
            merged_ids = json.loads(target.merged_from)
        except:
            merged_ids = []
    
    for source in sources:
        # Move messages to target
        db.query(Message).filter(Message.client_id == source.id).update(
            {"client_id": target_id}, synchronize_session=False
        )
        
        # Move reminders to target
        db.query(Reminder).filter(Reminder.client_id == source.id).update(
            {"client_id": target_id}, synchronize_session=False
        )
        
        # Merge tags
        for tag in source.tags:
            if tag not in target.tags:
                target.tags.append(tag)
        
        # Track merged ID
        merged_ids.append(source.telegram_user_id)
        
        # Delete source client
        db.delete(source)
    
    target.merged_from = json.dumps(merged_ids)
    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)
    return target


def create_manual_client(
    db: Session,
    first_name: str,
    source: str,
    last_name: Optional[str] = None,
    username: Optional[str] = None,
    phone: Optional[str] = None,
    notes: Optional[str] = None,
) -> Client:
    """Create a client manually (not from Telegram)."""
    import random
    
    # Generate a fake telegram_user_id for manual clients (negative to distinguish)
    fake_id = -random.randint(100000000, 999999999)
    
    now = datetime.utcnow()
    client = Client(
        telegram_user_id=fake_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        source=source,
        notes=notes,
        first_seen_at=now,
        created_at=now,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def mark_client_read(db: Session, client_id: int) -> Optional[Client]:
    """Mark all messages as read for client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        client.unread_count = 0
        db.commit()
        db.refresh(client)
    return client


def search_clients(db: Session, query: str, limit: int = 50) -> List[Client]:
    """Search clients with fuzzy matching."""
    normalized = normalize_text(query)
    variants = generate_search_variants(query)
    
    # Build search conditions
    conditions = []
    for variant in variants:
        conditions.append(Client.first_name.ilike(f"%{variant}%"))
        conditions.append(Client.last_name.ilike(f"%{variant}%"))
        conditions.append(Client.username.ilike(f"%{variant}%"))
    
    return (
        db.query(Client)
        .options(joinedload(Client.tags))
        .filter(or_(*conditions))
        .order_by(Client.last_message_at.desc().nullslast())
        .limit(limit)
        .all()
    )


# ============ Messages ============

def create_message(
    db: Session,
    client_id: int,
    direction: str,
    text: Optional[str],
    telegram_message_id: Optional[int] = None,
) -> Message:
    """Create a new message."""
    message = Message(
        client_id=client_id,
        direction=direction,
        text=text,
        telegram_message_id=telegram_message_id,
        sent_at=datetime.utcnow(),
    )
    db.add(message)
    
    # Update client
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        client.last_message_at = datetime.utcnow()
        if direction == "in":
            client.unread_count = (client.unread_count or 0) + 1
    
    db.commit()
    db.refresh(message)
    return message


def get_client_messages(
    db: Session, client_id: int, limit: int = 100
) -> List[Message]:
    """Get messages for a client."""
    return (
        db.query(Message)
        .filter(Message.client_id == client_id)
        .order_by(Message.sent_at.asc())
        .limit(limit)
        .all()
    )


# ============ Tags ============

def get_tags(db: Session) -> List[Tag]:
    """Get all tags."""
    return db.query(Tag).all()


def create_tag(db: Session, name: str, color: str = "#3b82f6") -> Tag:
    """Create a new tag."""
    tag = Tag(name=name, color=color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def get_or_create_tag(db: Session, name: str) -> Tag:
    """Get existing tag or create new one."""
    tag = db.query(Tag).filter(Tag.name == name).first()
    if not tag:
        tag = create_tag(db, name)
    return tag


# ============ Templates ============

def get_templates(
    db: Session, language: Optional[str] = None, is_auto_reply: Optional[bool] = None
) -> List[Template]:
    """Get templates with optional filters."""
    query = db.query(Template).filter(Template.is_active == True)
    
    if language:
        query = query.filter(Template.language == language)
    if is_auto_reply is not None:
        query = query.filter(Template.is_auto_reply == is_auto_reply)
    
    return query.all()


def get_auto_reply_template(db: Session, language: str) -> Optional[Template]:
    """Get active auto-reply template for language."""
    template = (
        db.query(Template)
        .filter(
            Template.is_active == True,
            Template.is_auto_reply == True,
            Template.language == language,
        )
        .first()
    )
    
    # Fallback to English
    if not template and language != "en":
        template = (
            db.query(Template)
            .filter(
                Template.is_active == True,
                Template.is_auto_reply == True,
                Template.language == "en",
            )
            .first()
        )
    
    return template


def create_template(db: Session, data: TemplateCreate) -> Template:
    """Create a new template."""
    template = Template(**data.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session, template_id: int, data: TemplateUpdate
) -> Optional[Template]:
    """Update a template."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        return None
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    
    db.commit()
    db.refresh(template)
    return template


# ============ Settings ============

def get_setting(db: Session, key: str) -> Optional[str]:
    """Get a setting value."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    return setting.value if setting else None


def set_setting(db: Session, key: str, value: str) -> Setting:
    """Set a setting value."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)
    
    db.commit()
    db.refresh(setting)
    return setting


def get_all_settings(db: Session) -> dict:
    """Get all settings as dict."""
    settings = db.query(Setting).all()
    return {s.key: s.value for s in settings}


# ============ Admins ============

def get_admin_by_telegram_id(db: Session, telegram_user_id: int) -> Optional[Admin]:
    """Get admin by Telegram user ID."""
    return db.query(Admin).filter(Admin.telegram_user_id == telegram_user_id).first()


def create_admin(
    db: Session, telegram_user_id: int, username: Optional[str] = None, role: str = "admin"
) -> Admin:
    """Create a new admin."""
    admin = Admin(telegram_user_id=telegram_user_id, username=username, role=role)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def get_admins(db: Session) -> List[Admin]:
    """Get all admins."""
    return db.query(Admin).all()


# ============ Reminders ============

def get_reminders(
    db: Session,
    client_id: Optional[int] = None,
    is_completed: Optional[bool] = None,
    due_before: Optional[datetime] = None,
) -> List[Reminder]:
    """Get reminders with optional filters."""
    query = db.query(Reminder)
    
    if client_id:
        query = query.filter(Reminder.client_id == client_id)
    if is_completed is not None:
        query = query.filter(Reminder.is_completed == is_completed)
    if due_before:
        query = query.filter(Reminder.remind_at <= due_before)
    
    return query.order_by(Reminder.remind_at.asc()).all()


def get_pending_reminders(db: Session) -> List[Reminder]:
    """Get all pending reminders that are due."""
    now = datetime.utcnow()
    return (
        db.query(Reminder)
        .filter(Reminder.is_completed == False, Reminder.remind_at <= now)
        .order_by(Reminder.remind_at.asc())
        .all()
    )


def create_reminder(db: Session, data: ReminderCreate) -> Reminder:
    """Create a new reminder."""
    reminder = Reminder(
        client_id=data.client_id,
        reminder_type=data.reminder_type,
        text=data.text,
        remind_at=data.remind_at,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def update_reminder(db: Session, reminder_id: int, data: ReminderUpdate) -> Optional[Reminder]:
    """Update a reminder."""
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        return None
    
    if data.text is not None:
        reminder.text = data.text
    if data.remind_at is not None:
        reminder.remind_at = data.remind_at
    if data.is_completed is not None:
        reminder.is_completed = data.is_completed
        if data.is_completed:
            reminder.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(reminder)
    return reminder


def complete_reminder(db: Session, reminder_id: int) -> Optional[Reminder]:
    """Mark a reminder as completed."""
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if reminder:
        reminder.is_completed = True
        reminder.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(reminder)
    return reminder


def delete_reminder(db: Session, reminder_id: int) -> bool:
    """Delete a reminder."""
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if reminder:
        db.delete(reminder)
        db.commit()
        return True
    return False


# ============ Orders ============

def get_orders(
    db: Session,
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = 100,
) -> List[Order]:
    """Get orders with optional filters."""
    query = db.query(Order)
    
    if client_id:
        query = query.filter(Order.client_id == client_id)
    if status:
        query = query.filter(Order.status == status)
    
    # По умолчанию не показываем удалённые
    if not include_deleted:
        query = query.filter(Order.status != "deleted")
    
    return query.order_by(Order.created_at.desc()).limit(limit).all()


def get_order(db: Session, order_id: int) -> Optional[Order]:
    """Get order by ID."""
    return db.query(Order).filter(Order.id == order_id).first()


def create_order(db: Session, data: OrderCreate) -> Order:
    """Create a new order."""
    from datetime import timedelta
    
    # Calculate deadline for flexible deadlines
    deadline_calculated = None
    if data.deadline_type == "exact" and data.deadline_date:
        deadline_calculated = data.deadline_date
    elif data.deadline_type == "flexible" and data.deadline_range:
        now = datetime.utcnow()
        if data.deadline_range == "today":
            deadline_calculated = now.replace(hour=23, minute=59, second=59)
        elif data.deadline_range == "tomorrow":
            deadline_calculated = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)
        elif data.deadline_range == "this_week":
            days_until_sunday = 6 - now.weekday()
            deadline_calculated = (now + timedelta(days=days_until_sunday)).replace(hour=23, minute=59, second=59)
        elif data.deadline_range == "next_week":
            days_until_next_sunday = 13 - now.weekday()
            deadline_calculated = (now + timedelta(days=days_until_next_sunday)).replace(hour=23, minute=59, second=59)
        elif data.deadline_range == "end_of_month":
            import calendar
            last_day = calendar.monthrange(now.year, now.month)[1]
            deadline_calculated = now.replace(day=last_day, hour=23, minute=59, second=59)
        elif data.deadline_range == "2_weeks":
            deadline_calculated = (now + timedelta(days=14)).replace(hour=23, minute=59, second=59)
        elif data.deadline_range == "no_rush":
            deadline_calculated = (now + timedelta(days=30)).replace(hour=23, minute=59, second=59)
    
    order = Order(
        client_id=data.client_id,
        service_type=data.service_type,
        quantity=data.quantity,
        amount=data.amount,
        currency=data.currency,
        has_ab_test=data.has_ab_test,
        has_title=data.has_title,
        has_rush=data.has_rush,
        deadline_type=data.deadline_type,
        deadline_date=data.deadline_date,
        deadline_range=data.deadline_range,
        deadline_custom=data.deadline_custom,
        deadline_calculated=deadline_calculated,
        notes=data.notes,
    )
    db.add(order)
    
    # Update client stats
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if client:
        # Auto-change status to "ordered" when first order is created
        if client.status in ("new", "sent_price"):
            client.status = "ordered"
    
    db.commit()
    db.refresh(order)
    return order


def update_order(db: Session, order_id: int, data: OrderUpdate) -> Optional[Order]:
    """Update an order."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(order, key, value)
    
    # Mark completed
    if data.status == "completed" and not order.completed_at:
        order.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    return order


def delete_order(db: Session, order_id: int) -> bool:
    """Soft delete an order (mark as deleted, don't count in stats)."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        order.status = "deleted"
        db.commit()
        return True
    return False


def get_client_orders_stats(db: Session, client_id: int) -> dict:
    """Get order statistics for a client (excluding deleted/cancelled)."""
    orders = db.query(Order).filter(
        Order.client_id == client_id,
        Order.status.notin_(["cancelled", "deleted"])  # Не считаем удалённые
    ).all()
    
    total_orders = len(orders)
    total_spent = sum(o.amount or 0 for o in orders if o.status == "completed")
    completed_orders = len([o for o in orders if o.status == "completed"])
    
    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "total_spent": total_spent,
    }


# ============ Rejection Reasons ============

def get_rejection_reasons(db: Session) -> List[RejectionReason]:
    """Get all rejection reasons."""
    return db.query(RejectionReason).order_by(RejectionReason.sort_order).all()


def seed_rejection_reasons(db: Session):
    """Seed default rejection reasons if not exist."""
    defaults = [
        ("expensive", "Дорого", "💰", 1),
        ("no_prepay", "Не хочет предоплату", "💳", 2),
        ("later", "Сказал позже - не написал", "⏰", 3),
        ("competitor", "Ушёл к другому", "🔄", 4),
        ("ghosted", "Пропал без причины", "❓", 5),
        ("wrong_niche", "Не моя ниша (ошибся)", "🚫", 6),
        ("other", "Другое", "📝", 7),
    ]
    
    for code, label, emoji, order in defaults:
        existing = db.query(RejectionReason).filter(RejectionReason.code == code).first()
        if not existing:
            reason = RejectionReason(code=code, label=label, emoji=emoji, sort_order=order)
            db.add(reason)
    
    db.commit()


def seed_default_tags(db: Session):
    """Seed default tags if not exist."""
    defaults = [
        ("Сложный", "#ef4444"),  # red
        ("Повторный", "#22c55e"),  # green
    ]
    
    for name, color in defaults:
        existing = db.query(Tag).filter(Tag.name == name).first()
        if not existing:
            tag = Tag(name=name, color=color)
            db.add(tag)
    
    db.commit()


# ============ AI Order Detection ============

def is_duplicate_order(
    db: Session,
    client_id: int,
    service_type: str,
    deadline_date: Optional[datetime],
    quantity: int
) -> bool:
    """
    Проверяет, есть ли похожий активный заказ.
    Дубликат = тот же клиент + тип + количество + дедлайн ± 2 дня.
    """
    from sqlalchemy import and_, func
    
    query = db.query(Order).filter(
        Order.client_id == client_id,
        Order.service_type == service_type,
        Order.quantity == quantity,
        Order.status.notin_(["completed", "cancelled", "refunded", "deleted"])
    )
    
    if deadline_date:
        # Проверяем дедлайн ± 2 дня
        from datetime import timedelta
        date_min = deadline_date - timedelta(days=2)
        date_max = deadline_date + timedelta(days=2)
        query = query.filter(
            Order.deadline_date.isnot(None),
            Order.deadline_date >= date_min,
            Order.deadline_date <= date_max
        )
    
    return query.first() is not None


def create_ai_order(
    db: Session,
    client_id: int,
    conversation_id: int,
    order_data: dict
) -> Optional[Order]:
    """
    Создаёт заказ от AI детектора.
    Проверяет дубликаты и обновляет связи.
    Также создаёт задачу в Todoist если настроено.
    """
    from datetime import datetime
    
    # Парсим дедлайн
    deadline_date = None
    if order_data.get("deadline_date"):
        try:
            deadline_date = datetime.strptime(order_data["deadline_date"], "%Y-%m-%d")
        except ValueError:
            pass
    
    # Проверка дубликата
    if is_duplicate_order(
        db,
        client_id,
        order_data.get("service_type", "thumbnail"),
        deadline_date,
        order_data.get("quantity", 1)
    ):
        return None
    
    # Создаём заказ
    order = Order(
        client_id=client_id,
        conversation_id=conversation_id,
        service_type=order_data.get("service_type", "thumbnail"),
        quantity=order_data.get("quantity", 1),
        amount=order_data.get("amount"),
        deadline_date=deadline_date,
        deadline_calculated=deadline_date,
        notes=order_data.get("notes", ""),
        source="ai",
        ai_confidence=order_data.get("confidence"),
        status="pending",
    )
    db.add(order)
    
    # Обновляем клиента
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        client.total_orders = (client.total_orders or 0) + 1
        if client.status in ("new", "sent_price"):
            client.status = "ordered"
    
    # Обновляем статус обращения
    from app.models import Conversation
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation and conversation.status == "new":
        conversation.status = "ordered"
    
    db.commit()
    db.refresh(order)
    
    # Todoist task will be created by the caller (async context)
    # Store settings for later use
    order._todoist_pending = True
    
    return order


def get_orders_board(db: Session) -> dict:
    """
    Получает заказы для доски Today/Not Today/Overdue.
    """
    from datetime import date
    from sqlalchemy.orm import joinedload
    
    today = date.today()
    
    # Базовый запрос - активные заказы с клиентами
    base_query = db.query(Order).options(
        joinedload(Order.client)
    ).filter(
        Order.status.notin_(["completed", "cancelled", "refunded", "deleted"])
    )
    
    # Просроченные (дедлайн до сегодня)
    overdue = base_query.filter(
        Order.deadline_date.isnot(None),
        func.date(Order.deadline_date) < today
    ).order_by(Order.deadline_date.asc()).all()
    
    # Сегодня
    today_orders = base_query.filter(
        Order.deadline_date.isnot(None),
        func.date(Order.deadline_date) == today
    ).order_by(Order.created_at.desc()).all()
    
    # Позже (дедлайн после сегодня или без дедлайна)
    later = base_query.filter(
        or_(
            Order.deadline_date.is_(None),
            func.date(Order.deadline_date) > today
        )
    ).order_by(
        Order.deadline_date.asc().nullslast(),
        Order.created_at.desc()
    ).all()
    
    # Выполненные (последние 50)
    completed = db.query(Order).options(
        joinedload(Order.client)
    ).filter(
        Order.status == "completed"
    ).order_by(Order.completed_at.desc().nullslast()).limit(50).all()
    
    return {
        "overdue": overdue,
        "today": today_orders,
        "later": later,
        "completed": completed
    }
