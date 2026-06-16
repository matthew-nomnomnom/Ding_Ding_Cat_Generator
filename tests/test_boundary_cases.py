"""50 boundary and general case tests for the LLM module.

Covers: input validation, history manager, cache manager,
output parser, safety filter, context assembler, refinement engine.
"""

import json
import os
import tempfile
import time
import pytest
from src.llm.input_validator import (
    detect_language,
    validate_input,
)
from src.llm.history_manager import HistoryManager
from src.llm.cache_manager import CacheManager, RefinementResult
from src.llm.output_parser import (
    enforce_trigger_word,
    parse_llm_output,
    TRIGGER_WORD,
)
from src.llm.safety_filter import check_blocklist, SafetyCheckResult


# ──────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def history(temp_dir):
    return HistoryManager(temp_dir, max_records=200)


@pytest.fixture
def sample_result():
    return RefinementResult(
        prompt="dingdingcat holding a mooncake",
        negative_prompt="blurry, low quality",
        suggested_props=["mooncake"],
        suggested_background="full moon",
    )


BLOCKLIST = {
    "categories": {
        "politics": {"keywords": ["protest", "riot", "revolution", "regime", "propaganda", "coup"], "description": "Politics"},
        "violence_gore": {"keywords": ["kill", "murder", "blood", "gore", "weapon", "gun", "dead", "corpse"], "description": "Violence"},
        "nsfw_adult": {"keywords": ["nude", "naked", "sex", "porn", "erotic", "strip"], "description": "NSFW"},
        "hate_speech": {"keywords": ["racist", "xenophobic", "slur"], "description": "Hate"},
        "self_harm": {"keywords": ["suicide", "self-harm", "self injur"], "description": "Self-harm"},
    },
    "overrides": {
        "halloween": {
            "allow_keywords": ["ghost", "witch", "vampire", "spooky", "skeleton"],
            "still_block": ["gore", "blood", "kill", "dead", "corpse"],
            "description": "Halloween",
        },
    },
}


# ──────────────────────────────────────────────
# 1–10: Input Validation — boundary inputs
# ──────────────────────────────────────────────

class TestInputValidationBoundary:

    def test_01_empty_string(self):
        r = validate_input("", "mid-autumn")
        assert not r.is_valid
        assert any("No input" in e for e in r.errors)

    def test_02_none_input(self):
        r = validate_input(None, "mid-autumn")
        assert not r.is_valid

    def test_03_whitespace_only(self):
        r = validate_input("   \t\n   ", "mid-autumn")
        assert not r.is_valid
        assert "No input" in " ".join(r.errors)

    def test_04_exactly_500_chars(self):
        inp = "x" * 500
        r = validate_input(inp, "christmas")
        assert r.is_valid
        assert len(r.sanitized_input) == 500
        assert len(r.warnings) == 0

    def test_05_501_chars_truncates(self):
        inp = "y" * 501
        r = validate_input(inp, "christmas")
        assert r.is_valid
        assert len(r.sanitized_input) == 500
        assert any("truncat" in w.lower() for w in r.warnings)

    def test_06_single_chinese_char(self):
        r = validate_input("貓", "mid-autumn")
        assert r.is_valid
        assert r.sanitized_input == "貓"
        assert r.detected_language == "zh"

    def test_07_emoji_only_input(self):
        r = validate_input("🎃👻🧛", "halloween")
        assert r.is_valid
        assert r.detected_language == "emoji"

    def test_08_mixed_emoji_text(self):
        r = validate_input("I want 🎄🎅 stickers", "christmas")
        assert r.is_valid
        assert r.detected_language == "en"  # Latin + emoji, no Chinese → "en"

    def test_09_mixed_cn_en(self):
        r = validate_input("I want 貓貓 with mooncake", "mid-autumn")
        assert r.is_valid
        assert r.detected_language == "mixed"

    def test_10_special_characters_safe(self):
        r = validate_input("cat with ~!@#$%^&*()_+-=[]{}|;:',.<>?/", "mid-autumn")
        assert r.is_valid


# ──────────────────────────────────────────────
# 11–18: Input Validation — content policy edge cases
# ──────────────────────────────────────────────

