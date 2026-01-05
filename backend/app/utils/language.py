"""Language detection utilities."""
import re


def detect_language(text: str) -> str:
    """
    Detect language from text based on character analysis.
    Returns: 'ru', 'ua', 'en', 'es' or 'en' as fallback
    """
    if not text:
        return "en"
    
    # Clean text
    text = text.lower().strip()
    
    # Count character types
    cyrillic_count = 0
    latin_count = 0
    ukrainian_specific = 0
    russian_specific = 0
    spanish_specific = 0
    
    # Ukrainian-specific letters: і, ї, є, ґ
    ukrainian_chars = set('іїєґ')
    # Russian-specific letters: ы, э, ъ
    russian_chars = set('ыэъё')
    # Spanish-specific: ñ, ¿, ¡, á, é, í, ó, ú, ü
    spanish_chars = set('ñ¿¡áéíóúü')
    
    for char in text:
        if '\u0400' <= char <= '\u04FF':  # Cyrillic range
            cyrillic_count += 1
            if char in ukrainian_chars:
                ukrainian_specific += 1
            elif char in russian_chars:
                russian_specific += 1
        elif 'a' <= char <= 'z':
            latin_count += 1
            if char in spanish_chars:
                spanish_specific += 1
    
    total = cyrillic_count + latin_count
    if total == 0:
        return "en"
    
    # If mostly Cyrillic
    if cyrillic_count > latin_count:
        # Check for Ukrainian-specific characters
        if ukrainian_specific > 0:
            return "ua"
        # Check for Russian-specific characters
        if russian_specific > 0:
            return "ru"
        
        # Check common Ukrainian words
        ukrainian_words = [
            'привіт', 'будь ласка', 'дякую', 'обкладинка', 'обкладинку',
            'потрібна', 'потрібно', 'потрібен', 'скільки', 'коштує',
            'зробити', 'можете', 'хочу', 'треба', 'мені', 'для',
            'відео', 'ютуб', 'превʼю', "прев'ю", 'мініатюра',
            'канал', 'каналу', 'ціна', 'ціну', 'грн', 'гривень',
        ]
        russian_words = [
            'привет', 'пожалуйста', 'спасибо', 'обложка', 'обложку',
            'нужна', 'нужно', 'нужен', 'сколько', 'стоит',
            'сделать', 'можете', 'хочу', 'надо', 'мне', 'для',
            'видео', 'ютуб', 'превью', 'миниатюра',
            'канал', 'канала', 'цена', 'цену', 'руб', 'рублей',
        ]
        
        text_lower = text.lower()
        ua_matches = sum(1 for w in ukrainian_words if w in text_lower)
        ru_matches = sum(1 for w in russian_words if w in text_lower)
        
        if ua_matches > ru_matches:
            return "ua"
        elif ru_matches > 0:
            return "ru"
        
        # Default to Russian for Cyrillic without specific markers
        return "ru"
    
    # If mostly Latin
    if spanish_specific > 0:
        return "es"
    
    return "en"


def detect_language_from_messages(messages: list) -> str:
    """
    Detect language from a list of messages.
    Combines all messages and detects language.
    """
    if not messages:
        return "en"
    
    combined = " ".join(messages)
    return detect_language(combined)
