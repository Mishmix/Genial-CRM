"""Text normalization and transliteration for fuzzy search."""
import re
from typing import List, Set

# Cyrillic to Latin transliteration table
CYR_TO_LAT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # Ukrainian specific
    'і': 'i', 'ї': 'yi', 'є': 'ye', 'ґ': 'g',
}

# Latin to Cyrillic (approximate, for search)
LAT_TO_CYR = {
    'a': 'а', 'b': 'б', 'c': 'с', 'd': 'д', 'e': 'е', 'f': 'ф', 'g': 'г',
    'h': 'х', 'i': 'и', 'j': 'й', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н',
    'o': 'о', 'p': 'п', 'q': 'к', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у',
    'v': 'в', 'w': 'в', 'x': 'кс', 'y': 'и', 'z': 'з',
}

# Common keyboard layout mistakes (RU <-> EN)
KEYBOARD_RU_TO_EN = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u',
    'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's',
    'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l',
    'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b',
    'т': 'n', 'ь': 'm', 'б': ',', 'ю': '.',
}

KEYBOARD_EN_TO_RU = {v: k for k, v in KEYBOARD_RU_TO_EN.items()}


def normalize_text(text: str) -> str:
    """
    Normalize text for search:
    - lowercase
    - remove extra whitespace
    - remove punctuation
    - normalize similar characters
    """
    if not text:
        return ""
    
    text = text.lower().strip()
    
    # Replace similar characters
    text = text.replace('ё', 'е')
    text = text.replace('і', 'и')  # Ukrainian і -> и
    
    # Remove punctuation and extra spaces
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def transliterate_cyr_to_lat(text: str) -> str:
    """Transliterate Cyrillic text to Latin."""
    result = []
    for char in text.lower():
        result.append(CYR_TO_LAT.get(char, char))
    return ''.join(result)


def transliterate_lat_to_cyr(text: str) -> str:
    """Transliterate Latin text to Cyrillic (approximate)."""
    result = []
    for char in text.lower():
        result.append(LAT_TO_CYR.get(char, char))
    return ''.join(result)


def convert_keyboard_layout(text: str, to_english: bool = True) -> str:
    """Convert text typed in wrong keyboard layout."""
    mapping = KEYBOARD_RU_TO_EN if to_english else KEYBOARD_EN_TO_RU
    result = []
    for char in text.lower():
        result.append(mapping.get(char, char))
    return ''.join(result)


def generate_search_variants(query: str) -> Set[str]:
    """
    Generate multiple search variants for fuzzy matching:
    - Original normalized
    - Transliterated (both directions)
    - Keyboard layout converted
    """
    variants = set()
    
    if not query:
        return variants
    
    # Original normalized
    normalized = normalize_text(query)
    variants.add(normalized)
    
    # Check if text contains Cyrillic
    has_cyrillic = bool(re.search(r'[а-яёіїєґ]', query.lower()))
    has_latin = bool(re.search(r'[a-z]', query.lower()))
    
    if has_cyrillic:
        # Cyrillic -> Latin transliteration
        variants.add(transliterate_cyr_to_lat(normalized))
        # Wrong keyboard layout (typed in Russian layout but meant English)
        variants.add(convert_keyboard_layout(normalized, to_english=True))
    
    if has_latin:
        # Latin -> Cyrillic transliteration
        variants.add(transliterate_lat_to_cyr(normalized))
        # Wrong keyboard layout (typed in English layout but meant Russian)
        variants.add(convert_keyboard_layout(normalized, to_english=False))
    
    # Remove empty strings
    variants.discard('')
    
    return variants


def build_client_search_text(
    first_name: str,
    last_name: str = None,
    username: str = None,
) -> str:
    """Build searchable text for a client with all variants."""
    parts = []
    
    for text in [first_name, last_name, username]:
        if text:
            variants = generate_search_variants(text)
            parts.extend(variants)
    
    return ' '.join(parts)
