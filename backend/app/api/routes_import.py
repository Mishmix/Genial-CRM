"""Import API routes - Telegram Desktop JSON import."""
import json
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import Client, Message, Setting
from app.crud import get_setting, set_setting
from app.api.deps import get_current_user
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_admin_telegram_id(db: Session) -> int:
    """Get admin Telegram ID from settings or env."""
    # Сначала из базы
    admin_ids = get_setting(db, "admin_telegram_ids")
    # Потом из .env
    if not admin_ids:
        admin_ids = os.environ.get("ADMIN_TELEGRAM_IDS", "")
    # Потом из config
    if not admin_ids:
        from app.config import get_settings
        settings = get_settings()
        admin_ids = settings.admin_telegram_ids or ""
    
    if admin_ids:
        try:
            return int(admin_ids.split(",")[0].strip())
        except ValueError:
            pass
    return 0

# Глобальный статус импорта
import_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_chat": "",
    "imported_clients": 0,
    "imported_messages": 0,
    "skipped_messages": 0,
    "errors": [],
}


def reset_status():
    import_status.update({
        "running": False,
        "progress": 0,
        "total": 0,
        "current_chat": "",
        "imported_clients": 0,
        "imported_messages": 0,
        "skipped_messages": 0,
        "errors": [],
    })


def parse_telegram_date(date_str: str) -> Optional[datetime]:
    """Parse Telegram export date format."""
    try:
        # Format: "2024-01-15T14:30:45"
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except:
        try:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        except:
            return None


def extract_text_from_message(msg: dict) -> Optional[str]:
    """Extract text from Telegram message object."""
    text = msg.get("text", "")
    
    # Text can be string or array of text entities
    if isinstance(text, str):
        return text if text else None
    elif isinstance(text, list):
        # Array of text entities
        result = []
        for item in text:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(item.get("text", ""))
        return "".join(result) if result else None
    
    return None


