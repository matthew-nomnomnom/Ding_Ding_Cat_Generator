"""LLM Prompt Refinement Engine — Main Orchestrator.

Ties together: input validation → cache check → context assembly →
Gemini LLM call → output parsing → safety filter → user approval simulation →
history persistence → cache update.

Called by the UI layer when the user submits their input.
"""

import logging
import os
import time
from pathlib import Path

from .cache_manager import CacheManager, RefinementResult
from .context_assembler import assemble_full_prompt
from .gemini_client import CircuitBreakerOpenError, GeminiClient, GeminiError
from .history_manager import HistoryManager
from .input_validator import ValidationResult, validate_input
from .output_parser import OutputParseError, parse_llm_output
from .safety_filter import SafetyCheckResult, full_safety_check

logger = logging.getLogger(__name__)


class RefinementError(Exception):
    pass


class RefinementBlockedError(RefinementError):
    pass


class RefinementEngine:
    def __init__(
        self,
        app_config_dir: str,
        festivals_config: dict,
        llm_settings: dict,
        blocklist_config: dict | None = None,
    ):
        gemini_cfg = llm_settings.get("gemini", {})
        api_key_env = gemini_cfg.get("api_key_env", "GEMINI_API_KEY")
        api_key = os.environ.get(api_key_env, "")
        if not api_key:
            raise RefinementError(
                f"Gemini API key not found. "
                f"Set the {api_key_env} environment variable."
            )

        self._festivals_config = festivals_config
        self._llm_settings = llm_settings

        history_cfg = llm_settings.get("history", {})
        self._history = HistoryManager(
            app_config_dir=app_config_dir,
            max_records=history_cfg.get("max_records", 200),
        )
        self._context_count = history_cfg.get("context_record_count", 5)

        cache_cfg = llm_settings.get("cache", {})
        self._cache = CacheManager(
            ttl_seconds=cache_cfg.get("ttl_seconds", 86400),
            max_entries=cache_cfg.get("max_entries", 1000),
        )

        self._gemini = GeminiClient(api_key, llm_settings)

        self._blocklist_config = blocklist_config

        safety_cfg = llm_settings.get("safety", {})
        self._enable_classifier = safety_cfg.get("enable_llm_classifier", True)

        self._system_prompt_template = self._load_system_prompt()

    def refine_prompt(
        self, festival_id: str, user_input: str
    ) -> tuple[RefinementResult, list[str]]:
        warnings: list[str] = []

        validation = validate_input(
            user_input, festival_id, self._blocklist_config
        )
        warnings.extend(validation.warnings)
        if validation.errors:
            raise RefinementError("; ".join(validation.errors))

        sanitized = validation.sanitized_input
        detected_language = validation.detected_language

        cache_key = self._history.get_cache_key(festival_id, sanitized)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit for key %s", cache_key[:16])
            return cached, warnings

        past_records = self._history.get_recent(self._context_count)

        full_prompt = assemble_full_prompt(
            festival_id=festival_id,
            user_input=sanitized,
            festivals_config=self._festivals_config,
            system_prompt_template=self._system_prompt_template,
            past_records=past_records,
        )

        t_start = time.monotonic()

        try:
            raw_response = self._gemini.generate(
                full_prompt,
                temperature=self._llm_settings.get("gemini", {}).get(
                    "temperature", 0.3
                ),
            )
        except CircuitBreakerOpenError as e:
            raise RefinementError(str(e)) from e
        except GeminiError as e:
            raise RefinementError(f"LLM API call failed: {e}") from e

        latency_ms = int((time.monotonic() - t_start) * 1000)

        try:
            result = parse_llm_output(raw_response)
        except OutputParseError as e:
            logger.warning("Output parsing failed, using raw text fallback: %s", e)
            result = parse_llm_output(raw_response)

        result.latency_ms = latency_ms
        result.raw_llm_response = raw_response

        safety = full_safety_check(
            prompt=result.prompt,
            negative_prompt=result.negative_prompt,
            blocklist_config=self._blocklist_config,
            gemini_client=self._gemini,
            enable_classifier=self._enable_classifier,
            festival_id=festival_id,
        )

        if not safety.is_safe:
            logger.warning(
                "Safety check failed (layer=%s, category=%s): %s",
                safety.layer, safety.blocked_category, safety.reason,
            )
            try:
                retry_prompt = (
                    full_prompt
                    + f"\n\nCRITICAL SAFETY NOTE: Your previous output was blocked "
                    f"because it contained potentially inappropriate content "
                    f"(category: {safety.blocked_category}). "
                    f"Please regenerate a completely different, family-friendly prompt "
                    f"for an official brand mascot sticker."
                )
                raw_response = self._gemini.generate(
                    retry_prompt,
                    temperature=self._llm_settings.get("gemini", {}).get(
                        "temperature", 0.3
                    ),
                )
                result = parse_llm_output(raw_response)
                result.raw_llm_response = raw_response

                safety2 = full_safety_check(
                    prompt=result.prompt,
                    negative_prompt=result.negative_prompt,
                    blocklist_config=self._blocklist_config,
                    gemini_client=self._gemini,
                    enable_classifier=self._enable_classifier,
                    festival_id=festival_id,
                )
                if not safety2.is_safe:
                    raise RefinementBlockedError(
                        f"Generated prompt was blocked by safety filter "
                        f"({safety2.blocked_category}). Please rephrase your request."
                    )
            except GeminiError as e:
                raise RefinementBlockedError(
                    f"Generated prompt was blocked by safety filter and retry failed. "
                    f"Please rephrase your request."
                ) from e

        record = {
            "festival_id": festival_id,
            "raw_input": sanitized,
            "detected_language": detected_language,
            "refined_prompt": result.prompt,
            "negative_prompt": result.negative_prompt,
            "suggested_props": result.suggested_props,
            "suggested_background": result.suggested_background,
            "user_action": "pending_approval",
            "user_edited_prompt": None,
            "image_urls": [],
            "generation_params": {},
            "llm_model": self._llm_settings.get("gemini", {}).get(
                "model", "gemini-2.5-flash"
            ),
            "refinement_latency_ms": latency_ms,
        }
        record_id = self._history.add_record(record)

        self._cache.set(cache_key, result)

        logger.info(
            "Refinement complete: record=%s, latency=%dms, cached=%s",
            record_id[:8], latency_ms, "no",
        )
        return result, warnings

    def approve_result(
        self, refined_prompt: str, user_edited_prompt: str | None = None
    ) -> str | None:

        records = self._history.load_history()
        for record in reversed(records):
            if record.get("refined_prompt") == refined_prompt:
                if user_edited_prompt:
                    record["user_action"] = "edited"
                    record["user_edited_prompt"] = user_edited_prompt
                else:
                    record["user_action"] = "approved"
                self._history.update_record(record["id"], record)
                return record["id"]
        return None

    def reject_result(self, refined_prompt: str) -> str | None:

        records = self._history.load_history()
        for record in reversed(records):
            if record.get("refined_prompt") == refined_prompt:
                record["user_action"] = "rejected"
                self._history.update_record(record["id"], record)
                return record["id"]
        return None

    def update_with_images(self, refined_prompt: str, image_urls: list[str]) -> None:

        records = self._history.load_history()
        for record in reversed(records):
            if record.get("refined_prompt") == refined_prompt:
                record["image_urls"] = image_urls
                self._history.update_record(record["id"], record)
                return

    def get_history(self) -> list[dict]:
        return self._history.load_history()

    def get_record_count(self) -> int:
        return self._history.get_record_count()

    def clear_cache(self) -> None:
        self._cache.clear_all()

    def reset_circuit(self) -> None:
        self._gemini.reset_circuit()

    def _load_system_prompt(self) -> str:
        config_dir = Path(__file__).parent.parent.parent / "config"
        prompt_path = config_dir / "system_prompt.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        local_path = Path("config") / "system_prompt.txt"
        if local_path.exists():
            return local_path.read_text(encoding="utf-8")

        raise RefinementError(
            "system_prompt.txt not found. "
            "Place it at config/system_prompt.txt relative to the project root."
        )
