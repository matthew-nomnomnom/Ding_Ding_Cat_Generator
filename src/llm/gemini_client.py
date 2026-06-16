"""Google Gemini API client with retry, circuit breaker, and JSON mode.

Handles: network timeouts, rate limiting, auth errors.
Circuit opens after N failures in T seconds, resets after clean window.
"""

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    pass


class CircuitBreakerOpenError(GeminiError):
    pass


class GeminiClient:
    def __init__(self, api_key: str, settings: dict):
        self._api_key = api_key
        self._model = settings.get("model", "gemini-2.5-flash")
        self._timeout = settings.get("timeout_seconds", 15)

        retry_cfg = settings.get("retry", {})
        self._max_attempts = retry_cfg.get("max_attempts", 3)
        self._backoff_seconds: list[float] = retry_cfg.get("backoff_seconds", [2, 4, 8])

        cb_cfg = settings.get("circuit_breaker", {})
        self._cb_threshold = cb_cfg.get("failure_threshold", 5)
        self._cb_window = cb_cfg.get("window_seconds", 60)
        self._cb_reset_after = cb_cfg.get("reset_after_seconds", 300)

        self._failure_timestamps: list[float] = []
        self._circuit_open_since: float | None = None

        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._client = genai
            except ImportError:
                raise GeminiError(
                    "google-generativeai package not installed. "
                    "Run: pip install google-generativeai"
                )
        return self._client

    def generate(self, prompt: str, temperature: float = 0.3) -> str:
        self._check_circuit()

        genai = self._get_client()
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": 512,
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                model = genai.GenerativeModel(
                    model_name=self._model,
                    generation_config=generation_config,
                )
                response = model.generate_content(prompt)
                if not response.text:
                    raise GeminiError("Gemini returned empty response")
                self._record_success()
                return response.text
            except Exception as e:
                last_error = e
                self._record_failure()
                err_msg = _safe_str(e)
                logger.warning(
                    "Gemini call attempt %d/%d failed: %s",
                    attempt, self._max_attempts, err_msg,
                )
                if attempt < self._max_attempts:
                    delay = self._backoff_seconds[min(attempt - 1, len(self._backoff_seconds) - 1)]
                    time.sleep(delay)
                else:
                    raise GeminiError(
                        f"Gemini API call failed after {self._max_attempts} attempts: {err_msg}"
                    ) from last_error

        raise GeminiError("Unreachable")

    def generate_json(
        self, prompt: str, temperature: float = 0.3
    ) -> dict:
        response_text = self.generate(prompt, temperature)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            text = response_text.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            raise GeminiError(
                f"Gemini response is not valid JSON: {response_text[:200]}..."
            )

    def is_circuit_open(self) -> bool:
        if self._circuit_open_since is None:
            return False
        elapsed = time.time() - self._circuit_open_since
        if elapsed > self._cb_reset_after:
            self._circuit_open_since = None
            self._failure_timestamps.clear()
            logger.info("Circuit breaker reset after %d seconds clean", self._cb_reset_after)
            return False
        return True

    def reset_circuit(self) -> None:
        self._circuit_open_since = None
        self._failure_timestamps.clear()
        logger.info("Circuit breaker manually reset")

    def _check_circuit(self) -> None:
        if self.is_circuit_open():
            remaining = self._cb_reset_after - (time.time() - self._circuit_open_since)
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open. Try again in {int(remaining)} seconds."
            )

    def _record_failure(self) -> None:
        now = time.time()
        self._failure_timestamps.append(now)
        cutoff = now - self._cb_window
        self._failure_timestamps = [t for t in self._failure_timestamps if t > cutoff]
        if len(self._failure_timestamps) >= self._cb_threshold:
            self._circuit_open_since = now
            logger.error(
                "Circuit breaker OPEN: %d failures in %d seconds",
                len(self._failure_timestamps), self._cb_window,
            )

    def _record_success(self) -> None:
        pass


def _safe_str(exc: Exception) -> str:
    msg = str(exc)
    return msg[:300]
