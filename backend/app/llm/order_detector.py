"""
AI Order Detector - автоматическое определение заказов из переписки.
Анализирует сообщения и определяет согласованные заказы с дедлайнами.
"""
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.llm.groq_client import chat_completion
from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def debug_log(msg: str):
    """Print debug message to stdout."""
    print(f"[ORDER_DETECTOR] {msg}", flush=True)
    logger.info(msg)


ORDER_DETECTION_PROMPT = """Ты анализатор переписки дизайнера YouTube-обложек.

Найди ЗАПРОС НА РАБОТУ от клиента.

Признаки заказа (достаточно ОДНОГО):
- Клиент просит сделать работу ("сделай", "нужна", "хочу", "можешь", "зроби", "потрібна")
- Указан срок ("завтра", "срочно", "к пятнице", "на завтра", "до 15")
- Упоминается тип работы (превью, обложка, баннер, лого)

ВАЖНО: Если клиент что-то просит = это ЗАКАЗ. Не жди подтверждения дизайнера!

Типы услуг (если не указано = thumbnail):
- превью/обложка/миниатюра/thumbnail → "thumbnail"
- баннер/banner → "banner"
- лого/логотип → "logo"
- оформление канала → "channel_design"

Количество: если не указано = 1

Сегодня: {today}

{existing_orders_section}Переписка:
{messages}

Ответь JSON одной строкой:
{{"has_order":true,"confidence":0.9,"reason":"причина","order":{{"service_type":"thumbnail","quantity":1,"amount":null,"deadline_date":"2026-01-06","deadline_text":"на завтра","notes":"описание"}}}}"""


def _format_existing_orders(existing_orders: Optional[List]) -> str:
    """Форматирует список существующих заказов для AI промпта."""
    if not existing_orders:
        return ""

    SERVICE_NAMES = {
        "thumbnail": "Превью",
        "banner": "Баннер",
        "logo": "Лого",
        "avatar": "Аватарка",
        "channel_design": "Оформление канала",
        "cover": "Обложка",
        "template": "Шаблоны",
        "other": "Другое",
    }

    lines = []
    for o in existing_orders:
        service = SERVICE_NAMES.get(o.service_type, o.service_type)
        deadline = o.deadline_date.strftime("%Y-%m-%d") if o.deadline_date else "без дедлайна"
        lines.append(f"- {o.quantity}x {service}, дедлайн: {deadline}")

    return "Уже существующие заказы из этой переписки (обнови их если клиент уточнил детали):\n" + "\n".join(lines) + "\n\n"


