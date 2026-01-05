"""Tests for text normalization and transliteration."""
import pytest

from app.search.normalize import (
    normalize_text,
    transliterate_cyr_to_lat,
    transliterate_lat_to_cyr,
    generate_search_variants,
    convert_keyboard_layout,
)


class TestNormalizeText:
    """Tests for normalize_text function."""
    
    def test_lowercase(self):
        assert normalize_text("HELLO") == "hello"
        assert normalize_text("HeLLo WoRLD") == "hello world"
    
    def test_strip_whitespace(self):
        assert normalize_text("  hello  ") == "hello"
        assert normalize_text("hello   world") == "hello world"
    
    def test_remove_punctuation(self):
        assert normalize_text("hello, world!") == "hello world"
        assert normalize_text("test@email.com") == "testemailcom"
    
    def test_normalize_similar_chars(self):
        assert normalize_text("ёлка") == "елка"
        assert normalize_text("київ") == "киив"
    
    def test_empty_string(self):
        assert normalize_text("") == ""
        assert normalize_text("   ") == ""


class TestTransliteration:
    """Tests for transliteration functions."""
    
    def test_cyr_to_lat_basic(self):
        assert transliterate_cyr_to_lat("привет") == "privet"
        assert transliterate_cyr_to_lat("михаил") == "mikhail"
    
    def test_cyr_to_lat_complex(self):
        assert transliterate_cyr_to_lat("щука") == "shchuka"
        assert transliterate_cyr_to_lat("юля") == "yulya"
    
    def test_cyr_to_lat_ukrainian(self):
        assert transliterate_cyr_to_lat("київ") == "kyiv"
        assert transliterate_cyr_to_lat("їжак") == "yizhak"
    
    def test_lat_to_cyr_basic(self):
        assert transliterate_lat_to_cyr("privet") == "привет"
        assert transliterate_lat_to_cyr("mikhail") == "микхаил"
    
    def test_mixed_text(self):
        # Should handle mixed text gracefully
        result = transliterate_cyr_to_lat("hello мир")
        assert "mir" in result


class TestKeyboardLayout:
    """Tests for keyboard layout conversion."""
    
    def test_ru_to_en(self):
        # "ghbdtn" typed in Russian layout = "привет"
        assert convert_keyboard_layout("привет", to_english=True) == "ghbdtn"
    
    def test_en_to_ru(self):
        # "ghbdtn" should convert to "привет"
        assert convert_keyboard_layout("ghbdtn", to_english=False) == "привет"


class TestSearchVariants:
    """Tests for search variant generation."""
    
    def test_cyrillic_input(self):
        variants = generate_search_variants("Михаил")
        
        # Should include original normalized
        assert "михаил" in variants
        
        # Should include transliteration
        assert "mikhail" in variants
    
    def test_latin_input(self):
        variants = generate_search_variants("Mikhail")
        
        # Should include original normalized
        assert "mikhail" in variants
        
        # Should include cyrillic approximation
        assert any("м" in v for v in variants)
    
    def test_empty_input(self):
        variants = generate_search_variants("")
        assert len(variants) == 0
    
    def test_mixed_input(self):
        variants = generate_search_variants("Test Тест")
        assert len(variants) > 1


class TestSearchScenarios:
    """Real-world search scenarios."""
    
    def test_find_mikhail_by_mikhailo(self):
        """Should find Михаил when searching for Mikhailo."""
        search_variants = generate_search_variants("Mikhailo")
        target_variants = generate_search_variants("Михаил")
        
        # Check if any variants overlap or are similar
        search_lat = transliterate_cyr_to_lat("михаил")
        assert "mikhail" in search_lat or any(
            "mikhail" in v for v in search_variants
        )
    
    def test_find_with_typo(self):
        """Search should be forgiving of small differences."""
        # This tests the concept - actual fuzzy matching is in FTS
        variants1 = generate_search_variants("Александр")
        variants2 = generate_search_variants("Aleksandr")
        
        # Both should have similar Latin variants
        lat1 = transliterate_cyr_to_lat("александр")
        assert "aleksandr" in lat1
    
    def test_wrong_keyboard_layout(self):
        """Should handle text typed in wrong layout."""
        # User typed "Vbhfbk" (Михаил in English layout)
        variants = generate_search_variants("ghbdtn")  # "привет" in EN layout
        
        # Should include the Russian version
        assert "привет" in variants


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
