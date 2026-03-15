"""Telegram bot message handlers with thumbnail classification."""
import asyncio
from app.db import SessionLocal
import json
import sys
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import get_settings

from app.crud import (
    upsert_client, create_message, get_client_by_telegram_id,
    get_setting, get_auto_reply_template, create_ai_order,
)
from app.models import Conversation, Message
from app.schemas import ClientCreate
from app.telegram.bot import send_message
from app.telegram.avatars import get_or_fetch_avatar, get_avatar_url
from app.llm.llm_client import classify_thumbnail
from app.llm.order_detector import detect_order
from app.utils.logging import get_logger
from app.utils.language import detect_language_from_messages
from app.utils.timezone import now_georgia
from app.api.websocket import broadcast_update

logger = get_logger(__name__)

# Default inactivity threshold (used if not set in settings)
DEFAULT_INACTIVITY_DAYS = 180


# Store active business connections
_business_connections: dict = {}


def log_print(msg: str):
    """Print directly to stdout for debugging."""
    print(f"[HANDLER] {msg}", flush=True)
    logger.info(msg)


# Time threshold for creating new conversation (2 hours)
CONVERSATION_TIMEOUT_HOURS = 2


def get_or_create_conversation(db, client, business_connection_id: str = None):
    """Get active conversation or create new one for client.
    
    Rules:
    1. If there's an active conversation (status="new") - use it
    2. If last conversation exists and owner hasn't replied yet - use it
    3. If last message was less than 2 hours ago - use existing conversation
    4. Otherwise - create new conversation
    """
    from datetime import timedelta
    
    # Find the most recent conversation for this client (not deleted)
    last_conv = db.query(Conversation).filter(
        Conversation.client_id == client.id,
        Conversation.is_deleted == False,
    ).order_by(Conversation.created_at.desc()).first()
    
    if last_conv:
        # Rule 1: Active conversation - always use it
        if last_conv.status == "new":
            log_print(f"Found active conversation {last_conv.id} (status=new) for client {client.id}")
            return last_conv
        
        # Rule 2: Owner hasn't replied yet - use existing
        if not last_conv.owner_replied:
            log_print(f"Found conversation {last_conv.id} where owner hasn't replied yet for client {client.id}")
            return last_conv
        
        # Rule 3: Check time since last message
        now = now_georgia()
        last_msg = db.query(Message).filter(
            Message.client_id == client.id
        ).order_by(Message.sent_at.desc()).first()
        
        if last_msg and last_msg.sent_at:
            time_since_last = now - last_msg.sent_at
            if time_since_last < timedelta(hours=CONVERSATION_TIMEOUT_HOURS):
                log_print(f"Last message was {time_since_last} ago (< {CONVERSATION_TIMEOUT_HOURS}h), using conversation {last_conv.id}")
                # Reopen conversation if it was closed
                if last_conv.status in ("ordered", "rejected"):
                    last_conv.status = "new"
                    last_conv.owner_replied = False
                    db.commit()
                    log_print(f"Reopened conversation {last_conv.id}")
                return last_conv
    
    # Rule 4: Create new conversation
    new_conv = Conversation(
        client_id=client.id,
        business_connection_id=business_connection_id,
        source="telegram",
        status="new",
        started_at=now_georgia(),
    )
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)
    log_print(f"Created new conversation {new_conv.id} for client {client.id}")
    return new_conv


