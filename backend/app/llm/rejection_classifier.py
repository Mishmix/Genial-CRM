"""Classify free-text rejection reasons into a fixed taxonomy.

The system prompt lives in `Setting["prompt_rejection_classifier"]` and is
editable from Mini App → AI Settings. Default seeded by `seed_prompts.py`.
"""
import json
import re
from typing import Tuple

from sqlalchemy.orm import Session

from app.crud import get_setting
from app.llm.llm_client import _groq_completion
from app.utils.logging import get_logger

logger = get_logger(__name__)


NORMALIZED_REJECTION_CATEGORIES = [
    "too_expensive",      # дорого, торгуется
    "no_urgency",         # не сейчас / нет срочности
    "chose_competitor",   # выбрал другого
    "ghosting",           # перестал отвечать
    "value_unclear",      # не понял ценности
    "no_budget",          # нет денег вообще
    "scope_mismatch",     # не та услуга
    "timing_mismatch",    # не до того сейчас
    "other",              # всё остальное / низкая уверенность
]

CATEGORY_LABEL_RU = {
    "too_expensive": "дорого",
    "no_urgency": "не сейчас",
    "chose_competitor": "выбрал другого",
    "ghosting": "пропал",
    "value_unclear": "не понял ценности",
    "no_budget": "нет бюджета",
    "scope_mismatch": "не подходит формат",
    "timing_mismatch": "сейчас занят",
    "other": "другое",
}

CONFIDENCE_FLOOR = 0.6


async def classify_rejection(
    raw_text: str,
    conversation_context: str,
    db: Session,
) -> Tuple[str, float]:
    """Returns (category, confidence). On any failure → ('other', 0.0)."""
    system = get_setting(db, "prompt_rejection_classifier") or _DEFAULT_PROMPT
    user = (
        f"Причина отказа (свободный текст):\n{raw_text or '(пусто)'}\n\n"
        f"Контекст переписки (последние сообщения):\n{conversation_context or '(нет)'}"
    )
    raw = await _groq_completion(
        [{"role": "system", "content": system},
         {"role": "user", "content": user}],
        max_completion_tokens=200,
        temperature=0.0,
    )
    if not raw:
        return ("other", 0.0)
    try:
        text = raw.strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return ("other", 0.0)
        data = json.loads(m.group(0))
        category = (data.get("category") or "other").strip().lower()
        confidence = float(data.get("confidence") or 0.0)
        if category not in NORMALIZED_REJECTION_CATEGORIES:
            category = "other"
        if confidence < CONFIDENCE_FLOOR:
            category = "other"
        return (category, confidence)
    except Exception as exc:
        logger.warning(f"rejection classify parse failed: {exc}; raw={raw[:200]!r}")
        return ("other", 0.0)


_DEFAULT_PROMPT = """Ты — классификатор причин отказа клиентов фрилансера-дизайнера YouTube-обложек.

Категории (ровно одна из этих 9 строк):
- too_expensive       — клиент торгуется по цене или говорит «дорого»
- no_urgency          — отложил, «потом», «не сейчас», «может позже»
- chose_competitor    — выбрал другого исполнителя
- ghosting            — перестал отвечать без объяснений
- value_unclear       — не понял зачем / не уверен что нужно
- no_budget           — нет денег вообще, не торг
- scope_mismatch      — не та услуга / не подходит формат
- timing_mismatch     — занят сейчас, отложил по времени
- other               — всё остальное / непонятно

Учитывай контекст переписки, не только последнюю фразу.

Возвращай СТРОГО JSON: {"category": "<одна из 9>", "confidence": 0.0-1.0}.
Если confidence < 0.6 — backend сам заменит на 'other'."""
