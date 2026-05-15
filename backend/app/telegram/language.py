"""Language detection for messages."""
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)

# langdetect is loaded lazily inside detect_language() on first call —
# pulls in ~8 MB of profile data which we don't need at process start.
# Module-level state stays simple: we just remember whether import succeeded.
_langdetect_module = None  # populated on first use; sentinel False = import failed
HAS_LANGDETECT = True  # provisional; flipped to False on first failed import attempt
LangDetectException = Exception  # rebound to real class once langdetect is loaded


def _get_langdetect():
    """Return langdetect module on demand, or None if unavailable."""
    global _langdetect_module, HAS_LANGDETECT, LangDetectException
    if _langdetect_module is False:
        return None
    if _langdetect_module is None:
        try:
            import langdetect as _ld
            _langdetect_module = _ld
            LangDetectException = _ld.LangDetectException
        except ImportError:
            _langdetect_module = False
            HAS_LANGDETECT = False
            return None
    return _langdetect_module


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
    
    # Try langdetect first (lazy-loaded on first use)
    ld = _get_langdetect()
    if ld is not None:
        try:
            detected = ld.detect(text)
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
