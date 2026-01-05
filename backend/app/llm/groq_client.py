"""Groq LLM API client for thumbnail classification."""
import json
import re
import httpx
from typing import List, Dict, Optional

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
TIMEOUT = 60.0
MAX_RETRIES = 2

# System prompt for thumbnail classification
THUMBNAIL_CLASSIFICATION_PROMPT = """Ты — строгий классификатор входящих сообщений клиента для дизайнера YouTube-обложек.
Твоя задача: по сообщениям клиента определить категорию.

Правила:
- Верни {"category":"thumbnail"} ТОЛЬКО если клиент явно просит YouTube-обложку/превью/thumbnail/миниатюру (на любом языке), даже если также упоминаются баннеры/шапки/оформление.
- Во всех остальных случаях верни {"category":"other"} (приветствия, общие вопросы, баннер без превью, неопределённость).

Примеры "thumbnail":
- "превью", "превʼю", "прев'ю", "thumbnail", "обложка для видео", "обложка на ютуб", "миниатюра", "превьюшка"
- "обкладинка для відео", "обкладинка на ютуб", "мініатюра"
- "шапка и превью" (есть превью = thumbnail)

Примеры "other":
- "Привет", "Добрый день", "вы дизайнер?"
- "нужен баннер", "шапка для канала", "оформление" (без превью)

ВАЖНО: Ответь ТОЛЬКО JSON без пояснений:
{"category":"thumbnail"} или {"category":"other"}"""


async def chat_completion(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_completion_tokens: int = 1024,
) -> Optional[str]:
    """Send chat completion request to Groq API."""
    settings = get_settings()
    
    if not settings.groq_api_key:
        logger.warning("Groq API key not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_completion_tokens,
        "top_p": 1.0,
    }
    
    logger.info(f"Sending request to Groq API with model={model}")
    
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
                if category in ("thumbnail", "other"):
                    logger.info(f"Classification result: {category}")
                    return category
        except json.JSONDecodeError:
            pass
        
        # Fallback: check for keywords
        result_lower = result.lower()
        if '"thumbnail"' in result_lower or "'thumbnail'" in result_lower:
            return "thumbnail"
        if '"other"' in result_lower or "'other'" in result_lower:
            return "other"
    
    logger.warning(f"Could not parse classification result: {result}")
    return "other"
