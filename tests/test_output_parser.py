"""Tests for output_parser.py"""

import pytest
from src.llm.output_parser import (
    TRIGGER_WORD,
    enforce_trigger_word,
    parse_llm_output,
)
from src.llm.cache_manager import RefinementResult


class TestEnforceTriggerWord:
    def test_already_starts_with_trigger(self):
        prompt = "dingdingcat holding a mooncake, 3D cartoon style"
        result = enforce_trigger_word(prompt)
        assert result.startswith("dingdingcat")

    def test_missing_trigger_prepended(self):
        prompt = "holding a mooncake, 3D cartoon style"
        result = enforce_trigger_word(prompt)
        assert result.startswith("dingdingcat,")
        assert "holding a mooncake" in result

    def test_trigger_mid_prompt_moved_to_start(self):
        prompt = "cute mascot, dingdingcat, holding a mooncake"
        result = enforce_trigger_word(prompt)
        assert result.startswith("dingdingcat,")
        assert "cute mascot" in result
        assert "holding a mooncake" in result

    def test_uppercase_trigger_normalized(self):
        prompt = "DingDingCat eating a mooncake"
        result = enforce_trigger_word(prompt)
        assert result.startswith("dingdingcat")

    def test_empty_prompt(self):
        prompt = ""
        result = enforce_trigger_word(prompt)
        assert result.startswith("dingdingcat")


class TestParseLlmOutput:
    def test_valid_json(self):
        response = """{"prompt": "dingdingcat holding a lantern", "negative_prompt": "blurry", "suggested_props": ["lantern"], "suggested_background": "full moon"}"""
        result = parse_llm_output(response)
        assert isinstance(result, RefinementResult)
        assert result.prompt.startswith("dingdingcat")
        assert result.negative_prompt == "blurry"
        assert "lantern" in result.suggested_props
        assert result.suggested_background == "full moon"

    def test_markdown_wrapped_json(self):
        response = """```json
{"prompt": "dingdingcat with a santa hat", "negative_prompt": "blurry", "suggested_props": ["santa hat"], "suggested_background": "snow"}
```"""
        result = parse_llm_output(response)
        assert result.prompt.startswith("dingdingcat")
        assert "santa hat" in result.prompt

    def test_bare_text_fallback(self):
        response = "dingdingcat holding a mooncake under the full moon, adorable 3D cartoon style"
        result = parse_llm_output(response)
        assert result.prompt.startswith("dingdingcat")
        assert "mooncake" in result.prompt
        assert "blurry" in result.negative_prompt  # default

    def test_missing_fields_defaulted(self):
        response = """{"prompt": "dingdingcat waving"}"""
        result = parse_llm_output(response)
        assert result.prompt.startswith("dingdingcat")
        assert result.negative_prompt != ""
        assert isinstance(result.suggested_props, list)
        assert isinstance(result.suggested_background, str)

    def test_trigger_word_enforced_on_parsed(self):
        response = """{"prompt": "a cat holding a mooncake", "negative_prompt": "blurry"}"""
        result = parse_llm_output(response)
        assert result.prompt.startswith("dingdingcat,")

    def test_alt_field_names_accepted(self):
        response = """{"refined_prompt": "dingdingcat with lantern", "negative": "blurry and ugly"}"""
        result = parse_llm_output(response)
        assert "dingdingcat" in result.prompt
        assert "blurry" in result.negative_prompt

    def test_handles_whitespace(self):
        response = """  \n  {"prompt": "dingdingcat  eating  mooncake",  "negative_prompt":  "blurry"}  \n  """
        result = parse_llm_output(response)
        assert "dingdingcat" in result.prompt