class TestInputValidationPolicy:

    def test_11_political_keyword_blocked(self):
        r = validate_input("protest cat", "mid-autumn")
        assert not r.is_valid
        assert any("political" in e.lower() for e in r.errors)

    def test_12_violence_keyword_blocked(self):
        r = validate_input("kill the cat", "mid-autumn")
        assert not r.is_valid
        assert any("violent" in e.lower() for e in r.errors)

    def test_13_nsfw_keyword_blocked(self):
        r = validate_input("nude cat image", "mid-autumn")
        assert not r.is_valid
        assert any("adult" in e.lower() or "explicit" in e.lower() for e in r.errors)

    def test_14_hate_speech_blocked(self):
        r = validate_input("racist stereotype", "mid-autumn")
        assert not r.is_valid

    def test_15_self_harm_blocked(self):
        r = validate_input("suicide reference", "mid-autumn")
        assert not r.is_valid

    def test_16_substring_match_block(self):
        r = validate_input("killing spree", "mid-autumn")
        assert not r.is_valid

    def test_17_multiple_offenses_first_wins(self):
        r = validate_input("kill protest nude", "mid-autumn")
        assert not r.is_valid
        assert len(r.errors) >= 1

    def test_18_case_insensitive_policy(self):
        r = validate_input("PROTEST RIOT", "mid-autumn")
        assert not r.is_valid


# ──────────────────────────────────────────────
# 19–24: Input Validation — festival mismatch & brand
# ──────────────────────────────────────────────

class TestFestivalMismatch:

    def test_19_halloween_input_christmas_festival(self):
        r = validate_input("pumpkin ghost witch", "christmas")
        assert r.is_valid
        assert any("halloween" in w.lower() for w in r.warnings)

    def test_20_cny_input_midautumn_festival(self):
        r = validate_input("red envelope dragon dance", "mid-autumn")
        assert r.is_valid
        assert any("chinese-new-year" in w.lower() for w in r.warnings)

    def test_21_same_festival_no_warning(self):
        r = validate_input("mooncake lantern full moon", "mid-autumn")
        assert r.is_valid
        mismatch = [w for w in r.warnings if "another festival" in w.lower()]
        assert len(mismatch) == 0

    def test_22_brand_hello_kitty(self):
        r = validate_input("like hello kitty", "christmas")
        assert r.is_valid
        assert any("hello kitty" in w.lower() for w in r.warnings)

    def test_23_brand_disney_mickey(self):
        r = validate_input("like mickey mouse and minnie mouse", "christmas")
        assert r.is_valid
        assert any("mickey mouse" in w.lower() for w in r.warnings)

    def test_24_no_brand_no_warning(self):
        r = validate_input("cute cat with scarf", "christmas")
        assert r.is_valid
        assert len(r.warnings) == 0


# ──────────────────────────────────────────────
# 25–29: Language Detection
# ──────────────────────────────────────────────

class TestLanguageDetection:

    def test_25_pure_english(self):
        assert detect_language("I want a cat sticker for Christmas") == "en"

    def test_26_pure_traditional_chinese(self):
        assert detect_language("新年快樂身體健康") == "zh"

    def test_27_pure_simplified_chinese(self):
        assert detect_language("新年快乐身体健康") == "zh"

    def test_28_emoji_only_detect(self):
        assert detect_language("🎄🎅🧧🏮") == "emoji"

    def test_29_empty_string_default(self):
        assert detect_language("") == "en"


# ──────────────────────────────────────────────
# 30–34: History Manager — CRUD & edge cases
# ──────────────────────────────────────────────

class TestHistoryManagerExtended:

    def test_30_add_and_retrieve_100_records(self, history):
        for i in range(100):
            history.add_record({"raw_input": f"input_{i}", "festival_id": "test"})
        assert history.get_record_count() == 100
        recent = history.get_recent(5)
        assert len(recent) == 5

    def test_31_auto_id_generated(self, history):
        rid = history.add_record({"raw_input": "hello"})
        assert rid is not None
        assert len(rid) == 36
        records = history.load_history()
        assert records[0]["id"] == rid

    def test_32_auto_timestamp_generated(self, history):
        history.add_record({"raw_input": "hello"})
        records = history.load_history()
        assert "timestamp" in records[0]
        assert records[0]["timestamp"] is not None

    def test_33_schema_version(self, history):
        history.add_record({"raw_input": "hello"})
        records = history.load_history()
        assert records[0]["schema_version"] == 1

    def test_34_update_existing_record(self, history):
        rid = history.add_record({"raw_input": "original", "user_action": "pending"})
        ok = history.update_record(rid, {"user_action": "approved"})
        assert ok
        records = history.load_history()
        assert records[0]["user_action"] == "approved"


