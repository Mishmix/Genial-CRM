"""Language detection for messages."""
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Try to use langdetect, fallback to simple heuristics
try:
    from langdetect import detect as langdetect_detect
    from langdetect import LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    LangDetectException = Exception


# Language code mapping
LANG_MAP = {
    "ru": "ru",
    "uk": "ua",  # Ukrainian
    "ua": "ua",
    "en": "en",
    "es": "es",
}

# Cyrillic character ranges
CYRILLIC_CHARS = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяіїєґ")
UKRAINIAN_SPECIFIC = set("іїєґ")


def detect_language_simple(text: str) -> str:
    """Simple language detection based on character analysis."""
    if not text:
        return "en"
    
    text_lower = text.lower()
    
    # Count character types
    cyrillic_count = sum(1 for c in text_lower if c in CYRILLIC_CHARS)
    ukrainian_count = sum(1 for c in text_lower if c in UKRAINIAN_SPECIFIC)
    latin_count = sum(1 for c in text_lower if c.isalpha() and c not in CYRILLIC_CHARS)
    
    total_alpha = cyrillic_count + latin_count
    if total_alpha == 0:
        return "en"
    
    # If mostly Cyrillic
    if cyrillic_count > latin_count:
        # Check for Ukrainian-specific characters
        if ukrainian_count > 0:
            return "ua"
        return "ru"
    
    # Check for Spanish indicators
    spanish_chars = set("áéíóúüñ¿¡")
    if any(c in text_lower for c in spanish_chars):
        return "es"
    
    return "en"


async def detect_language(
    text: str,
    user_language_code: Optional[str] = None,
) -> str:
    """
    Detect language of text.
    
    Priority:
    1. langdetect library (if confident)
    2. User's Telegram language_code
    3. Simple heuristics
    
    Returns: ru, en, es, or ua
    """
    if not text or len(text.strip()) < 3:
        # Too short, use user's language or default
        if user_language_code:
            return LANG_MAP.get(user_language_code, "en")
        return "en"
    
    # Try langdetect first
    if HAS_LANGDETECT:
        try:
            detected = langdetect_detect(text)
            mapped = LANG_MAP.get(detected)
            if mapped:
                return mapped
        except LangDetectException:
            pass
        except Exception as e:
            logger.warning(f"langdetect error: {type(e).__name__}")
    
    # Fallback to simple detection
    simple_result = detect_language_simple(text)
    
    # If simple detection is uncertain and we have user language, prefer that
    if simple_result == "en" and user_language_code:
        mapped = LANG_MAP.get(user_language_code)
        if mapped:
            return mapped
    
    return simple_result
