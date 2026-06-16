"""Safety filter — 2-layer content moderation.

Layer 1: Keyword blocklist scan against safety_blocklist.yaml.
Layer 2: LLM-based safety classifier (optional, toggle via config).

Halloween festival gets context-aware overrides (allow spooky, block gore).
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SafetyCheckResult:
    is_safe: bool
    layer: str = ""
    blocked_category: str | None = None
    blocked_keyword: str | None = None
    reason: str | None = None


def check_blocklist(
    prompt: str,
    negative_prompt: str,
    blocklist_config: dict,
    festival_id: str,
) -> SafetyCheckResult:
    if not blocklist_config:
        return SafetyCheckResult(is_safe=True, layer="blocklist")

    combined = (prompt + " " + negative_prompt).lower()
    categories = blocklist_config.get("categories", {})

    halloween_allow: set[str] = set()
    halloween_still_block: set[str] = set()
    if festival_id == "halloween":
        overrides = blocklist_config.get("overrides", {}).get("halloween", {})
        halloween_allow = set(
            kw.lower() for kw in overrides.get("allow_keywords", [])
        )
        halloween_still_block = set(
            kw.lower() for kw in overrides.get("still_block", [])
        )

    for category_name, cat_config in categories.items():
        if isinstance(cat_config, dict):
            keywords_raw = cat_config.get("keywords", [])
        else:
            keywords_raw = cat_config

        for keyword in keywords_raw:
            kw = keyword.lower()
            if festival_id == "halloween" and kw in halloween_allow:
                continue
            if kw in combined:
                return SafetyCheckResult(
                    is_safe=False,
                    layer="blocklist",
                    blocked_category=category_name,
                    blocked_keyword=keyword,
                    reason=f"Blocked by keyword '{keyword}' in category '{category_name}'",
                )

    if festival_id == "halloween":
        for kw in halloween_still_block:
            if kw in combined:
                return SafetyCheckResult(
                    is_safe=False,
                    layer="blocklist",
                    blocked_category="violence_gore",
                    blocked_keyword=kw,
                    reason=f"Halloween override: '{kw}' is still blocked (too graphic)",
                )

    return SafetyCheckResult(is_safe=True, layer="blocklist")


def check_with_classifier(
    prompt: str,
    negative_prompt: str,
    gemini_client,
) -> SafetyCheckResult:

    classifier_prompt = (
        "You are a content safety classifier for an internal brand tool. "
        "Analyze this AI image generation prompt and determine if it is SAFE "
        "for use in an official Hong Kong Tramway WhatsApp sticker pack.\n\n"
        "UNSAFE categories:\n"
        "- Political imagery or slogans\n"
        "- Violence, gore, or weapons\n"
        "- Adult, sexual, or explicit content\n"
        "- Hate speech or discrimination\n"
        "- Self-harm or suicide references\n"
        "- Religious proselytizing or controversial religious imagery\n\n"
        "SAFE categories:\n"
        "- Festive, family-friendly content\n"
        "- Cultural celebrations (CNY, Mid-Autumn, Christmas, etc.)\n"
        "- Cute, adorable cartoon style\n"
        "- Seasonal greetings and holiday themes\n"
        "- Mild Halloween spookiness (ghosts, pumpkins, costumes)\n\n"
        f"Prompt to analyze:\n{json.dumps(prompt)}\n\n"
        f"Negative prompt:\n{json.dumps(negative_prompt)}\n\n"
        'Respond with ONLY this JSON:\n'
        '{"safe": true/false, "reason": "..."}'
    )

    try:
        response = gemini_client.generate(classifier_prompt, temperature=0.0)
        import json as _json
        data = _json.loads(response)
        if data.get("safe") is False:
            return SafetyCheckResult(
                is_safe=False,
                layer="llm_classifier",
                reason=data.get("reason", "LLM classifier flagged as unsafe"),
            )
        return SafetyCheckResult(is_safe=True, layer="llm_classifier")
    except Exception as e:
        logger.warning("LLM safety classifier failed (will allow by default): %s", e)
        return SafetyCheckResult(is_safe=True, layer="llm_classifier")


import json  # noqa: E402 (used in classifier prompt)


def full_safety_check(
    prompt: str,
    negative_prompt: str,
    blocklist_config: dict | None,
    gemini_client,
    enable_classifier: bool,
    festival_id: str,
) -> SafetyCheckResult:

    if blocklist_config:
        result = check_blocklist(
            prompt, negative_prompt, blocklist_config, festival_id
        )
        if not result.is_safe:
            return result

    if enable_classifier and gemini_client is not None:
        result = check_with_classifier(prompt, negative_prompt, gemini_client)
        if not result.is_safe:
            return result

    return SafetyCheckResult(is_safe=True, layer="both")
