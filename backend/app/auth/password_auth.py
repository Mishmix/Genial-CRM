"""Password-based authentication for browser access."""
import bcrypt as bcrypt_lib

from app.config import get_settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt_lib.hashpw(password.encode(), bcrypt_lib.gensalt()).decode()


def verify_password(password: str, hashed: str = None) -> bool:
    """
    Verify password against stored hash.
    
    If no hash provided, uses the one from settings.
    """
    if hashed is None:
        settings = get_settings()
        hashed = settings.admin_password_hash
    
    if not hashed:
        return False
    
    try:
        return bcrypt_lib.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False