async def handle_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle business connection updates - when bot is connected/disconnected from business account."""
    conn = update.business_connection
    if not conn:
        return
    
    log_print(f"=== BUSINESS CONNECTION UPDATE ===")
    log_print(f"Connection ID: {conn.id}")
    log_print(f"User ID: {conn.user.id}")
    log_print(f"User chat ID: {conn.user_chat_id}")
    log_print(f"Can reply: {conn.can_reply}")
    log_print(f"Is enabled: {conn.is_enabled}")
    
    # Store connection info
    if conn.is_enabled and conn.can_reply:
        _business_connections[conn.id] = {
            "user_id": conn.user.id,
            "user_chat_id": conn.user_chat_id,
            "can_reply": conn.can_reply,
        }
        log_print(f"Stored business connection: {conn.id}")
    elif conn.id in _business_connections:
        del _business_connections[conn.id]
        log_print(f"Removed business connection: {conn.id}")


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming business message with thumbnail classification."""
    log_print("=== BUSINESS MESSAGE RECEIVED ===")
    
    message = update.business_message
    if not message:
        log_print("No business_message in update")
        return
    
    user = message.from_user
    if not user:
        log_print("No from_user in message")
        return
    
    # Skip non-text messages
    if not message.text:
        log_print(f"Skipping non-text message from user {user.id}")
        return
    
    log_print(f"Message text: {message.text[:100]}...")
    
    business_connection_id = message.business_connection_id
    settings = get_settings()
    
    log_print(f"Settings loaded - admin_ids: {settings.admin_telegram_ids}, groq_key: {'SET' if settings.groq_api_key else 'NOT SET'}")
    
    # Check if this is owner's message (outgoing)
    is_owner_message = False
    if settings.admin_telegram_ids:
        admin_ids = [int(x.strip()) for x in settings.admin_telegram_ids.split(",") if x.strip()]
        is_owner_message = user.id in admin_ids
        log_print(f"Admin IDs: {admin_ids}, user.id: {user.id}, is_owner: {is_owner_message}")
    
    log_print(f"Business message from user {user.id}, is_owner: {is_owner_message}")
    
    db = SessionLocal()
    try:
        # Upsert client
        # For owner's outgoing messages: the client is message.chat (the person being written to),
        # NOT message.from_user (which would be the owner themselves).
        if is_owner_message:
            chat = message.chat
            client_data = ClientCreate(
                telegram_user_id=chat.id,
                username=getattr(chat, 'username', None),
                first_name=getattr(chat, 'first_name', None) or "Unknown",
                last_name=getattr(chat, 'last_name', None),
                language_code=None,
                business_connection_id=business_connection_id,
            )
            log_print(f"Owner message: using chat as client (chat.id={chat.id}, name={getattr(chat, 'first_name', '')})")
        else:
            client_data = ClientCreate(
                telegram_user_id=user.id,
                username=user.username,
                first_name=user.first_name or "Unknown",
                last_name=user.last_name,
                language_code=user.language_code,
                business_connection_id=business_connection_id,
            )
        client = upsert_client(db, client_data)
        log_print(f"Client upserted: id={client.id}, first_seen_at={client.first_seen_at}, thumbnail_processed={client.thumbnail_processed}, owner_replied={client.owner_replied}")
        
        # Auto-unarchive if client was archived and sends a new message
        if client.is_archived and not is_owner_message:
            client.is_archived = False
            client.archived_at = None
            db.commit()
            log_print(f"Client {client.id} auto-unarchived due to new message")
        
        # Fetch avatar if not already cached
        # Use the client's telegram_user_id (not owner's user.id for outgoing messages)
        if not client.avatar_local_path:
            try:
                avatar_path = await get_or_fetch_avatar(client.telegram_user_id)
                if avatar_path:
                    client.avatar_local_path = get_avatar_url(client.telegram_user_id)
                    db.commit()
                    log_print(f"Avatar fetched for client {client.id}: {client.avatar_local_path}")
            except Exception as e:
                log_print(f"Failed to fetch avatar: {e}")
        
        # Get or create conversation for this client
        conversation = get_or_create_conversation(db, client, business_connection_id)
        
        # Save message with conversation_id
        new_msg = Message(
            client_id=client.id,
            conversation_id=conversation.id,
            direction="out" if is_owner_message else "in",
            text=message.text,
            message_type="text",
            telegram_message_id=message.message_id,
            sent_at=now_georgia(),
        )
        db.add(new_msg)
        
        # Update conversation unread count for incoming messages
        if not is_owner_message:
            conversation.unread_count = (conversation.unread_count or 0) + 1
            conversation.updated_at = now_georgia()
        
        db.commit()
        db.refresh(new_msg)
        
        # Broadcast new message to WebSocket clients
        try:
            await broadcast_update("new_message", {
                "client_id": client.id,
                "conversation_id": conversation.id,
                "message": {
                    "id": new_msg.id,
                    "client_id": client.id,
                    "conversation_id": conversation.id,
                    "direction": new_msg.direction,
                    "text": new_msg.text,
                    "sent_at": new_msg.sent_at.isoformat() if new_msg.sent_at else None,
                },
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
                    "sticky_note": client.sticky_note,
                    "total_orders": client.total_orders or 0,
                    "total_spent": client.total_spent or 0,
                    "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in client.tags] if client.tags else [],
                },
                "conversation": {
                    "id": conversation.id,
                    "status": conversation.status,
                    "category": conversation.category,
                    "unread_count": conversation.unread_count,
                    "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                    "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
                }
            })
            log_print(f"Broadcasted new_message for client {client.id}, conversation {conversation.id}")
        except Exception as e:
            log_print(f"Failed to broadcast: {e}")
        
        # If owner replied - mark conversation as read and stop analysis
        if is_owner_message:
            # Reset unread count - owner has seen the messages
            conversation.unread_count = 0
            client.unread_count = 0
            
            if not client.owner_replied:
                client.owner_replied = True
            
            db.commit()
            log_print(f"Owner replied to client {client.id}, marked as read, stopping analysis")
            
            # Broadcast read status update
            try:
                await broadcast_update("conversation_read", {
                    "conversation_id": conversation.id,
                    "client_id": client.id,
                })
            except Exception as e:
                log_print(f"Failed to broadcast read status: {e}")
            
            # AI Order Detection - анализируем после ответа владельца
            log_print(f"[AI_ORDER] Checking AI order detection...")
            log_print(f"[AI_ORDER] ai_order_detection_enabled = {settings.ai_order_detection_enabled}")
            log_print(f"[AI_ORDER] ai_analyze_after_owner_reply = {settings.ai_analyze_after_owner_reply}")
            
            if settings.ai_order_detection_enabled and settings.ai_analyze_after_owner_reply:
                # Capture IDs into local variables to avoid DetachedInstanceError
                target_client_id = client.id
                target_conversation_id = conversation.id
                
                log_print(f"[AI_ORDER] Spawning background task detect_and_create_order for conversation {target_conversation_id}")
                try:
                    import asyncio
                    
                    async def bg_detect():
                        bg_db = SessionLocal()
                        try:
                            # Use IDs instead of potentially detached model instances
                            order = await detect_and_create_order(bg_db, target_client_id, target_conversation_id)
                            log_print(f"[AI_ORDER] Background Result: {order}")
                        except Exception as e:
                            log_print(f"[AI_ORDER] Background ERROR: {type(e).__name__}: {e}")
                        finally:
                            bg_db.close()
                            
                    asyncio.create_task(bg_detect())
                except Exception as e:
                    log_print(f"[AI_ORDER] Failed to spawn background task: {type(e).__name__}: {e}")
                    import traceback
                    log_print(traceback.format_exc())
            else:
                log_print(f"[AI_ORDER] Skipped - detection disabled or not after owner reply")
            
            return
        
        # Client message - check if we should process
        client.last_client_message_at = now_georgia()
        
        # Skip if already processed (Mini App sent)
        if client.thumbnail_processed:
            log_print(f"Client {client.id} already processed, skipping auto-reply")
            db.commit()
            return
        
        # Skip if owner already replied
        if client.owner_replied:
            log_print(f"Owner already replied to client {client.id}, skipping auto-reply")
            db.commit()
            return

        # HARD GUARD: Skip if this client is definitely not new
        # (check total_orders or count of messages before this session)
        if (client.total_orders or 0) > 0:
            log_print(f"Client {client.id} has past orders ({client.total_orders}), skipping auto-reply")
            db.commit()
            return

        
        # Check if chat is eligible for processing
        # Auto-reply срабатывает если:
        # 1. Клиент НОВЫЙ (никогда не писал раньше до текущей сессии)
        # 2. ИЛИ клиент не писал 6+ месяцев (реактивация)
        # 
        # ВАЖНО: Проверяем только ПЕРВОЕ сообщение сессии, а не каждое!
        # Если клиент уже в процессе общения (buffer_messages не пустой), продолжаем обработку
        now = now_georgia()
        
        # Проверяем, есть ли уже буфер сообщений (клиент в процессе общения)
        has_active_buffer = client.buffer_messages and len(json.loads(client.buffer_messages)) > 0
        
        if not has_active_buffer:
            # Это первое сообщение сессии - проверяем eligibility
            # Ищем ЛЮБЫЕ сообщения ДО текущего (от клиента или дизайнера)
            last_msg = db.query(Message).filter(
                Message.client_id == client.id,
                Message.id != new_msg.id  # исключаем текущее сообщение
            ).order_by(Message.sent_at.desc()).first()
            
            is_new_client = last_msg is None
            is_reactivated = False
            
            inactivity_threshold = settings.auto_reply_inactivity_days
            
            if last_msg and last_msg.sent_at:
                days_since_last = (now - last_msg.sent_at).days
                is_reactivated = days_since_last >= inactivity_threshold
                log_print(f"Client {client.id}: last interaction {days_since_last} days ago, inactivity_threshold={inactivity_threshold}, reactivated={is_reactivated}")
            
            # Если клиент НЕ новый и НЕ реактивирован - пропускаем
            if not is_new_client and not is_reactivated:
                log_print(f"Client {client.id} is active (last interaction < {inactivity_threshold} days), skipping auto-reply")
                db.commit()
                return
            
            # If client was already processed but reactivated, reset for new processing
            if is_reactivated and client.thumbnail_processed:
                log_print(f"Client {client.id} reactivated after {inactivity_threshold}+ days, resetting")
                client.thumbnail_processed = False
                client.buffer_messages = None
                db.commit()
            
            log_print(f"Chat eligibility: is_new={is_new_client}, is_reactivated={is_reactivated}, thumbnail_processed={client.thumbnail_processed}")

        else:
            log_print(f"Client {client.id} has active buffer, continuing processing")
        
        # Add message to buffer
        buffer = []
        if client.buffer_messages:
            try:
                buffer = json.loads(client.buffer_messages)
            except json.JSONDecodeError:
                buffer = []
        
        buffer.append(message.text)
        client.buffer_messages = json.dumps(buffer, ensure_ascii=False)
        db.commit()
        
        log_print(f"Buffer for client {client.id}: {len(buffer)} messages: {buffer}")
        
        # Move EVERYTHING heavy (Classification, Auto-reply) to a background task
        # This makes the lead creation "instant" in the CRM
        target_client_id = client.id
        target_conversation_id = conversation.id
        target_connection_id = business_connection_id
        current_buffer = list(buffer) # Copy buffer
        
        async def bg_classify_and_reply():
            bg_db = SessionLocal()
            try:
                # Classify with LLM (blocks for seconds/minutes)
                log_print(f"[BG_AI] Calling classify_thumbnail with buffer: {current_buffer}")
                category = await classify_thumbnail(current_buffer)
                log_print(f"[BG_AI] Classification result: {category}")
                
                # Fetch fresh objects in bg_db
                from app.models import Client as ClientModel, Conversation as ConvModel
                bg_client = bg_db.query(ClientModel).filter(ClientModel.id == target_client_id).first()
                bg_conv = bg_db.query(ConvModel).filter(ConvModel.id == target_conversation_id).first()
                
                if not bg_client or not bg_conv:
                    return

                # Update conversation category for all types
                bg_conv.category = category
                bg_db.commit()

                if category == "thumbnail":
                    # Detect language from message buffer
                    detected_lang = detect_language_from_messages(current_buffer)
                    log_print(f"[BG_AI] Detected language from messages: {detected_lang}")
                    
                    # Send Mini App!
                    log_print(f"[BG_AI] Sending Mini App to client {target_client_id} (category: {category})")
                    await send_mini_app(
                        bg_db, bg_client, target_connection_id, detected_lang
                    )
                elif category in ("email_lead", "other"):
                    # Send category-specific auto-reply if template exists
                    detected_lang = detect_language_from_messages(current_buffer)
                    log_print(f"[BG_AI] Client {target_client_id} classified as '{category}', checking for auto-reply template")
                    
                    template = get_auto_reply_template(bg_db, detected_lang, category=category)
                    if template:
                        log_print(f"[BG_AI] Found auto-reply template '{template.name}' for category '{category}'")
                        await send_category_auto_reply(
                            bg_db, bg_client, target_connection_id, template, detected_lang
                        )
                    else:
                        log_print(f"[BG_AI] No auto-reply template for category '{category}', skipping")
                else:
                    log_print(f"[BG_AI] Client {target_client_id} classified as '{category}', no action")
            except Exception as e:
                log_print(f"[BG_AI] ERROR in classification task: {type(e).__name__}: {e}")
            finally:
                bg_db.close()

        # Fire and forget
        import asyncio
        asyncio.create_task(bg_classify_and_reply())
        
    except Exception as e:
        logger.error(f"Error handling business message: {type(e).__name__}: {e}")
    finally:
        db.close()

