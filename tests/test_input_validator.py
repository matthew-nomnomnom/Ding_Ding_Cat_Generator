"""Tests for input_validator.py"""

import pytest
from src.llm.input_validator import (
    ValidationResult,
    detect_language,
    validate_input,
)


class TestDetectLanguage:
    def test_english(self):
        assert detect_language("I want a Christmas sticker") == "en"

    def test_chinese(self):
        assert detect_language("我想要一個聖誕 sticker") == "mixed"

    def test_chinese_only(self):
        assert detect_language("新年快樂萬事如意") == "zh"

    def test_emoji_only(self):
        assert detect_language("🎄🎅☃️") == "emoji"

    def test_empty(self):
        assert detect_language("") == "en"


class TestValidateInput:
    def test_empty_input_rejected(self):
        result = validate_input("", "christmas")
        assert not result.is_valid
        assert "No input provided" in " ".join(result.errors)

    def test_none_input_rejected(self):
        result = validate_input(None, "christmas")
        assert not result.is_valid

    def test_valid_english_input(self):
        result = validate_input("cat with a Santa hat holding a present", "christmas")
        assert result.is_valid
        assert result.detected_language == "en"
        assert result.sanitized_input == "cat with a Santa hat holding a present"

    def test_valid_chinese_input(self):
        result = validate_input("貓貓戴聖誕帽拎禮物", "christmas")
        assert result.is_valid
        assert result.detected_language == "zh"

    def test_truncation(self):
        long_input = "a" * 600
        result = validate_input(long_input, "christmas")
        assert result.is_valid
        assert len(result.sanitized_input) == 500
        assert any("truncated" in w.lower() for w in result.warnings)

    def test_profanity_blocked(self):
        result = validate_input("kill the cat violently", "christmas")
        assert not result.is_valid
        assert any("violent" in e.lower() for e in result.errors)

    def test_festival_mismatch_warning(self):
        result = validate_input("I want a Halloween pumpkin", "christmas")
        assert result.is_valid
        assert any("halloween" in w.lower() for w in result.warnings)

    def test_festival_match_no_warning(self):
        result = validate_input("Santa Claus with presents", "christmas")
        assert result.is_valid
        mismatch_warnings = [w for w in result.warnings if "halloween" in w.lower() or "another festival" in w.lower()]
        assert len(mismatch_warnings) == 0

    def test_brand_mention_warning(self):
        result = validate_input("cat like Hello Kitty", "christmas")
        assert result.is_valid
        assert any("hello kitty" in w.lower() for w in result.warnings)

    def test_short_chinese_input_allowed(self):
        result = validate_input("新年", "chinese-new-year")
        assert result.is_valid
        assert result.sanitized_input == "新年"

    def test_single_char_input_allowed(self):
        result = validate_input("貓", "mid-autumn")
        assert result.is_valid