async def detect_order(messages: List[Dict[str, Any]], existing_orders: Optional[List] = None) -> Optional[Dict[str, Any]]:
    """
    Анализирует переписку и возвращает заказ если найден.

    Args:
        messages: список сообщений [{direction, text, sent_at}, ...]
        existing_orders: список существующих pending AI заказов для контекста

    Returns:
        {service_type, quantity, amount, deadline_date, notes, confidence, source} или None
    """
    debug_log("=== DETECT_ORDER CALLED ===")

    settings = get_settings()

    debug_log(f"ai_order_detection_enabled = {settings.ai_order_detection_enabled}")

    if not settings.ai_order_detection_enabled:
        debug_log("AI order detection is DISABLED, returning None")
        return None

    # Форматируем сообщения для GPT (последние 30)
    formatted = []
    for msg in messages[-30:]:
        sender = "Дизайнер" if msg.get("direction") == "out" else "Клиент"
        text = msg.get("text", "")
        if text:
            formatted.append(f"{sender}: {text}")

    debug_log(f"Formatted {len(formatted)} messages for GPT")

    if not formatted:
        debug_log(f"No messages to analyze")
        return None

    messages_text = "\n".join(formatted)
    today = datetime.now().strftime("%Y-%m-%d")
    existing_orders_section = _format_existing_orders(existing_orders)

    debug_log(f"Messages for analysis:\n{messages_text}")
    if existing_orders_section:
        debug_log(f"Existing orders context: {existing_orders_section.strip()}")

    try:
        prompt = ORDER_DETECTION_PROMPT.format(
            today=today,
            messages=messages_text,
            existing_orders_section=existing_orders_section,
        )

        debug_log("Calling GPT for order detection...")

        result = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_completion_tokens=500,
        )

        debug_log(f"GPT raw response: {result[:500]}...")

        if not result:
            debug_log("GPT returned empty result")
            return None

        # Парсим JSON из ответа - пробуем разные варианты
        data = None

        # Вариант 1: весь ответ это JSON
        try:
            data = json.loads(result.strip())
        except json.JSONDecodeError:
            pass

        # Вариант 2: ищем JSON в ответе
        if not data:
            # Убираем переносы строк для поиска
            clean_result = result.replace('\n', ' ').replace('\r', '')
            json_match = re.search(r'\{[^{}]*"has_order"[^{}]*\}', clean_result)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        # Вариант 3: ищем вложенный JSON с order
        if not data:
            clean_result = result.replace('\n', ' ').replace('\r', '')
            # Более жадный поиск
            json_match = re.search(r'\{.*"has_order".*"order".*\}', clean_result)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        if not data:
            debug_log(f"Could not parse JSON from response")
            return None

        debug_log(f"Parsed JSON: {data}")

        if not data.get("has_order"):
            reason = data.get("reason", "unknown")
            debug_log(f"No order detected. Reason: {reason}")
            return None

        confidence = data.get("confidence", 0)
        threshold = settings.ai_order_confidence_threshold
        debug_log(f"Confidence: {confidence}, threshold: {threshold}")

        if confidence < threshold:
            debug_log(f"Confidence {confidence} below threshold {threshold}")
            return None

        order = data.get("order")
        if not order:
            debug_log("has_order=true but no order object in response")
            return None

        # Парсим дедлайн
        deadline = parse_deadline(
            order.get("deadline_date"),
            order.get("deadline_text")
        )

        # Дефолт на thumbnail если не указано
        service_type = order.get("service_type", "thumbnail") or "thumbnail"
        quantity = order.get("quantity", 1) or 1

        debug_log(f"ORDER DETECTED: {service_type} x{quantity}, deadline={deadline}, confidence={confidence}")

        return {
            "service_type": service_type,
            "quantity": quantity,
            "amount": order.get("amount"),
            "deadline_date": deadline,
            "deadline_text": order.get("deadline_text"),
            "notes": order.get("notes", ""),
            "confidence": confidence,
            "source": "ai"
        }

    except json.JSONDecodeError as e:
        debug_log(f"JSON parse error: {e}")
        return None
    except Exception as e:
        debug_log(f"Order detection error: {type(e).__name__}: {e}")
        import traceback
        debug_log(traceback.format_exc())
        return None


def parse_deadline(date_str: Optional[str], text: Optional[str]) -> Optional[str]:
    """Парсит дедлайн из разных форматов."""

    # Сначала пробуем готовую дату
    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            pass

    if not text:
        return None

    text_lower = text.lower()
    today = datetime.now()

    # Сегодня (включая "сейчас", "прямо сейчас")
    if any(w in text_lower for w in ["сегодня", "today", "hoy", "сьогодні", "сейчас", "прямо сейчас"]):
        return today.strftime("%Y-%m-%d")

    # Завтра
    if any(w in text_lower for w in ["завтра", "tomorrow", "mañana"]):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # Послезавтра
    if any(w in text_lower for w in ["послезавтра", "через 2 дня"]):
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # "через N дней"
    match = re.search(r"через\s*(\d+)\s*дн", text_lower)
    if match:
        days = int(match.group(1))
        return (today + timedelta(days=days)).strftime("%Y-%m-%d")

    # Дни недели
    weekdays = {
        "понедельник": 0, "вторник": 1, "среда": 2, "среду": 2,
        "четверг": 3, "пятница": 4, "пятницу": 4,
        "суббота": 5, "субботу": 5, "воскресенье": 6,
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
    }

    for day_name, day_num in weekdays.items():
        if day_name in text_lower:
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Конкретная дата "15 января", "15.01"
    months_ru = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
        "мая": 5, "июня": 6, "июля": 7, "августа": 8,
        "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
    }

    for month_name, month_num in months_ru.items():
        match = re.search(rf"(\d{{1,2}})\s*{month_name}", text_lower)
        if match:
            day = int(match.group(1))
            year = today.year
            # Если дата уже прошла в этом году, берём следующий
            target = datetime(year, month_num, day)
            if target < today:
                target = datetime(year + 1, month_num, day)
            return target.strftime("%Y-%m-%d")

    # Формат DD.MM
    match = re.search(r"(\d{1,2})\.(\d{1,2})", text_lower)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = today.year
        try:
            target = datetime(year, month, day)
            if target < today:
                target = datetime(year + 1, month, day)
            return target.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None
