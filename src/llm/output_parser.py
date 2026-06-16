"""Gemini JSON output parser with trigger word enforcement.

Handles: valid JSON, markdown-wrapped JSON, bare text fallback.
Always ensures "dingdingcat" is the first token in the prompt field.
"""

import json
import re

from .cache_manager import RefinementResult

TRIGGER_WORD = "dingdingcat"
DEFAULT_NEGATIVE = (
    "blurry, low quality, deformed, extra limbs, bad anatomy, watermark, "
    "text, nsfw, ugly, distorted face, mutated, poorly drawn, out of frame, "
    "disfigured, bad proportions, gross proportions, duplicate, multiple cats"
)


class OutputParseError(Exception):
    pass


def parse_llm_output(raw_response: str) -> RefinementResult:
    text = raw_response.strip()

    result = _try_parse_json(text)
    if result is None:
        # Strip leading "json" word before trying again
        cleaned = re.sub(r"^(?:json\s*)+", "", text, count=1, flags=re.IGNORECASE).strip()
        result = _try_parse_json(cleaned)
    if result is None:
        result = _try_parse_markdown_json(text)
    if result is None:
        result = _try_extract_any_json(text)
    if result is None:
        result = _try_fallback_text(text)

    result.prompt = enforce_trigger_word(result.prompt)
    result.raw_llm_response = raw_response

    if not result.negative_prompt.strip():
        result.negative_prompt = DEFAULT_NEGATIVE

    if not result.suggested_props:
        result.suggested_props = []

    if not result.suggested_background:
        result.suggested_background = ""

    return result


def enforce_trigger_word(prompt: str) -> str:
    cleaned = prompt.strip().strip('"').strip("'")
    pattern = re.compile(re.escape(TRIGGER_WORD), re.IGNORECASE)

    if pattern.search(cleaned):
        cleaned = pattern.sub(TRIGGER_WORD, cleaned, count=1)
        match = pattern.search(cleaned)
        if match and match.start() > 0:
            before = cleaned[: match.start()].strip()
            after = cleaned[match.start():]
            if before.endswith(","):
                before = before[:-1]
            cleaned = f"{TRIGGER_WORD}, {before} {after}"
            cleaned = " ".join(cleaned.split())
        return cleaned

    return f"{TRIGGER_WORD}, {cleaned}"


def _try_parse_json(text: str) -> RefinementResult | None:
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return _dict_to_result(data)
    except json.JSONDecodeError:
        return None


def _try_parse_markdown_json(text: str) -> RefinementResult | None:
    pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(pattern, text)
    for match in matches:
        result = _try_parse_json(match.strip())
        if result is not None:
            return result
    return None


def _try_extract_any_json(text: str) -> RefinementResult | None:
    # Find all { ... } blocks and try each as JSON
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start : i + 1]
                result = _try_parse_json(candidate)
                if result is not None:
                    return result
                start = -1
    return None


def _try_fallback_text(text: str) -> RefinementResult:
    cleaned = _strip_markdown(text)
    negative = DEFAULT_NEGATIVE

    # Try regex extraction of fields from raw JSON-like text before full fallback
    prompt_match = re.search(
        r'"prompt"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.IGNORECASE
    )
    if prompt_match:
        cleaned = _unescape_json_string(prompt_match.group(1))

    neg_match = re.search(
        r'"negative_prompt"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.IGNORECASE
    )
    if neg_match:
        negative = _unescape_json_string(neg_match.group(1))

    props_match = re.search(
        r'"suggested_props"\s*:\s*\[(.*?)\]', text, re.IGNORECASE | re.DOTALL
    )
    suggested_props = _extract_props(props_match.group(1)) if props_match else []

    bg_match = re.search(
        r'"suggested_background"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.IGNORECASE
    )
    suggested_background = _unescape_json_string(bg_match.group(1)) if bg_match else ""

    return RefinementResult(
        prompt=cleaned,
        negative_prompt=negative,
        suggested_props=suggested_props,
        suggested_background=suggested_background,
    )


def _strip_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1])
    text = text.replace("`", "")
    text = text.replace("**", "")
    return text.strip()


def _unescape_json_string(s: str) -> str:
    # Handle common JSON escape sequences in a regex-extracted string
    s = s.replace('\\"', '"')
    s = s.replace("\\n", "\n")
    s = s.replace("\\t", "\t")
    s = s.replace("\\\\", "\\")
    return s


def _extract_props(text: str) -> list[str]:
    items = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
    return [_unescape_json_string(item) for item in items]


def _dict_to_result(data: dict) -> RefinementResult:
    prompt = data.get("prompt", data.get("refined_prompt", ""))
    if not isinstance(prompt, str) or not prompt.strip():
        for key in ["description", "output", "text", "image_prompt"]:
            candidate = data.get(key, "")
            if isinstance(candidate, str) and candidate.strip():
                prompt = candidate
                break

    negative = data.get(
        "negative_prompt", data.get("negative", DEFAULT_NEGATIVE)
    )
    if not isinstance(negative, str):
        negative = DEFAULT_NEGATIVE

    props = data.get("suggested_props", data.get("props", []))
    if not isinstance(props, list):
        props = []

    background = data.get(
        "suggested_background", data.get("background", "")
    )
    if not isinstance(background, str):
        background = ""

    return RefinementResult(
        prompt=str(prompt),
        negative_prompt=str(negative),
        suggested_props=[str(p) for p in props],
        suggested_background=str(background),
    )
