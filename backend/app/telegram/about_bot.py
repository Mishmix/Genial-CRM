"""
About Bot - простой бот для отправки ссылки на Mini App портфолио.
Работает параллельно с основным CRM ботом.
"""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Токен бота
ABOUT_BOT_TOKEN = "8229237229:AAGxHzj81PKsFYRcB5ZwvvXXC8hxpsSgpQQ"
MINI_APP_URL = "https://t.me/genial_about_bot/launch"

# Переводы
MESSAGES = {
    "ru": {
        "text": "Обо мне, кейсы, портфолио, отзывы 👇",
        "button": "Посмотреть"
    },
    "uk": {
        "text": "Про мене, кейси, портфоліо, відгуки 👇",
        "button": "Переглянути"
    },
    "es": {
        "text": "Sobre mí, casos, portafolio, reseñas 👇",
        "button": "Ver"
    },
    "en": {
        "text": "About me, cases, portfolio, reviews 👇",
        "button": "View"
    }
}

# Глобальная переменная для приложения
_about_app: Application = None


def get_language(user) -> str:
    """Определить язык пользователя."""
    lang_code = user.language_code or "en"
    
    # Украинский
    if lang_code.startswith("uk") or lang_code.startswith("ua"):
        return "uk"
    # Русский
    if lang_code.startswith("ru"):
        return "ru"
    # Испанский
    if lang_code.startswith("es"):
        return "es"
    # По умолчанию английский
    return "en"


async def send_portfolio_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить сообщение с кнопкой Mini App."""
    user = update.effective_user
    lang = get_language(user)
    
    messages = MESSAGES.get(lang, MESSAGES["en"])
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            messages["button"],
            url=MINI_APP_URL
        )]
    ])
    
    await update.message.reply_text(
        messages["text"],
        reply_markup=keyboard
    )
    
    logger.info(f"About bot: sent portfolio to user {user.id} ({user.first_name}), lang={lang}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    await send_portfolio_message(update, context)


async def any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик любого сообщения."""
    await send_portfolio_message(update, context)


async def init_about_bot():
    """Инициализация About бота."""
    global _about_app
    
    logger.info("Initializing About bot...")
    
    _about_app = Application.builder().token(ABOUT_BOT_TOKEN).build()
    
    # Добавляем обработчики
    _about_app.add_handler(CommandHandler("start", start_command))
    _about_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, any_message))
    
    import os
    is_railway = bool(os.environ.get('RAILWAY_ENVIRONMENT_NAME') or os.environ.get('PORT'))
    
    if not is_railway and not settings.is_production:
        # Инициализируем и запускаем polling только локально
        await _about_app.initialize()
        await _about_app.start()
        await _about_app.updater.start_polling(drop_pending_updates=True)
        logger.info("About bot started in polling mode")
    else:
        # В проде просто инициализируем (вебхуки настраиваются в main)
        await _about_app.initialize()
        from app.config import get_settings
        config_settings = get_settings()
        if config_settings.webhook_url:
            about_webhook = f"{config_settings.webhook_url.rstrip('/')}/telegram/about-webhook"
            await _about_app.bot.set_webhook(about_webhook)
            logger.info(f"About bot initialized for webhook mode at {about_webhook}")
        else:
            logger.warning("About bot initialized for webhook mode but no webhook_url configured.")
    
    logger.info("About bot started successfully!")


async def stop_about_bot():
    """Остановка About бота."""
    global _about_app
    
    if _about_app:
        logger.info("Stopping About bot...")
        await _about_app.updater.stop()
        await _about_app.stop()
        await _about_app.shutdown()
        _about_app = None
        logger.info("About bot stopped.")
