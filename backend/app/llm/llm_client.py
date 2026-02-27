"""LLM API client (Groq and Gemini REST) for thumbnail classification and order detection."""
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
        return await _gemini_completion(messages, temperature, max_completion_tokens, thinking_level="minimal")
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
    """Send request to Google Gemini 3 Flash API using direct REST calls with httpx."""
    settings = get_settings()
    api_key = getattr(settings, "gemini_api_key", None)
    
    if not api_key:
        logger.error("Gemini API key not found in settings")
        return None

    try:
        # Construct the REST API request
        # Endpoint for Gemini 3 Flash Preview (supports thinkingLevel)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
        
        # Prepare system instruction and contents
        system_instruction_data = None
        contents = []
        
        for msg in messages:
            role = "user" if msg["role"] == "user" else ("model" if msg["role"] == "assistant" else "system")
            if role == "system":
                system_instruction_data = {
                    "parts": [{"text": msg["content"]}]
                }
            else:
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
        
        # Build the request body
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_completion_tokens,
                "thinkingLevel": thinking_level.upper() if thinking_level else "MINIMAL"
            }
        }
        
        if system_instruction_data:
            payload["systemInstruction"] = system_instruction_data

        logger.info(f"Sending REST request to Gemini API (model={GEMINI_MODEL}, level={thinking_level})")
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code != 200:
                logger.error(f"Gemini API error ({response.status_code}): {response.text}")
                return None
            
            data = response.json()
            
            # Extract content from response
            try:
                result = data['candidates'][0]['content']['parts'][0]['text']
                logger.info(f"Gemini response length: {len(result) if result else 0}")
                return result
            except (KeyError, IndexError) as e:
                logger.error(f"Error parsing Gemini response: {e}. Data: {json.dumps(data)}")
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