async def send_category_auto_reply(
    db,
    client,
    business_connection_id: Optional[str],
    template,
    detected_lang: str = "en",
):
    """Send text-only auto-reply based on category template (for email_lead, other)."""
    conn_id = business_connection_id or client.business_connection_id
    log_print(f"send_category_auto_reply: client_id={client.id}, category={template.category}, lang={detected_lang}")
    
    # Replace variables in template
    text = template.content
    text = text.replace("{first_name}", client.first_name or "")
    text = text.replace("{username}", client.username or "")
    
    from app.telegram.bot import get_bot
    bot = get_bot()
    
    if not bot:
        log_print("ERROR: Bot not initialized!")
        return
    
    try:
        chat_id = client.telegram_user_id
        
        # Send typing animation
        typing_kwargs = {"chat_id": chat_id, "action": "typing"}
        if conn_id:
            typing_kwargs["business_connection_id"] = conn_id
        
        await bot.send_chat_action(**typing_kwargs)
        await asyncio.sleep(2.5)
        
        # Build kwargs for message (text only, no Mini App button)
        kwargs = {"chat_id": chat_id, "text": text}
        if conn_id:
            kwargs["business_connection_id"] = conn_id
        
        sent_message = await bot.send_message(**kwargs)
        log_print(f"Category auto-reply sent successfully: {sent_message.message_id}")
        
        if sent_message:
            create_message(
                db,
                client_id=client.id,
                direction="out",
                text=text,
                telegram_message_id=sent_message.message_id,
            )
            
            # Mark as processed so we don't send again
            client.thumbnail_processed = True
            client.last_auto_reply_at = now_georgia()
            db.commit()
            
            logger.info(f"Sent category auto-reply ({template.category}) to client {client.id}")
            
    except Exception as e:
        log_print(f"ERROR sending category auto-reply: {type(e).__name__}: {e}")
        
        # Retry without business_connection_id
        if "Business_peer_invalid" in str(e) or "BUSINESS_PEER_INVALID" in str(e):
            log_print("Retrying without business_connection_id...")
            try:
                await bot.send_chat_action(chat_id=client.telegram_user_id, action="typing")
                await asyncio.sleep(2.5)
                
                sent_message = await bot.send_message(
                    chat_id=client.telegram_user_id,
                    text=text,
                )
                log_print(f"Retry successful: {sent_message.message_id}")
                
                create_message(
                    db,
                    client_id=client.id,
                    direction="out",
                    text=text,
                    telegram_message_id=sent_message.message_id,
                )
                
                client.thumbnail_processed = True
                client.last_auto_reply_at = now_georgia()
                client.business_connection_id = None
                db.commit()
                
                logger.info(f"Sent category auto-reply ({template.category}) to client {client.id} (without business connection)")
                return
            except Exception as e2:
                log_print(f"Retry also failed: {type(e2).__name__}: {e2}")


