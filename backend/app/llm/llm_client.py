"""LLM API client (Groq and NIM) for thumbnail classification and order detection."""
import json
import re
import httpx
import time
from typing import List, Dict, Optional

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Groq Config
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

# Gemini Config
GEMINI_MODEL = "gemini-3-flash-preview"

TIMEOUT = 180.0
MAX_RETRIES = 2

# System prompt for thumbnail classification
# ... (same classification prompt)
THUMBNAIL_CLASSIFICATION_PROMPT = """Ты — строгий классификатор входящих сообщений для дизайнера YouTube-обложек.
Задача: определить категорию сообщения клиента.

## Категории (в порядке приоритета проверки)

### 1. "email_lead" - пришёл с рассылки/почты
Маркеры:
- "вы мне писали", "ви мені писали"
- "пишу с рассылки", "пишу з розсилки"
- "получил ваше письмо", "отримав ваш лист"
- "по поводу вашего письма", "щодо вашого листа"
- "с почты", "з пошти", "email", "e-mail", "імейл"
- "увидел ваше предложение", "побачив вашу пропозицію"
- "откликаюсь на ваше сообщение"
- "вы писали на почту", "писали мені на пошту"
- "из рассылки", "з розсилки"
- упоминание что где-то видел/получил сообщение от дизайнера
→ Ответ: {"category":"email_lead"}

### 2. "thumbnail" - явный запрос на превью
Маркеры:
- "превью", "превʼю", "прев'ю", "превьюшка"
- "thumbnail", "миниатюра", "мініатюра"
- "обложка для видео", "обложка на ютуб"
- "обкладинка для відео", "обкладинка на ютуб"
- "шапка и превью", "баннер и превью" (есть превью = thumbnail)
ВАЖНО: Если есть маркеры email_lead + thumbnail → всё равно "email_lead"
→ Ответ: {"category":"thumbnail"}

### 3. "other" - всё остальное
- Приветствия без контекста: "Привет", "Добрый день"
- Общие вопросы: "вы дизайнер?", "какие цены?"
- Только баннер/шапка/оформление (без превью)
- Неопределённые запросы
→ Ответ: {"category":"other"}

## Примеры
"Здравствуйте, вы мне писали на почту по поводу обложек" → {"category":"email_lead"}
"Привет, пишу с рассылки, интересует цена на превью" → {"category":"email_lead"}
"Получил ваше письмо, нужны обложки" → {"category":"email_lead"}
"Привет, нужно превью для видео" → {"category":"thumbnail"}
"Обложка на ютуб сколько стоит?" → {"category":"thumbnail"}
"Добрый день" → {"category":"other"}
"Нужен баннер для канала" → {"category":"other"}

## Правила
1. СНАЧАЛА проверяй маркеры email_lead (приоритет!)
2. Потом проверяй маркеры thumbnail
3. Всё остальное = other
4. Ответ: СТРОГО JSON, один из трёх вариантов"""


async def chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_completion_tokens: int = 1024,
) -> Optional[str]:
    """Send chat completion request to the configured LLM API (Groq or Gemini)."""
    settings = get_settings()
    provider = getattr(settings, "llm_provider", "groq").lower()

    if provider == "gemini":
        if not getattr(settings, "gemini_api_key", None):
            logger.warning("Gemini API key not configured, falling back to Groq if available")
            if settings.groq_api_key:
                return await _groq_completion(messages, model, temperature, max_completion_tokens)
            return None
        return await _gemini_completion(messages, temperature, max_completion_tokens, thinking_level)
    else:
        if not settings.groq_api_key:
            logger.warning("Groq API key not configured")
            return None
        return await _groq_completion(messages, model, temperature, max_completion_tokens)


