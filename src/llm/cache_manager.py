"""In-memory refinement result cache with 24-hour TTL.

Stores RefinementResult objects keyed by SHA256(festival_id + user_input).
Auto-evicts oldest entries when over max_entries.
No file I/O — purely in-memory for speed.
"""

import time
from dataclasses import dataclass, field


@dataclass
class RefinementResult:
    prompt: str
    negative_prompt: str
    suggested_props: list[str] = field(default_factory=list)
    suggested_background: str = ""
    raw_llm_response: str = ""
    was_cached: bool = False
    latency_ms: int = 0


@dataclass
class CacheEntry:
    result: RefinementResult
    created_at: float
    expires_at: float


class CacheManager:
    def __init__(self, ttl_seconds: int = 86400, max_entries: int = 1000):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._store: dict[str, CacheEntry] = {}

    def get(self, cache_key: str) -> RefinementResult | None:
        entry = self._store.get(cache_key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._store[cache_key]
            return None
        result = entry.result
        result.was_cached = True
        result.latency_ms = 0
        return result

    def set(self, cache_key: str, result: RefinementResult) -> None:
        now = time.time()
        entry = CacheEntry(
            result=result, created_at=now, expires_at=now + self._ttl
        )
        self._store[cache_key] = entry
        if len(self._store) > self._max_entries:
            self._evict_oldest()

    def clear_expired(self) -> int:
        now = time.time()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]
        return len(expired)

    def clear_all(self) -> None:
        self._store.clear()

    def _evict_oldest(self) -> None:
        sorted_keys = sorted(self._store.keys(), key=lambda k: self._store[k].created_at)
        for k in sorted_keys[: len(sorted_keys) - self._max_entries]:
            del self._store[k]

    def __len__(self) -> int:
        return len(self._store)