async def send_mini_app(
    db,
    client,
    business_connection_id: Optional[str],
    detected_lang: str = "en",
):
    """Send Mini App link to client who wants thumbnails."""
    settings = get_settings()
    
    # Use client's stored business_connection_id if available
    conn_id = business_connection_id or client.business_connection_id
    log_print(f"send_mini_app: client_id={client.id}, telegram_user_id={client.telegram_user_id}, business_connection_id={conn_id}")
    
    mini_app_url = settings.mini_app_url if hasattr(settings, 'mini_app_url') else None
    
    # Use detected language from message text (not Telegram language_code)
    template_lang = detected_lang
    
    log_print(f"Using detected language: {template_lang}")
    
    # Get auto-reply template for this language
    template = get_auto_reply_template(db, template_lang)
    
    # Button text based on language
    button_texts = {
        "ru": "🎨 Открыть портфолио",
        "ua": "🎨 Відкрити портфоліо",
        "en": "🎨 Open Portfolio",
        "es": "🎨 Abrir Portafolio",
    }
    button_text = button_texts.get(template_lang, button_texts["en"])
    
    if template:
        log_print(f"Using template: {template.name} (lang={template.language})")
        # Replace variables in template
        text = template.content
        text = text.replace("{first_name}", client.first_name or "")
        text = text.replace("{username}", client.username or "")
        text = text.replace("{portfolio_url}", mini_app_url or settings.portfolio_url or "")
    elif not mini_app_url:
        # Fallback message without Mini App (language-aware)
        if template_lang == "ru":
            text = f"Привет, {client.first_name}! 👋\n\nСпасибо за интерес к YouTube-обложкам! Я скоро отвечу вам с деталями. 🎨"
        elif template_lang == "ua":
            text = f"Привіт, {client.first_name}! 👋\n\nДякую за інтерес до YouTube-обкладинок! Я скоро відповім вам з деталями. 🎨"
        else:
            text = f"Hi, {client.first_name}! 👋\n\nThanks for your interest in YouTube thumbnails! I'll get back to you with details soon. 🎨"
    else:
        # Default message with Mini App (language-aware)
        if template_lang == "ru":
            text = f"Привет, {client.first_name}! 👋\n\nОтлично, что вас интересуют YouTube-обложки! 🎨\n\nНажмите кнопку ниже, чтобы посмотреть портфолио и оформить заказ:"
        elif template_lang == "ua":
            text = f"Привіт, {client.first_name}! 👋\n\nЧудово, що вас цікавлять YouTube-обкладинки! 🎨\n\nНатисніть кнопку нижче, щоб переглянути портфоліо та оформити замовлення:"
        else:
            text = f"Hi, {client.first_name}! 👋\n\nGreat that you're interested in YouTube thumbnails! 🎨\n\nClick the button below to view portfolio and place an order:"
    
    # Create inline keyboard with Mini App button
    keyboard = None
    if mini_app_url:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(button_text, url=mini_app_url)]
        ])
    
    # Send message
    from app.telegram.bot import get_bot
    bot = get_bot()
    
    if not bot:
        log_print("ERROR: Bot not initialized!")
        return
    
    try:
        # For Business API, we need to send to the user's chat_id with business_connection_id
        chat_id = client.telegram_user_id
        log_print(f"Sending typing animation to chat_id={chat_id} with business_connection_id={conn_id}")
        
        # Send typing animation
        typing_kwargs = {"chat_id": chat_id, "action": "typing"}
        if conn_id:
            typing_kwargs["business_connection_id"] = conn_id
        
        await bot.send_chat_action(**typing_kwargs)
        log_print("Typing animation sent, waiting 2.5 seconds...")
        
        # Wait 2.5 seconds while showing typing animation
        await asyncio.sleep(2.5)
        
        log_print(f"Calling bot.send_message to chat_id={chat_id} with business_connection_id={conn_id}")
        
        # Build kwargs for message
        kwargs = {
            "chat_id": chat_id,
            "text": text,
        }
        
        if keyboard:
            kwargs["reply_markup"] = keyboard
        
        # IMPORTANT: Only add business_connection_id if we have one
        if conn_id:
            kwargs["business_connection_id"] = conn_id
        
        sent_message = await bot.send_message(**kwargs)
        
        log_print(f"Message sent successfully: {sent_message.message_id}")
        
        if sent_message:
            # Save outbound message
            create_message(
                db,
                client_id=client.id,
                direction="out",
                text=text,
                telegram_message_id=sent_message.message_id,
            )
            
            # Mark as processed
            client.thumbnail_processed = True
            client.last_auto_reply_at = now_georgia()
            db.commit()
            
            logger.info(f"Sent Mini App to client {client.id}")
        
    except Exception as e:
        log_print(f"ERROR sending message: {type(e).__name__}: {e}")
        
        # If Business_peer_invalid, try without business_connection_id
        if "Business_peer_invalid" in str(e) or "BUSINESS_PEER_INVALID" in str(e):
            log_print("Retrying without business_connection_id...")
            try:
                # Send typing animation for retry too
                await bot.send_chat_action(chat_id=client.telegram_user_id, action="typing")
                await asyncio.sleep(2.5)
                
                sent_message = await bot.send_message(
                    chat_id=client.telegram_user_id,
                    text=text,
                    reply_markup=keyboard,
                )
                log_print(f"Retry successful: {sent_message.message_id}")
                
                # Save outbound message
                create_message(
                    db,
                    client_id=client.id,
                    direction="out",
                    text=text,
                    telegram_message_id=sent_message.message_id,
                )
                
                # Mark as processed
                client.thumbnail_processed = True
                client.last_auto_reply_at = now_georgia()
                
                # Clear invalid business_connection_id
                client.business_connection_id = None
                db.commit()
                
                logger.info(f"Sent Mini App to client {client.id} (without business connection)")
                return
            except Exception as e2:
                log_print(f"Retry also failed: {type(e2).__name__}: {e2}")
        
        logger.error(f"Failed to send Mini App to client {client.id}: {e}")