def process_telegram_export(db: Session, data: dict, your_user_id: int):
    """Process Telegram Desktop JSON export."""
    global import_status
    
    # Импортируем только сообщения за последний год
    from datetime import timedelta
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    
    chats = data.get("chats", {}).get("list", [])
    if not chats:
        # Maybe it's a single chat export
        if "messages" in data:
            chats = [data]
    
    import_status["total"] = len(chats)
    
    for idx, chat in enumerate(chats):
        try:
            chat_type = chat.get("type", "")
            
            # Только личные чаты
            if chat_type not in ["personal_chat", "private_supergroup", "saved_messages", ""]:
                if chat_type in ["private_group", "public_group", "public_supergroup", "private_channel", "public_channel"]:
                    import_status["progress"] = idx + 1
                    continue
            
            # Пропускаем Saved Messages
            if chat.get("name") == "Saved Messages":
                import_status["progress"] = idx + 1
                continue
            
            chat_name = chat.get("name", "Unknown")
            import_status["current_chat"] = chat_name
            import_status["progress"] = idx + 1
            
            # Получаем ID пользователя из чата
            user_id = chat.get("id")
            if not user_id:
                continue
            
            # Пропускаем если это мы сами
            if user_id == your_user_id:
                continue
            
            messages = chat.get("messages", [])
            if not messages:
                continue
            
            # Ищем или создаём клиента
            client = db.query(Client).filter(Client.telegram_user_id == user_id).first()
            
            if not client:
                # Парсим имя
                name_parts = chat_name.split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else None
                
                # Находим самое раннее сообщение для first_seen_at
                earliest_date = None
                for msg in messages:
                    msg_date = parse_telegram_date(msg.get("date", ""))
                    if msg_date and (earliest_date is None or msg_date < earliest_date):
                        earliest_date = msg_date
                
                client = Client(
                    telegram_user_id=user_id,
                    first_name=first_name,
                    last_name=last_name,
                    status="new",
                    source="telegram-import",
                    first_seen_at=earliest_date or datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
                db.add(client)
                db.flush()
                import_status["imported_clients"] += 1
            else:
                # Обновляем first_seen_at если импортируемые сообщения старше
                for msg in messages:
                    msg_date = parse_telegram_date(msg.get("date", ""))
                    if msg_date and (client.first_seen_at is None or msg_date < client.first_seen_at):
                        client.first_seen_at = msg_date
            
            # Получаем существующие telegram_message_id для этого клиента
            existing_msg_ids = set(
                m[0] for m in db.query(Message.telegram_message_id)
                .filter(Message.client_id == client.id, Message.telegram_message_id.isnot(None))
                .all()
            )
            
            # Импортируем сообщения
            new_messages = []
            for msg in messages:
                msg_id = msg.get("id")
                
                # Пропускаем если уже есть
                if msg_id and msg_id in existing_msg_ids:
                    import_status["skipped_messages"] += 1
                    continue
                
                # Пропускаем служебные сообщения
                msg_type = msg.get("type", "message")
                if msg_type != "message":
                    continue
                
                text = extract_text_from_message(msg)
                if not text:
                    continue
                
                msg_date = parse_telegram_date(msg.get("date", ""))
                if not msg_date:
                    continue
                
                # Пропускаем сообщения старше 1 года
                if msg_date < one_year_ago:
                    continue
                
                # Определяем направление
                # from_id может быть: "user123456", число, или None
                from_id = msg.get("from_id")
                if from_id is None:
                    from_id = msg.get("actor_id")
                
                # Парсим from_id
                sender_id = None
                if isinstance(from_id, str):
                    if from_id.startswith("user"):
                        try:
                            sender_id = int(from_id[4:])
                        except ValueError:
                            pass
                    else:
                        try:
                            sender_id = int(from_id)
                        except ValueError:
                            pass
                elif isinstance(from_id, int):
                    sender_id = from_id
                
                # Если отправитель == владелец (ты), то это исходящее
                # Если отправитель == клиент (user_id чата), то это входящее
                if sender_id == your_user_id:
                    direction = "out"
                elif sender_id == user_id:  # user_id чата = клиент
                    direction = "in"
                else:
                    # Неизвестный отправитель - считаем входящим
                    direction = "in"
                
                new_messages.append(Message(
                    client_id=client.id,
                    direction=direction,
                    text=text[:10000],  # Ограничиваем длину
                    message_type="text",
                    telegram_message_id=msg_id,
                    sent_at=msg_date,
                ))
            
            # Batch insert
            if new_messages:
                db.bulk_save_objects(new_messages)
                import_status["imported_messages"] += len(new_messages)
            
            # Обновляем last_message_at клиента
            latest_msg = db.query(func.max(Message.sent_at)).filter(Message.client_id == client.id).scalar()
            if latest_msg:
                client.last_message_at = latest_msg
            
            # Коммитим каждые 10 чатов
            if (idx + 1) % 10 == 0:
                db.commit()
                
        except Exception as e:
            logger.error(f"Error processing chat {chat.get('name', 'unknown')}: {e}")
            import_status["errors"].append(f"{chat.get('name', 'unknown')}: {str(e)}")
            continue
    
    db.commit()
    import_status["running"] = False


@router.get("/status")
async def get_import_status(
    current_user: dict = Depends(get_current_user),
):
    """Get current import status."""
    return import_status


@router.post("/telegram")
async def import_telegram_export(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Import Telegram Desktop JSON export."""
    global import_status
    
    if import_status["running"]:
        raise HTTPException(status_code=400, detail="Импорт уже выполняется")
    
    # Получаем твой Telegram ID из настроек
    your_user_id = get_admin_telegram_id(db)
    
    if not your_user_id:
        raise HTTPException(status_code=400, detail="Укажите ваш Telegram ID в настройках")
    
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Неверный JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {e}")
    
    reset_status()
    import_status["running"] = True
    
    # Запускаем в фоне
    background_tasks.add_task(process_telegram_export, db, data, your_user_id)
    
    return {"success": True, "message": "Импорт запущен"}


@router.post("/telegram/sync")
async def import_telegram_sync(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Import Telegram Desktop JSON export (synchronous for small files)."""
    global import_status
    
    if import_status["running"]:
        raise HTTPException(status_code=400, detail="Импорт уже выполняется")
    
    your_user_id = get_admin_telegram_id(db)
    
    if not your_user_id:
        raise HTTPException(status_code=400, detail="Укажите ваш Telegram ID в настройках")
    
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Неверный JSON: {e}")
    
    reset_status()
    import_status["running"] = True
    
    try:
        process_telegram_export(db, data, your_user_id)
    except Exception as e:
        import_status["running"] = False
        raise HTTPException(status_code=500, detail=str(e))
    
    return {
        "success": True,
        "imported_clients": import_status["imported_clients"],
        "imported_messages": import_status["imported_messages"],
        "skipped_messages": import_status["skipped_messages"],
        "errors": import_status["errors"],
    }
