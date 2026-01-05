"""Main FastAPI application."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from datetime import datetime, time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, filters, TypeHandler,
)

# BusinessConnectionHandler may not be available in older versions
try:
    from telegram.ext import BusinessConnectionHandler
    HAS_BUSINESS_CONNECTION = True
except ImportError:
    HAS_BUSINESS_CONNECTION = False
    BusinessConnectionHandler = None

from app.config import get_settings
from app.db import init_db, SessionLocal
from app.api import api_router
from app.api.websocket import router as ws_router
from app.telegram.handlers import handle_business_message, handle_edited_business_message, handle_business_connection
from app.telegram.bot import get_application
from app.utils.logging import setup_logging, get_logger
from app.seed import seed_database
from app.backup import run_scheduled_backup

logger = get_logger(__name__)
settings = get_settings()

# Telegram application instance
telegram_app: Optional[Application] = None

# Backup scheduler task
backup_task: Optional[asyncio.Task] = None

# Avatars directory
AVATARS_DIR = Path("avatars")
AVATARS_DIR.mkdir(exist_ok=True)


async def backup_scheduler():
    """Background task to run scheduled backups at midnight."""
    while True:
        try:
            now = datetime.now()
            # Calculate seconds until next midnight
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now.hour >= 0:
                tomorrow = tomorrow.replace(day=now.day + 1)
            seconds_until_midnight = (tomorrow - now).total_seconds()
            
            logger.info(f"Backup scheduler: next backup in {seconds_until_midnight/3600:.1f} hours")
            await asyncio.sleep(seconds_until_midnight)
            
            # Run backup
            logger.info("Running scheduled backup...")
            run_scheduled_backup()
            
            # Sleep a bit to avoid running twice
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Backup scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Backup scheduler error: {e}")
            await asyncio.sleep(3600)  # Retry in 1 hour


async def log_all_updates(update: Update, context):
    """Log all incoming updates for debugging."""
    print(f"[DEBUG] Received update type: {update.effective_message}", flush=True)
    print(f"[DEBUG] Update: {update.to_dict()}", flush=True)
    logger.info(f"Received update: {update.to_dict()}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global telegram_app, backup_task
    
    setup_logging()
    logger.info("Starting CRM Bot...")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Seed database with defaults
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    
    # Initialize Telegram bot
    if settings.telegram_bot_token:
        telegram_app = get_application()
        
        if telegram_app:
            # Add debug handler for all updates (lowest priority)
            telegram_app.add_handler(
                TypeHandler(Update, log_all_updates),
                group=-1  # Run before other handlers
            )
            
            # Add handlers for business messages
            telegram_app.add_handler(
                MessageHandler(
                    filters.UpdateType.BUSINESS_MESSAGE,
                    handle_business_message,
                )
            )
            telegram_app.add_handler(
                MessageHandler(
                    filters.UpdateType.EDITED_BUSINESS_MESSAGE,
                    handle_edited_business_message,
                )
            )
            
            # Add handler for business connection updates (if available)
            if HAS_BUSINESS_CONNECTION and BusinessConnectionHandler:
                telegram_app.add_handler(
                    BusinessConnectionHandler(handle_business_connection)
                )
            
            await telegram_app.initialize()
            
            # Start polling in development mode
            if not settings.is_production and not settings.webhook_url:
                await telegram_app.start()
                asyncio.create_task(telegram_app.updater.start_polling(
                    allowed_updates=Update.ALL_TYPES  # Explicitly request all update types
                ))
                logger.info("Telegram bot started (polling mode)")
            else:
                logger.info("Telegram bot initialized (webhook mode)")
    else:
        logger.warning("Telegram bot token not configured")
    
    # Start backup scheduler
    backup_task = asyncio.create_task(backup_scheduler())
    logger.info("Backup scheduler started")
    
    yield
    
    # Shutdown
    if backup_task:
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            pass
    
    if telegram_app:
        if telegram_app.updater and telegram_app.updater.running:
            await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
    
    logger.info("CRM Bot stopped")


# Create FastAPI app
app = FastAPI(
    title="CRM Bot API",
    description="Telegram Business CRM with auto-replies",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

# Serve avatars as static files
app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR)), name="avatars")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "crm-bot"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Telegram webhook endpoint for production."""
    global telegram_app
    
    if not telegram_app:
        return JSONResponse(
            status_code=500,
            content={"error": "Bot not initialized"},
        )
    
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {type(e).__name__}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Processing failed"},
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled error: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
