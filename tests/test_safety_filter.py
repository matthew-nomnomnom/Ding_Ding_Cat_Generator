"""Tests for safety_filter.py"""

import pytest
from src.llm.safety_filter import check_blocklist, SafetyCheckResult


BLOCKLIST_CONFIG = {
    "categories": {
        "politics": {
            "keywords": ["protest", "riot", "revolution", "propaganda"],
            "description": "Political imagery",
        },
        "violence_gore": {
            "keywords": ["kill", "blood", "gore", "weapon", "gun"],
            "description": "Violence and gore",
        },
        "nsfw_adult": {
            "keywords": ["nude", "sex", "porn", "erotic"],
            "description": "Adult content",
        },
        "hate_speech": {
            "keywords": ["racist", "xenophobic", "slur"],
            "description": "Hate speech",
        },
        "self_harm": {
            "keywords": ["suicide", "self-harm", "self injur"],
            "description": "Self-harm",
        },
    },
    "overrides": {
        "halloween": {
            "allow_keywords": ["ghost", "witch", "vampire", "spooky", "skeleton"],
            "still_block": ["gore", "blood", "kill"],
            "description": "Halloween allows mild spookiness",
        },
    },
}


class TestCheckBlocklist:
    def test_safe_prompt_passes(self):
        result = check_blocklist(
            "dingdingcat holding a mooncake in a garden",
            "blurry, low quality",
            BLOCKLIST_CONFIG,
            "mid-autumn",
        )
        assert result.is_safe
        assert result.layer == "blocklist"

    def test_violence_blocked(self):
        result = check_blocklist(
            "dingdingcat with a bloody knife",
            "blurry",
            BLOCKLIST_CONFIG,
            "christmas",
        )
        assert not result.is_safe
        assert result.blocked_category == "violence_gore"

    def test_politics_blocked(self):
        result = check_blocklist(
            "dingdingcat at a protest",
            "",
            BLOCKLIST_CONFIG,
            "mid-autumn",
        )
        assert not result.is_safe
        assert result.blocked_category == "politics"

    def test_nsfw_blocked(self):
        result = check_blocklist(
            "nude cat",
            "",
            BLOCKLIST_CONFIG,
            "christmas",
        )
        assert not result.is_safe
        assert result.blocked_category == "nsfw_adult"

    def test_hate_speech_blocked(self):
        result = check_blocklist(
            "racist cat stereotype",
            "",
            BLOCKLIST_CONFIG,
            "mid-autumn",
        )
        assert not result.is_safe
        assert result.blocked_category == "hate_speech"

    def test_self_harm_blocked(self):
        result = check_blocklist(
            "dingdingcat suicide",
            "",
            BLOCKLIST_CONFIG,
            "christmas",
        )
        assert not result.is_safe
        assert result.blocked_category == "self_harm"

    def test_halloween_allows_spooky(self):
        result = check_blocklist(
            "dingdingcat as a cute ghost, spooky witch hat",
            "blurry",
            BLOCKLIST_CONFIG,
            "halloween",
        )
        assert result.is_safe

    def test_halloween_still_blocks_gore(self):
        result = check_blocklist(
            "dingdingcat with gore and blood",
            "",
            BLOCKLIST_CONFIG,
            "halloween",
        )
        assert not result.is_safe
        assert result.blocked_category == "violence_gore"

    def test_no_config_always_safe(self):
        result = check_blocklist(
            "anything goes here",
            "",
            None,
            "mid-autumn",
        )
        assert result.is_safe

    def test_keyword_in_negative_prompt_blocked(self):
        result = check_blocklist(
            "dingdingcat waving",
            "kill, blood, gore",
            BLOCKLIST_CONFIG,
            "mid-autumn",
        )
        assert not result.is_safe
