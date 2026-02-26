"""Settings API routes."""
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.crud import get_all_settings, set_setting, get_admins, get_setting
from app.schemas import SettingUpdate, AdminResponse
from app.api.deps import get_current_user
from app.config import get_settings as get_app_settings

router = APIRouter()


@router.get("")
async def get_settings(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all settings including API keys (masked)."""
    db_settings = get_all_settings(db)
    app_settings = get_app_settings()
    
    # Mask API keys for display
    def mask_key(key: str) -> str:
        if not key or len(key) < 8:
            return ""
        return key[:4] + "..." + key[-4:]
    
    # Get API keys from DB (with fallback to env vars for migration)
    telegram_token = db_settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    llm_provider = db_settings.get("llm_provider") or os.environ.get("LLM_PROVIDER", "groq")
    groq_key = db_settings.get("groq_api_key") or os.environ.get("GROQ_API_KEY", "")
    nim_key = db_settings.get("nim_api_key") or os.environ.get("NIM_API_KEY", "")
    mini_app_url = db_settings.get("mini_app_url") or os.environ.get("MINI_APP_URL", "")
    admin_ids = db_settings.get("admin_telegram_ids") or os.environ.get("ADMIN_TELEGRAM_IDS", "")
    
    return {
        "portfolio_url": db_settings.get("portfolio_url", app_settings.portfolio_url),
        "auto_reply_enabled": db_settings.get("auto_reply_enabled", "true") == "true",
        "social_proof": db_settings.get("social_proof", ""),
        # API Keys (masked)
        "telegram_bot_token": mask_key(telegram_token),
        "telegram_bot_token_set": bool(telegram_token),
        "llm_provider": llm_provider,
        "groq_api_key": mask_key(groq_key),
        "groq_api_key_set": bool(groq_key),
        "nim_api_key": mask_key(nim_key),
        "nim_api_key_set": bool(nim_key),
        "mini_app_url": mini_app_url,
        "admin_telegram_ids": admin_ids,
        # Prompts from DB
        "prompt_thumbnail_classification": db_settings.get("prompt_thumbnail_classification", ""),
        "prompt_auto_reply": db_settings.get("prompt_auto_reply", ""),
    }


@router.put("")
async def update_setting(
    data: SettingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a setting in database."""
    try:
        # All settings now go to DB
        set_setting(db, data.key, data.value)
        
        # For API keys, also update environment variable for current process
        env_mapping = {
            "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
            "llm_provider": "LLM_PROVIDER",
            "groq_api_key": "GROQ_API_KEY",
            "nim_api_key": "NIM_API_KEY",
            "mini_app_url": "MINI_APP_URL",
            "admin_telegram_ids": "ADMIN_TELEGRAM_IDS",
        }
        
        if data.key in env_mapping:
            os.environ[env_mapping[data.key]] = data.value
            # Clear settings cache to reload
            from app.config import get_settings
            get_settings.cache_clear()
        
        return {"success": True, "key": data.key, "requires_restart": data.key == "telegram_bot_token"}
    except Exception as e:
        import logging
        logging.error(f"Failed to save setting {data.key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@router.post("/restart-bot")
async def restart_bot(
    current_user: dict = Depends(get_current_user),
):
    """Restart the Telegram bot with new token."""
    try:
        from app.telegram.bot import restart_bot as do_restart
        await do_restart()
        return {"success": True, "message": "Bot restarted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admins")
async def list_admins(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get list of admin users."""
    admins = get_admins(db)
    return {
        "items": [AdminResponse.model_validate(a) for a in admins],
    }


@router.get("/bot-status")
async def get_bot_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get Telegram bot connection status."""
    db_settings = get_all_settings(db)
    
    # Get from DB with fallback to env vars
    token = db_settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    llm_provider = db_settings.get("llm_provider") or os.environ.get("LLM_PROVIDER", "groq")
    groq_key = db_settings.get("groq_api_key") or os.environ.get("GROQ_API_KEY", "")
    nim_key = db_settings.get("nim_api_key") or os.environ.get("NIM_API_KEY", "")
    mini_app = db_settings.get("mini_app_url") or os.environ.get("MINI_APP_URL", "")
    admin_ids = db_settings.get("admin_telegram_ids") or os.environ.get("ADMIN_TELEGRAM_IDS", "")
    
    return {
        "bot_configured": bool(token),
        "llm_configured": bool(groq_key) if llm_provider == "groq" else bool(nim_key),
        "groq_configured": bool(groq_key),
        "mini_app_configured": bool(mini_app),
        "admin_configured": bool(admin_ids),
    }


@router.get("/timezone")
async def get_timezone():
    """Get timezone offset for frontend."""
    app_settings = get_app_settings()
    return {
        "offset": app_settings.timezone_offset,
        "name": "Asia/Tbilisi"  # Georgia
    }