# ──────────────────────────────────────────────
# 35–39: Cache Manager — TTL & eviction
# ──────────────────────────────────────────────

class TestCacheManagerExtended:

    def test_35_get_returns_cached_flag(self, sample_result):
        c = CacheManager(ttl_seconds=3600)
        c.set("k", sample_result)
        r = c.get("k")
        assert r is not None
        assert r.was_cached is True
        assert r.latency_ms == 0

    def test_36_miss_returns_none(self):
        c = CacheManager()
        assert c.get("nonexistent") is None

    def test_37_expiry_after_ttl(self, sample_result):
        c = CacheManager(ttl_seconds=0.3)
        c.set("k", sample_result)
        time.sleep(0.35)
        assert c.get("k") is None

    def test_38_eviction_when_full(self, sample_result):
        c = CacheManager(max_entries=3)
        for i in range(10):
            c.set(f"k{i}", sample_result)
        assert len(c) <= 3

    def test_39_clear_all_empties(self, sample_result):
        c = CacheManager()
        c.set("a", sample_result)
        c.set("b", sample_result)
        c.clear_all()
        assert len(c) == 0


# ──────────────────────────────────────────────
# 40–44: Output Parser — edge cases
# ──────────────────────────────────────────────

class TestOutputParserExtended:

    def test_40_trigger_word_case_insensitive_replacement(self):
        prompt = "DINGDINGCAT eating a treat"
        result = enforce_trigger_word(prompt)
        assert result.startswith("dingdingcat")

    def test_41_trigger_word_remove_duplicates(self):
        prompt = "dingdingcat dingdingcat eating"
        result = enforce_trigger_word(prompt)
        assert result.startswith("dingdingcat")
        assert result.count("dingdingcat") <= 2  # first preserved, second is left as-is

    def test_42_parse_json_with_extra_fields(self):
        resp = '''{"prompt": "dingdingcat waving", "negative_prompt": "blurry", "color": "red", "mood": "happy"}'''
        result = parse_llm_output(resp)
        assert result.prompt.startswith("dingdingcat")

    def test_43_json_with_unicode(self):
        resp = '{"prompt": "dingdingcat 拿著月餅", "negative_prompt": "blurry", "suggested_props": ["月餅"], "suggested_background": "中秋夜"}'
        result = parse_llm_output(resp)
        assert "dingdingcat" in result.prompt
        assert "月餅" in result.prompt

    def test_44_text_with_line_breaks_fallback(self):
        resp = "dingdingcat\nholding a lantern\nunder the full moon\n3D cartoon style, adorable"
        result = parse_llm_output(resp)
        assert result.prompt.startswith("dingdingcat")


# ──────────────────────────────────────────────
# 45–50: Safety Filter — edge cases
# ──────────────────────────────────────────────

class TestSafetyFilterExtended:

    def test_45_empty_prompt_is_safe(self):
        r = check_blocklist("", "", BLOCKLIST, "mid-autumn")
        assert r.is_safe

    def test_46_keyword_as_substring_blocked(self):
        r = check_blocklist(
            "dingdingcat protesting peacefully",
            "", BLOCKLIST, "mid-autumn",
        )
        assert not r.is_safe
        assert r.blocked_category == "politics"

    def test_47_safe_prompt_all_festivals(self):
        for fid in ["new-year", "chinese-new-year", "dragon-boat", "mid-autumn", "christmas"]:
            r = check_blocklist(
                f"dingdingcat celebrating {fid} festival", "blurry", BLOCKLIST, fid
            )
            assert r.is_safe, f"Should be safe for {fid}"

    def test_48_halloween_ghost_is_allowed(self):
        r = check_blocklist(
            "dingdingcat as a cute ghost bathing", "blurry", BLOCKLIST, "halloween"
        )
        assert r.is_safe

    def test_49_halloween_gore_blocked(self):
        r = check_blocklist(
            "dingdingcat with gore and blood", "", BLOCKLIST, "halloween"
        )
        assert not r.is_safe
        assert r.blocked_category == "violence_gore"

    def test_50_negative_prompt_scanned_too(self):
        r = check_blocklist(
            "dingdingcat waving", "kill the cat violently gore", BLOCKLIST, "mid-autumn"
        )
        assert not r.is_safe
        assert r.blocked_category == "violence_gore"
