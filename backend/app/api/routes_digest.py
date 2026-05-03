"""AI-Manager digest API: data extraction, save, deliver, prompts CRUD.

All `/digest/*` endpoints are auth'd via `X-Routine-Token` header (Setting key
`routine_api_token`, auto-generated on first lookup). Prompt CRUD uses the
existing admin session.
"""
import html
import os
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import get_setting, set_setting
from app.db import get_db
from app.models import Client, Conversation, Digest, Message, Setting
from app.telegram.bot import get_bot
from app.utils.logging import get_logger
from app.utils.timezone import now_georgia

logger = get_logger(__name__)
router = APIRouter()


# ---------- Routine token auth ----------

ROUTINE_TOKEN_KEY = "routine_api_token"


def _ensure_routine_token(db: Session) -> str:
    token = get_setting(db, ROUTINE_TOKEN_KEY)
    if not token:
        token = "gnr_" + secrets.token_urlsafe(32)
        set_setting(db, ROUTINE_TOKEN_KEY, token)
        logger.info("Generated new routine_api_token")
    return token


def require_routine_token(
    x_routine_token: Optional[str] = Header(default=None, alias="X-Routine-Token"),
    db: Session = Depends(get_db),
):
    expected = _ensure_routine_token(db)
    if not x_routine_token or not secrets.compare_digest(x_routine_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid routine token")


# ---------- Prompts CRUD (admin) ----------

ALLOWED_PROMPT_KEYS = {"prompt_morning_digest", "prompt_evening_strategist", "prompt_todoist_sync"}


class PromptUpdate(BaseModel):
    content: str


def _prompt_payload(db: Session, key: str) -> dict:
    return {
        "key": key,
        "content": get_setting(db, key) or "",
        "previous": get_setting(db, f"{key}__previous"),
    }


@router.get("/prompts")
async def list_prompts(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return [_prompt_payload(db, k) for k in sorted(ALLOWED_PROMPT_KEYS)]


@router.get("/prompts/{key}")
async def get_prompt(
    key: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if key not in ALLOWED_PROMPT_KEYS:
        raise HTTPException(status_code=404, detail="Unknown prompt key")
    return _prompt_payload(db, key)


@router.put("/prompts/{key}")
async def update_prompt(
    key: str,
    payload: PromptUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if key not in ALLOWED_PROMPT_KEYS:
        raise HTTPException(status_code=404, detail="Unknown prompt key")
    current = get_setting(db, key)
    if current is not None and current != payload.content:
        # One-step undo: previous value parked in `{key}__previous`.
        set_setting(db, f"{key}__previous", current)
    set_setting(db, key, payload.content)
    return _prompt_payload(db, key)


@router.post("/prompts/{key}/undo")
async def undo_prompt(
    key: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if key not in ALLOWED_PROMPT_KEYS:
        raise HTTPException(status_code=404, detail="Unknown prompt key")
    previous = get_setting(db, f"{key}__previous")
    if previous is None:
        raise HTTPException(status_code=404, detail="No previous version to restore")
    current = get_setting(db, key) or ""
    # Swap: current becomes the new "previous" so the user can flip back.
    set_setting(db, f"{key}__previous", current)
    set_setting(db, key, previous)
    return _prompt_payload(db, key)


# Routine version of prompt fetch — no admin session, only routine token.
@router.get("/routine/prompt/{key}", dependencies=[Depends(require_routine_token)])
async def routine_get_prompt(key: str, db: Session = Depends(get_db)):
    if key not in ALLOWED_PROMPT_KEYS:
        raise HTTPException(status_code=404, detail="Unknown prompt key")
    return {"key": key, "content": get_setting(db, key) or ""}


# ---------- Digest data extraction (routine) ----------

def _build_deep_link(client: Client) -> Optional[str]:
    if client.telegram_user_id and client.telegram_user_id > 0:
        return f"tg://user?id={client.telegram_user_id}"
    if client.username:
        return f"https://t.me/{client.username}"
    return None


def _serialize_message(msg: Message) -> dict:
    if msg.message_type == "voice":
        content = msg.transcription or msg.text or ""
    else:
        content = msg.text or ""
    return {
        "id": msg.id,
        "direction": msg.direction,
        "type": msg.message_type or "text",
        "content": content,
        "transcription_status": msg.transcription_status,
        "created_at": msg.sent_at.isoformat() if msg.sent_at else None,
    }


@router.get("/digest/data", dependencies=[Depends(require_routine_token)])
async def digest_data(
    type: str = Query(..., pattern="^(morning|evening)$"),
    db: Session = Depends(get_db),
):
    if type == "morning":
        window_hours = 24
        max_chats = 15
        msgs_per_chat = 35
    else:
        window_hours = 48
        max_chats = 9999
        msgs_per_chat = 50

    now = now_georgia()
    period_start = now - timedelta(hours=window_hours)

    clients = (
        db.query(Client)
        .filter(Client.last_client_message_at.isnot(None))
        .filter(Client.last_client_message_at >= period_start)
        .filter(Client.is_archived == False)  # noqa: E712
        .order_by(desc(Client.last_client_message_at))
        .limit(max_chats)
        .all()
    )

    chats = []
    for client in clients:
        msgs = (
            db.query(Message)
            .filter(Message.client_id == client.id)
            .order_by(desc(Message.sent_at))
            .limit(msgs_per_chat)
            .all()
        )
        msgs.reverse()  # chronological
        chats.append({
            "client_id": client.id,
            "client_name": " ".join(filter(None, [client.first_name, client.last_name])).strip() or "Unknown",
            "telegram_user_id": client.telegram_user_id if client.telegram_user_id and client.telegram_user_id > 0 else None,
            "telegram_username": client.username,
            "client_status": client.status,
            "client_notes": client.notes,
            "tags": [t.name for t in (client.tags or [])],
            "deep_link": _build_deep_link(client),
            "last_client_message_at": client.last_client_message_at.isoformat() if client.last_client_message_at else None,
            "messages": [_serialize_message(m) for m in msgs],
        })

    response = {
        "type": type,
        "now": now.isoformat(),
        "now_human": _format_now_ru(now),
        "timezone": "Asia/Tbilisi (UTC+4)",
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
        "chats": chats,
    }
    if type == "morning":
        response["todoist"] = await _morning_todoist_block(db, now)
    return response


async def _morning_todoist_block(db: Session, now: datetime) -> Optional[dict]:
    """Today's plan + yesterday's wins from Todoist. Returns None on any error
    so the morning digest never fails because Todoist is down/misconfigured."""
    try:
        from app.integrations.todoist import list_active_tasks, list_completed_tasks
        api_token = get_setting(db, "todoist_api_token")
        project_id = get_setting(db, "todoist_project_id")
        if not api_token or not project_id:
            return None
        today = now.date().isoformat()
        yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        active = await list_active_tasks(api_token, project_id)
        completed = await list_completed_tasks(api_token, project_id, yesterday_start)
        today_tasks = [
            {"content": t["content"], "due_string": t.get("due_string"), "url": t.get("url")}
            for t in active
            if (t.get("section_name") or "").strip().lower() == "today"
            or t.get("due_date") == today
        ]
        not_today_count = sum(1 for t in active if t not in today_tasks)
        return {
            "today": today_tasks,
            "not_today_count": not_today_count,
            "completed_yesterday": [
                {"content": t.get("content"), "completed_at": t.get("completed_at")}
                for t in completed
            ],
        }
    except Exception as exc:
        logger.warning(f"morning todoist block failed: {exc}")
        return None


_WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
_MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def _format_now_ru(dt: datetime) -> str:
    """`понедельник, 3 мая 2026, 04:25` — readable timestamp the routine can quote in the digest header."""
    return f"{_WEEKDAYS_RU[dt.weekday()]}, {dt.day} {_MONTHS_RU[dt.month - 1]} {dt.year}, {dt.strftime('%H:%M')}"


@router.get("/digests/recent", dependencies=[Depends(require_routine_token)])
async def digests_recent(
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Digest)
        .order_by(desc(Digest.created_at))
        .limit(n)
        .all()
    )
    return [
        {
            "id": d.id,
            "type": d.type,
            "summary": (d.content or "")[:500],
            "period_start": d.period_start.isoformat() if d.period_start else None,
            "period_end": d.period_end.isoformat() if d.period_end else None,
            "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in rows
    ]


# ---------- Digest save + deliver ----------

class DigestSave(BaseModel):
    type: str
    content: str
    raw_response: Optional[dict] = None
    period_start: datetime
    period_end: datetime
    routine_session_url: Optional[str] = None


@router.post("/digest/save", dependencies=[Depends(require_routine_token)])
async def digest_save(payload: DigestSave, db: Session = Depends(get_db)):
    if payload.type not in ("morning", "evening"):
        raise HTTPException(status_code=400, detail="type must be morning|evening")
    digest = Digest(
        type=payload.type,
        content=payload.content,
        raw_response=payload.raw_response,
        period_start=payload.period_start,
        period_end=payload.period_end,
        routine_session_url=payload.routine_session_url,
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)
    return {"digest_id": digest.id}


class DigestDeliver(BaseModel):
    digest_id: int


TG_HTML_LIMIT = 4000  # conservative under 4096 to leave room for chunk markers


def _chunk_html(text: str, limit: int = TG_HTML_LIMIT) -> List[str]:
    """Split a markdown-ish string into HTML-safe chunks on line boundaries."""
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    buf: List[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > limit and buf:
            chunks.append("".join(buf))
            buf = [line]
            size = len(line)
        else:
            buf.append(line)
            size += len(line)
    if buf:
        chunks.append("".join(buf))
    return chunks


def _markdown_to_telegram_html(md: str) -> str:
    """Best-effort markdown→Telegram HTML conversion.

    Telegram HTML supports a small whitelist: <b>, <i>, <u>, <s>, <code>, <pre>,
    <a href>. We:
      1. Escape &, <, > globally.
      2. Convert **bold** to <b>, *italic*/_italic_ to <i>, `code` to <code>.
      3. Convert [text](url) to <a href="url">text</a>.

    Markdown headings (## …) are kept as bold lines for readability.
    """
    import re
    safe = html.escape(md, quote=False)

    # Headings: ## Foo  →  <b>Foo</b>
    safe = re.sub(r"(?m)^#{1,6}\s*(.+?)\s*$", r"<b>\1</b>", safe)

    # Links: [text](url) — escape the URL too.
    def _link(match: re.Match) -> str:
        text, url = match.group(1), match.group(2)
        # html.escape already ran, but URL may contain & we want as &amp; (already done).
        return f'<a href="{url}">{text}</a>'

    safe = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, safe)

    # Bold **x** and code `x` (kept simple; nested formatting rarely matters here).
    safe = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", safe)
    return safe


def _admin_chat_id(db: Session) -> Optional[int]:
    # Prefer the value the user edited via Mini App; fall back to the env var
    # that fresh Railway deploys ship with so deliver works out of the box.
    raw = get_setting(db, "admin_telegram_ids") or os.environ.get("ADMIN_TELEGRAM_IDS", "")
    if not raw:
        return None
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                return int(part)
            except ValueError:
                continue
    return None


@router.post("/digest/deliver", dependencies=[Depends(require_routine_token)])
async def digest_deliver(payload: DigestDeliver, db: Session = Depends(get_db)):
    digest = db.query(Digest).filter(Digest.id == payload.digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    chat_id = _admin_chat_id(db)
    if not chat_id:
        raise HTTPException(status_code=400, detail="No admin_telegram_ids configured")

    bot = get_bot()
    if bot is None:
        raise HTTPException(status_code=500, detail="Telegram bot not initialized")

    html_text = _markdown_to_telegram_html(digest.content or "")
    chunks = _chunk_html(html_text)

    first_message_id: Optional[int] = None
    for i, chunk in enumerate(chunks):
        try:
            sent = await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            if i == 0:
                first_message_id = sent.message_id
        except Exception as e:
            logger.error(f"Digest deliver chunk {i} failed: {type(e).__name__}: {e}")
            raise HTTPException(status_code=502, detail=f"Telegram send failed: {e}") from e

    digest.delivered_at = now_georgia()
    digest.delivery_message_id = first_message_id
    db.commit()
    return {
        "delivered": True,
        "telegram_message_id": first_message_id,
        "chunks": len(chunks),
    }