async def handle_edited_business_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle edited business message (just log)."""
    message = update.edited_business_message
    if message:
        logger.info(f"Edited business message from user {message.from_user.id}")


async def detect_and_create_order(db, client_id: int, conversation_id: int):
    """
    Анализирует переписку и создаёт/обновляет заказ если найден.
    Вызывается автоматически при получении сообщений.
    
    Логика:
    - AI детектирует заказ и возвращает is_confirmed (подтверждённый vs запрос)
    - Для НОВЫХ клиентов (без завершённых заказов) Todoist-задача создаётся ТОЛЬКО
      если заказ подтверждён (is_confirmed=true) И владелец ответил ≥2 раз в переписке
    - Для ПОСТОЯННЫХ клиентов (есть завершённые заказы) задача создаётся сразу
    - Если Todoist-задача уже существует, она ОБНОВЛЯЕТСЯ (не удаляется/пересоздаётся)
    """
    log_print(f"[DETECT_ORDER] Starting for client={client_id}, conversation={conversation_id}")

    # Получаем сообщения за последние 3 дня
    now = now_georgia()
    three_days_ago = now - timedelta(days=3)
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.sent_at >= three_days_ago
    ).order_by(Message.sent_at.asc()).all()

    log_print(f"[DETECT_ORDER] Found {len(messages)} messages in conversation")

    if len(messages) < 1:
        log_print(f"[DETECT_ORDER] No messages to analyze")
        return None

    # Не детектим заказы если нет ни одного входящего сообщения от клиента
    has_client_message = any(m.direction == "in" for m in messages)
    if not has_client_message:
        log_print(f"[DETECT_ORDER] No incoming client messages — skipping detection")
        return None

    # GUARD: Не анализируем переписку, если в ней уже есть завершённые заказы
    # (order completed/cancelled = работа сделана, не нужно пересоздавать)
    from app.models import Order as OrderModel
    completed_in_conv = db.query(OrderModel).filter(
        OrderModel.conversation_id == conversation_id,
        OrderModel.status.in_(["completed", "cancelled"]),
    ).count()
    if completed_in_conv > 0:
        log_print(f"[DETECT_ORDER] Conversation {conversation_id} already has {completed_in_conv} completed/cancelled orders — skipping AI detection")
        return None

    # Форматируем для детектора
    messages_data = [
        {
            "direction": m.direction,
            "text": m.text,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None
        }
        for m in messages
    ]

    log_print(f"[DETECT_ORDER] Messages data: {messages_data}")

    # Передаём существующие pending заказы как контекст для AI
    from app.crud import get_pending_ai_orders_for_conversation
    existing_orders = get_pending_ai_orders_for_conversation(db, conversation_id)
    log_print(f"[DETECT_ORDER] Existing pending AI orders: {len(existing_orders)}")

    # Детектим заказ
    log_print(f"[DETECT_ORDER] Calling detect_order()...")
    order_data = await detect_order(messages_data, existing_orders=existing_orders)

    log_print(f"[DETECT_ORDER] detect_order returned: {order_data}")

    if not order_data:
        log_print(f"[DETECT_ORDER] No order detected for conversation {conversation_id}")
        return None

    is_confirmed = order_data.get("is_confirmed", False)
    log_print(f"[DETECT_ORDER] AI detected order: {order_data}, is_confirmed={is_confirmed}")

    # Создаём или обновляем заказ в CRM (всегда — даже если не подтверждён)
    log_print(f"[DETECT_ORDER] Calling create_ai_order()...")
    order = create_ai_order(db, client_id, conversation_id, order_data)

    if order:
        was_updated = getattr(order, '_was_updated', False)
        log_print(f"[DETECT_ORDER] {'Updated' if was_updated else 'Created'} AI order {order.id} for client {client_id}")

        # === GUARD: Проверяем, нужно ли создавать Todoist-задачу ===
        from app.models import Client as ClientModel, Order as OrderModel
        client_obj = db.query(ClientModel).filter(ClientModel.id == client_id).first()
        
        # Считаем завершённые заказы клиента (признак постоянного клиента)
        completed_orders_count = db.query(OrderModel).filter(
            OrderModel.client_id == client_id,
            OrderModel.status == "completed"
        ).count()
        is_returning_client = completed_orders_count > 0
        
        # Считаем ответы владельца в этой переписке
        owner_replies_count = sum(1 for m in messages if m.direction == "out")
        
        log_print(f"[TODOIST_GUARD] is_returning_client={is_returning_client} (completed_orders={completed_orders_count}), "
                   f"owner_replies={owner_replies_count}, is_confirmed={is_confirmed}")
        
        # Для новых клиентов: задача в Todoist только если подтверждено И 2+ ответа владельца
        should_sync_todoist = True
        if not is_returning_client:
            if not is_confirmed:
                log_print(f"[TODOIST_GUARD] New client, order NOT confirmed by AI — skipping Todoist")
                should_sync_todoist = False
            elif owner_replies_count < 2:
                log_print(f"[TODOIST_GUARD] New client, owner replied only {owner_replies_count} time(s) — skipping Todoist")
                should_sync_todoist = False
            else:
                log_print(f"[TODOIST_GUARD] New client but order confirmed + {owner_replies_count} owner replies — creating Todoist task")
        else:
            log_print(f"[TODOIST_GUARD] Returning client — syncing Todoist task")

        # Sync Todoist task if configured and allowed
        if should_sync_todoist:
            try:
                from app.integrations.todoist import create_task_from_order, TodoistClient, SERVICE_NAMES
                from datetime import date

                todoist_token = get_setting(db, "todoist_api_token")
                todoist_project = get_setting(db, "todoist_project_id")
                todoist_today = get_setting(db, "todoist_section_today_id") or ""
                todoist_not_today = get_setting(db, "todoist_section_not_today_id") or ""
                todoist_enabled_flag = get_setting(db, "todoist_enabled")

                if todoist_token and todoist_project and todoist_enabled_flag != "false":
                    client_name = f"{client_obj.first_name} {client_obj.last_name or ''}".strip() if client_obj else "Клиент"

                    if was_updated and order.todoist_task_id:
                        # === UPDATE existing Todoist task (not delete+create) ===
                        old_quantity = getattr(order, '_old_quantity', None)
                        old_deadline = getattr(order, '_old_deadline', None)
                        values_changed = (
                            old_quantity != order.quantity or
                            old_deadline != order.deadline_date
                        )
                        if values_changed:
                            log_print(f"[TODOIST] Values changed (qty: {old_quantity}->{order.quantity}, "
                                       f"deadline: {old_deadline}->{order.deadline_date}), updating task")
                            tc = TodoistClient(todoist_token)
                            
                            # Build updated content
                            service_name = SERVICE_NAMES.get(order.service_type, order.service_type)
                            if order.quantity > 1:
                                content = f"{order.quantity} {service_name} {client_name}"
                            else:
                                content = f"{service_name} {client_name}"
                            
                            due_date = order.deadline_date.strftime("%Y-%m-%d") if order.deadline_date else None
                            
                            # Determine section
                            section_id = None
                            if todoist_today or todoist_not_today:
                                today_date = date.today()
                                if order.deadline_date and order.deadline_date.date() == today_date:
                                    section_id = todoist_today or todoist_not_today
                                else:
                                    section_id = todoist_not_today or todoist_today
                            
                            result = await tc.update_task(
                                task_id=order.todoist_task_id,
                                content=content,
                                due_date=due_date,
                                section_id=section_id,
                            )
                            if result:
                                log_print(f"[TODOIST] Task {order.todoist_task_id} updated for order {order.id}")
                            else:
                                log_print(f"[TODOIST] Failed to update task {order.todoist_task_id}")
                        else:
                            log_print(f"[TODOIST] Values unchanged, skipping update for order {order.id}")
                    else:
                        # === CREATE new Todoist task ===
                        log_print(f"[TODOIST] Creating task for order {order.id}...")
                        result = await create_task_from_order(
                            todoist_token, todoist_project, todoist_today, todoist_not_today,
                            client_name, order.service_type, order.quantity, order.deadline_date
                        )

                        if result and result.get("id"):
                            order.todoist_task_id = result["id"]
                            db.commit()
                            log_print(f"[TODOIST] Task {result['id']} created for order {order.id}")
                        else:
                            log_print(f"[TODOIST] Failed to create task: {result}")
            except Exception as e:
                log_print(f"[TODOIST] Error syncing task: {type(e).__name__}: {e}")

        # Broadcast order event
        try:
            await broadcast_update("new_order", {
                "order_id": order.id,
                "client_id": client_id,
                "conversation_id": conversation_id,
                "source": "ai",
                "service_type": order.service_type,
                "quantity": order.quantity,
                "updated": was_updated,
            })
        except Exception as e:
            log_print(f"[DETECT_ORDER] Failed to broadcast order event: {e}")

        return order
    else:
        log_print(f"[DETECT_ORDER] Order not created for conversation {conversation_id}")
        return None

