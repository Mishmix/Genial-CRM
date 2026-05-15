"""About bot — lightweight portfolio handler.

This bot only ever does one thing: when any message arrives, reply with a
localised "About me / portfolio" line and an inline button to the Mini App.

The previous version booted a full python-telegram-bot ``Application`` for
the second bot, which kept ~30–50 MB of handler/dispatcher/HTTP-pool state
in memory 24/7 just to perform a single Bot API call per inbound message.
This rewrite drops the Application and talks to api.telegram.org directly
via the httpx client we already import elsewhere.

Startup: register the webhook with Telegram (no Application created).
Per-update: parse `message.from.language_code`, build text + keyboard,
POST to /sendMessage. That's the whole bot.

Public surface preserved for `app.main`:
- ``init_about_bot()``  — async, called from lifespan.
- ``stop_about_bot()``  — async, no-op kept for symmetry.
- ``handle_about_update(update_dict)`` — async, called from the webhook
  endpoint (was previously ``_about_app.process_update``).
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Bot credentials and Mini App target. These were already inline in the
# previous version of this module — kept here unchanged so behaviour matches.
ABOUT_BOT_TOKEN = "8229237229:AAGxHzj81PKsFYRcB5ZwvvXXC8hxpsSgpQQ"
MINI_APP_URL = "https://t.me/genial_about_bot/launch"

_TELEGRAM_API = f"https://api.telegram.org/bot{ABOUT_BOT_TOKEN}"

# Message copy per language. Keys must mirror what `_pick_language` returns.
MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        "text": "Обо мне, кейсы, портфолио, отзывы 👇",
        "button": "Посмотреть",
    },
    "uk": {
        "text": "Про мене, кейси, портфоліо, відгуки 👇",
        "button": "Переглянути",
    },
    "es": {
        "text": "Sobre mí, casos, portafolio, reseñas 👇",
        "button": "Ver",
    },
    "en": {
        "text": "About me, cases, portfolio, reviews 👇",
        "button": "View",
    },
}


def _pick_language(lang_code: Optional[str]) -> str:
    """Match Telegram language_code (e.g. 'uk-UA') to our message bucket."""
    code = (lang_code or "en").lower()
    if code.startswith(("uk", "ua")):
        return "uk"
    if code.startswith("ru"):
        return "ru"
    if code.startswith("es"):
        return "es"
    return "en"


async def init_about_bot() -> None:
    """Set the Telegram webhook for the About bot.

    Idempotent — Telegram accepts repeated set_webhook calls with the same
    URL. We only do this in production (where ``RAILWAY_ENVIRONMENT_NAME``
    or ``PORT`` is set); locally we skip so that polling could be added later.
    """
    import os

    is_railway = bool(
        os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("PORT")
    )
    if not is_railway:
        logger.info("About bot: skipping webhook setup (non-Railway env)")
        return

    from app.config import get_settings

    config_settings = get_settings()
    base = (config_settings.webhook_url or "").rstrip("/")
    if not base:
        logger.warning("About bot: no webhook_url configured, skipping")
        return

    webhook_url = f"{base}/telegram/about-webhook"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_TELEGRAM_API}/setWebhook",
                json={"url": webhook_url, "drop_pending_updates": False},
            )
        if resp.status_code == 200 and resp.json().get("ok"):
            logger.info(f"About bot: webhook set at {webhook_url}")
        else:
            logger.warning(
                f"About bot: setWebhook returned {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        logger.error(f"About bot: setWebhook failed: {type(e).__name__}: {e}")


async def stop_about_bot() -> None:
    """No-op kept for symmetry with main.py's lifespan shutdown call."""
    return None


async def handle_about_update(update: dict[str, Any]) -> None:
    """Process one inbound Telegram update.

    Behaviour mirrors the previous version: any message (command or otherwise)
    triggers a single reply with the portfolio text + inline button. Messages
    without a `chat` are silently ignored (callbacks, edits, etc.).
    """
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return

    user = message.get("from") or {}
    lang = _pick_language(user.get("language_code"))
    copy = MESSAGES[lang]

    payload = {
        "chat_id": chat_id,
        "text": copy["text"],
        "reply_markup": {
            "inline_keyboard": [
                [{"text": copy["button"], "url": MINI_APP_URL}]
            ]
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_TELEGRAM_API}/sendMessage",
                json=payload,
            )
        if resp.status_code != 200:
            logger.warning(
                f"About bot sendMessage non-200 ({resp.status_code}) for chat={chat_id}: "
                f"{resp.text[:200]}"
            )
        else:
            logger.info(
                f"About bot: sent portfolio to user {user.get('id')} "
                f"({user.get('first_name','?')}), lang={lang}"
            )
    except Exception as e:
        logger.error(
            f"About bot sendMessage failed for chat={chat_id}: "
            f"{type(e).__name__}: {e}"
        )
