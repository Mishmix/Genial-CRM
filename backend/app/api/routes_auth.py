"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import TelegramAuthRequest, PasswordAuthRequest, AuthResponse
from app.auth.telegram_initdata import validate_telegram_init_data, is_admin_user
from app.auth.password_auth import verify_password
from app.crud import get_admins, get_admin_by_telegram_id, create_admin
from app.api.deps import (
    create_session, get_current_user, SESSION_COOKIE_NAME, SESSION_EXPIRY_DAYS
)
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/telegram", response_model=AuthResponse)
async def auth_telegram(
    data: TelegramAuthRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticate via Telegram Mini App initData.
    
    Validates initData and creates session if user is in admin allowlist.
    """
    is_valid, user_data, error = validate_telegram_init_data(data.init_data)
    
    if not is_valid:
        logger.warning(f"Invalid initData: {error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid initData",
        )
    
    user_id = user_data.get("id")
    username = user_data.get("username")
    
    # Check if user is admin
    admins = get_admins(db)
    if not is_admin_user(user_id, admins):
        logger.warning(f"Non-admin user attempted login: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not an admin.",
        )
    
    # Ensure admin exists in DB
    admin = get_admin_by_telegram_id(db, user_id)
    if not admin:
        admin = create_admin(db, user_id, username)
    
    # Create session
    session_id, expiry_days = create_session(
        db,
        auth_type="telegram",
        telegram_user_id=user_id,
        admin_id=admin.id,
        remember_me=True,  # Always remember for Telegram
    )
    
    # Set cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=expiry_days * 24 * 60 * 60,
    )
    
    logger.info(f"Telegram auth successful for user {user_id}")
    
    return AuthResponse(
        success=True,
        user_id=user_id,
        username=username,
    )


@router.post("/login", response_model=AuthResponse)
async def auth_password(
    data: PasswordAuthRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticate via password (for browser access).
    """
    if not verify_password(data.password):
        logger.warning("Failed password login attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )
    
    # Create session with remember_me option
    session_id, expiry_days = create_session(db, auth_type="password", remember_me=data.remember_me)
    
    # Set cookie - use secure=True and samesite=none for cross-domain (Railway)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=True,  # Required for cross-domain
        samesite="none",  # Required for cross-domain
        max_age=expiry_days * 24 * 60 * 60,
    )
    
    logger.info(f"Password auth successful (remember_me={data.remember_me})")
    
    return AuthResponse(success=True, message="Logged in")


@router.post("/logout")
async def logout(
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    """Log out current user."""
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"success": True}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return {
        "authenticated": True,
        "auth_type": current_user["auth_type"],
        "telegram_user_id": current_user.get("telegram_user_id"),
    }
