"""API dependencies for authentication and database."""
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Session as SessionModel, Admin
from app.crud import get_admin_by_telegram_id, get_admins
from app.auth.telegram_initdata import is_admin_user
from app.config import get_settings


SESSION_COOKIE_NAME = "crm_session"
SESSION_EXPIRY_DAYS = 7
SESSION_EXPIRY_DAYS_REMEMBER = 90  # 3 months when "remember me" is checked


def get_session_from_cookie(request: Request) -> Optional[str]:
    """Extract session ID from cookie."""
    return request.cookies.get(SESSION_COOKIE_NAME)


def create_session(
    db: Session,
    auth_type: str,
    telegram_user_id: Optional[int] = None,
    admin_id: Optional[int] = None,
    remember_me: bool = True,
) -> str:
    """Create a new session."""
    session_id = secrets.token_urlsafe(32)
    expiry_days = SESSION_EXPIRY_DAYS_REMEMBER if remember_me else SESSION_EXPIRY_DAYS
    expires_at = datetime.utcnow() + timedelta(days=expiry_days)
    
    session = SessionModel(
        session_id=session_id,
        auth_type=auth_type,
        telegram_user_id=telegram_user_id,
        admin_id=admin_id,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    
    return session_id, expiry_days


def get_valid_session(
    db: Session,
    session_id: str,
) -> Optional[SessionModel]:
    """Get valid (non-expired) session."""
    session = (
        db.query(SessionModel)
        .filter(SessionModel.session_id == session_id)
        .first()
    )
    
    if session and session.expires_at > datetime.utcnow():
        return session
    
    return None


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get current authenticated user.
    
    Raises HTTPException if not authenticated.
    """
    session_id = get_session_from_cookie(request)
    
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    session = get_valid_session(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    
    # Check if user is still admin
    if session.telegram_user_id:
        admins = get_admins(db)
        if not is_admin_user(session.telegram_user_id, admins):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
    
    return {
        "session_id": session.session_id,
        "auth_type": session.auth_type,
        "telegram_user_id": session.telegram_user_id,
        "admin_id": session.admin_id,
    }


async def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[dict]:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None
