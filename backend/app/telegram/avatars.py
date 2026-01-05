"""Avatar fetching and caching for Telegram users."""
import os
import asyncio
from pathlib import Path
from typing import Optional

from app.telegram.bot import get_bot
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Directory to store avatars
AVATARS_DIR = Path("avatars")
AVATARS_DIR.mkdir(exist_ok=True)


async def fetch_user_avatar(telegram_user_id: int) -> Optional[str]:
    """
    Fetch user's profile photo from Telegram and save locally.
    Returns the local file path or None if no avatar.
    
    Note: Telegram Business API has limitations - you can only get profile photos
    for users who have directly started a conversation with the bot (not via Business API).
    """
    bot = get_bot()
    if not bot:
        logger.warning("Bot not initialized, cannot fetch avatar")
        return None
    
    logger.info(f"Fetching avatar for user {telegram_user_id}")
    
    try:
        # Get user profile photos
        photos = await bot.get_user_profile_photos(user_id=telegram_user_id, limit=1)
        logger.info(f"Got photos response: total_count={photos.total_count if photos else 'None'}")
        
        if not photos or photos.total_count == 0:
            logger.info(f"No profile photo for user {telegram_user_id} (may be privacy settings or Business API limitation)")
            return None
        
        # Get the smallest photo (last in the list of sizes)
        photo_sizes = photos.photos[0]
        if not photo_sizes:
            logger.warning(f"No photo sizes for user {telegram_user_id}")
            return None
        
        logger.info(f"Photo sizes available: {len(photo_sizes)}")
        
        # Get smallest size for efficiency (usually 160x160)
        smallest_photo = photo_sizes[0]  # First is smallest
        
        # Download the file
        file = await bot.get_file(smallest_photo.file_id)
        logger.info(f"Got file: file_path={file.file_path}")
        
        if not file.file_path:
            logger.warning(f"No file path for avatar of user {telegram_user_id}")
            return None
        
        # Create local filename
        extension = file.file_path.split('.')[-1] if '.' in file.file_path else 'jpg'
        local_filename = f"{telegram_user_id}.{extension}"
        local_path = AVATARS_DIR / local_filename
        
        # Download to local file
        await file.download_to_drive(str(local_path))
        
        logger.info(f"Downloaded avatar for user {telegram_user_id} to {local_path}")
        return str(local_path)
        
    except Exception as e:
        error_msg = str(e)
        # Common errors:
        # - "User not found" - user hasn't interacted with bot directly
        # - "Bad Request: user not found" - same
        # - Privacy settings blocking access
        if "not found" in error_msg.lower() or "bad request" in error_msg.lower():
            logger.info(f"Cannot fetch avatar for user {telegram_user_id}: User hasn't directly interacted with bot (Business API limitation)")
        else:
            logger.error(f"Failed to fetch avatar for user {telegram_user_id}: {type(e).__name__}: {e}")
        return None


async def get_or_fetch_avatar(telegram_user_id: int, force_refresh: bool = False) -> Optional[str]:
    """
    Get avatar from cache or fetch from Telegram.
    Returns local file path or None.
    """
    # Check if we already have it cached
    for ext in ['jpg', 'jpeg', 'png']:
        cached_path = AVATARS_DIR / f"{telegram_user_id}.{ext}"
        if cached_path.exists() and not force_refresh:
            return str(cached_path)
    
    # Fetch from Telegram
    return await fetch_user_avatar(telegram_user_id)


def get_avatar_url(telegram_user_id: int) -> Optional[str]:
    """
    Get the URL path for serving the avatar.
    Returns None if avatar doesn't exist.
    """
    for ext in ['jpg', 'jpeg', 'png']:
        cached_path = AVATARS_DIR / f"{telegram_user_id}.{ext}"
        if cached_path.exists():
            return f"/avatars/{telegram_user_id}.{ext}"
    return None
