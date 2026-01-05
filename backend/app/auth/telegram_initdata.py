"""Telegram Mini App initData validation."""
import hashlib
import hmac
import json
import time
from typing import Optional, Tuple
from urllib.parse import parse_qs, unquote

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def validate_telegram_init_data(
    init_data: str,
    max_age_seconds: int = 86400,  # 24 hours
) -> Tuple[bool, Optional[dict], Optional[str]]:
    """
    Validate Telegram Mini App initData.
    
    Returns:
        Tuple of (is_valid, user_data, error_message)
    """
    settings = get_settings()
    bot_token = settings.telegram_bot_token
    
    if not bot_token:
        return False, None, "Bot token not configured"
    
    if not init_data:
        return False, None, "Empty initData"
    
    try:
        # Parse query string
        parsed = parse_qs(init_data, keep_blank_values=True)
        
        # Extract hash
        received_hash = parsed.get("hash", [None])[0]
        if not received_hash:
            return False, None, "Missing hash"
        
        # Check auth_date
        auth_date_str = parsed.get("auth_date", [None])[0]
        if not auth_date_str:
            return False, None, "Missing auth_date"
        
        auth_date = int(auth_date_str)
        current_time = int(time.time())
        
        if current_time - auth_date > max_age_seconds:
            return False, None, "initData expired"
        
        # Build data check string
        # Sort all params except hash and signature, join with \n
        check_pairs = []
        for key in sorted(parsed.keys()):
            if key not in ("hash", "signature"):
                value = parsed[key][0]
                check_pairs.append(f"{key}={value}")
        
        data_check_string = "\n".join(check_pairs)
        
        # Calculate HMAC
        # secret_key = HMAC_SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        # check = HMAC_SHA256(data_check_string, secret_key)
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Compare hashes
        if not hmac.compare_digest(calculated_hash, received_hash):
            return False, None, "Invalid hash"
        
        # Extract user data
        user_str = parsed.get("user", [None])[0]
        if not user_str:
            return False, None, "Missing user data"
        
        user_data = json.loads(unquote(user_str))
        
        # Check if user is in admin allowlist
        user_id = user_data.get("id")
        if user_id not in settings.admin_ids_list:
            # Also check database admins
            return True, user_data, None  # Valid but may not be admin
        
        return True, user_data, None
        
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error in initData: {e}")
        return False, None, "Invalid user JSON"
    except Exception as e:
        logger.warning(f"initData validation error: {type(e).__name__}")
        return False, None, "Validation error"


def is_admin_user(user_id: int, db_admins: list = None) -> bool:
    """Check if user ID is in admin allowlist."""
    settings = get_settings()
    
    # Check env config
    if user_id in settings.admin_ids_list:
        return True
    
    # Check database admins
    if db_admins:
        for admin in db_admins:
            if admin.telegram_user_id == user_id:
                return True
    
    return False
