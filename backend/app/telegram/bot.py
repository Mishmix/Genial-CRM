"""Telegram bot initialization and management."""
from typing import Optional
from telegram import Bot
from telegram.ext import Application, ApplicationBuilder

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_app_instance: Optional[Application] = None


def get_application() -> Optional[Application]:
    """Get the Telegram application instance."""
    global _app_instance
    
    if _app_instance is None:
        settings = get_settings()
        if settings.telegram_bot_token:
            _app_instance = (
                ApplicationBuilder()
                .token(settings.telegram_bot_token)
                .build()
            )
    
    return _app_instance


def get_bot() -> Optional[Bot]:
    """Get the Telegram bot instance from application."""
    app = get_application()
    if app:
        return app.bot
    return None


async def send_message(
    chat_id: int,
    text: str,
    business_connection_id: Optional[str] = None,
) -> Optional[int]:
    """
    Send a message via Telegram bot.
    
    Args:
        chat_id: Telegram chat/user ID
        text: Message text
        business_connection_id: Business connection ID for business messages
    
    Returns:
        Message ID if successful, None otherwise
    """
    bot = get_bot()
    if not bot:
        logger.error("Bot not initialized")
        return None
    
    try:
        kwargs = {"chat_id": chat_id, "text": text}
        
        if business_connection_id:
            kwargs["business_connection_id"] = business_connection_id
        
        logger.info(f"Sending message to {chat_id} with business_connection_id={business_connection_id}")
        message = await bot.send_message(**kwargs)
        logger.info(f"Message sent successfully, id={message.message_id}")
        return message.message_id
        
    except Exception as e:
        error_str = str(e)
        logger.error(f"Failed to send message: {type(e).__name__}: {e}")
        
        # If Business_peer_invalid, try without business_connection_id
        if business_connection_id and ("Business_peer_invalid" in error_str or "BUSINESS_PEER_INVALID" in error_str):
            logger.info("Retrying without business_connection_id...")
            try:
                message = await bot.send_message(chat_id=chat_id, text=text)
                logger.info(f"Retry successful, id={message.message_id}")
                return message.message_id
            except Exception as e2:
                logger.error(f"Retry also failed: {type(e2).__name__}: {e2}")
        
        return None


async def get_user_profile_photo_url(user_id: int) -> Optional[str]:
    """Get user's profile photo as base64 or file path."""
    bot = get_bot()
    if not bot:
        return None
    
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.photos and photos.photos[0]:
            # Get the smallest photo (first in array)
            photo = photos.photos[0][0]  # smallest size
            file = await bot.get_file(photo.file_id)
            return file.file_path  # URL to download
    except Exception as e:
        logger.warning(f"Failed to get profile photo for {user_id}: {type(e).__name__}: {e}")
    
    return None
