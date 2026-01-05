"""Application configuration from environment variables."""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # Telegram
    telegram_bot_token: str = ""
    
    # Groq LLM
    groq_api_key: str = ""
    
    # Application
    portfolio_url: str = "https://example.com/portfolio"
    auto_reply_enabled: bool = True
    mini_app_url: str = ""  # Mini App URL for thumbnail clients
    
    # AI Order Detection
    ai_order_detection_enabled: bool = True
    ai_order_confidence_threshold: float = 0.5  # Снижен с 0.7 для лучшего детекта
    ai_analyze_after_owner_reply: bool = True
    
    # Timezone (UTC offset in hours, e.g. 4 for Georgia/Tbilisi)
    timezone_offset: int = 4  # Georgia UTC+4
    
    # Admin access
    admin_telegram_ids: str = ""  # Comma-separated
    admin_password_hash: str = ""
    
    # CORS
    cors_origins: str = "http://localhost:5173,https://*.up.railway.app"
    
    # Database
    database_url: str = "sqlite:///./crm.db"
    
    # Session
    session_secret: str = "change_this_to_random_secret_key_min_32_chars"
    
    # Webhook
    webhook_url: str = ""
    webhook_path: str = "/telegram/webhook"
    
    # Environment
    env: str = "development"
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Parse admin IDs from comma-separated string."""
        if not self.admin_telegram_ids:
            return []
        return [int(x.strip()) for x in self.admin_telegram_ids.split(",") if x.strip()]
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.cors_origins:
            return []
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]
    
    @property
    def is_production(self) -> bool:
        return self.env == "production"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def clear_settings_cache():
    """Clear the settings cache to reload from .env file."""
    get_settings.cache_clear()