async def _gemini_completion(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_completion_tokens: int = 2048,
    thinking_level: str = 'minimal',
) -> Optional[str]:
    """Send request to Google Gemini 3 Flash API using the SDK."""
    settings = get_settings()
    
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=settings.gemini_api_key)
        
        # Extract system instruction if present
        system_instruction = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                user_messages.append(msg["content"])
        
        # Join user messages as a single string for simple cases
        contents = "\n".join(user_messages)
        
        logger.info(f"Sending request to Gemini API (model={GEMINI_MODEL}, level=minimal)")
        
        if thinking_level == 'minimal':
            # Gemini 3 Flash Thinking level configuration
            # Requires google-genai >= 1.51.0
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_completion_tokens,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True, # For Gemini 3 Flash preview
                    thinking_level="MINIMAL"
                )
            )
        else:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_completion_tokens
            )
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config
        )
        
        result = response.text
        logger.info(f"Gemini response length: {len(result) if result else 0}")
        return result
        
    except ImportError:
        logger.error("google-genai library not installed")
        return None
    except Exception as e:
        logger.error(f"Gemini API error: {type(e).__name__}: {e}")
        return None


async def _groq_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_completion_tokens: int = 1024,
) -> Optional[str]:
    """Send chat completion request to Groq API."""
    settings = get_settings()
    target_model = model or DEFAULT_GROQ_MODEL
    
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_completion_tokens,
        "top_p": 1.0,
    }
    
    logger.info(f"Sending request to Groq API with model={target_model}")
    
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    GROQ_API_URL,
                    headers=headers,
                    json=payload,
                )
                logger.info(f"Groq API response status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"Groq API error: {response.text}")
                    return None
                
                data = response.json()
                message = data["choices"][0]["message"]
                
                # Get content or reasoning
                result = message.get("content", "")
                reasoning = message.get("reasoning", "")
                
                logger.info(f"Groq content: '{result}', reasoning length: {len(reasoning) if reasoning else 0}")
                
                # If content is empty but reasoning exists, extract from reasoning
                if not result and reasoning:
                    # Look for JSON in reasoning
                    json_match = re.search(r'\{[^}]*"category"[^}]*\}', reasoning)
                    if json_match:
                        result = json_match.group(0)
                        logger.info(f"Extracted JSON from reasoning: {result}")
                    else:
                        # Fallback: check for keywords
                        reasoning_lower = reasoning.lower()
                        if 'thumbnail' in reasoning_lower and 'other' not in reasoning_lower:
                            result = '{"category":"thumbnail"}'
                        else:
                            result = '{"category":"other"}'
                        logger.info(f"Inferred from reasoning keywords: {result}")
                
                return result
                
        except httpx.TimeoutException:
            logger.warning(f"Groq API timeout (attempt {attempt + 1}/{MAX_RETRIES})")
        except Exception as e:
            logger.error(f"Groq API error: {type(e).__name__}: {e}")
            break
    
    return None


async def classify_thumbnail(buffer_messages: List[str]) -> Optional[str]:
    """Classify if client messages indicate interest in YouTube thumbnails."""
    if not buffer_messages:
        return None
    
    messages_text = "\n".join(buffer_messages)
    
    messages = [
        {"role": "system", "content": THUMBNAIL_CLASSIFICATION_PROMPT},
        {"role": "user", "content": f"Сообщения клиента:\n{messages_text}"}
    ]
    
    result = await chat_completion(messages, max_completion_tokens=512, temperature=0.0)
    
    if result:
        result = result.strip()
        # Try to parse JSON
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^}]*"category"[^}]*\}', result)
            if json_match:
                data = json.loads(json_match.group(0))
                category = data.get("category", "").lower()
                if category in ("thumbnail", "email_lead", "other"):
                    logger.info(f"Classification result: {category}")
                    return category
        except json.JSONDecodeError:
            pass
        
        # Fallback: check for keywords
        result_lower = result.lower()
        if '"email_lead"' in result_lower or "'email_lead'" in result_lower:
            return "email_lead"
        if '"thumbnail"' in result_lower or "'thumbnail'" in result_lower:
            return "thumbnail"
        if '"other"' in result_lower or "'other'" in result_lower:
            return "other"
    
    logger.warning(f"Could not parse classification result: {result}")
    return "other"
