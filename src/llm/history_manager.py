"""Atomic JSON history read/write with auto-pruning.

Stores refinement records at {app_config_dir}/refinement_history.json.
Capped at max_records. Overflow archived to .archive.json.
All writes are atomic (temp file + os.replace) to prevent corruption.
"""

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path


class HistoryManager:
    def __init__(self, app_config_dir: str, max_records: int = 200):
        os.makedirs(app_config_dir, exist_ok=True)
        self._file_path = os.path.join(app_config_dir, "refinement_history.json")
        self._archive_path = os.path.join(app_config_dir, "refinement_history.archive.json")
        self._max_records = max_records

    def load_history(self) -> list[dict]:
        if not os.path.exists(self._file_path):
            return []
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            return data
        except (json.JSONDecodeError, OSError):
            return []

    def get_recent(self, count: int = 5) -> list[dict]:
        records = self.load_history()
        return records[-count:]

    def add_record(self, record: dict) -> str:
        record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("timestamp", _iso_now())
        record.setdefault("schema_version", 1)

        records = self.load_history()
        records.append(record)

        if len(records) > self._max_records:
            overflow = records[: len(records) - self._max_records]
            records = records[-self._max_records :]
            self._append_archive(overflow)

        self._atomic_write(records)
        return record["id"]

    def update_record(self, record_id: str, updates: dict) -> bool:
        records = self.load_history()
        for i, rec in enumerate(records):
            if rec.get("id") == record_id:
                records[i].update(updates)
                self._atomic_write(records)
                return True
        return False

    def _atomic_write(self, data: list[dict]) -> None:
        dirname = os.path.dirname(self._file_path)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json", prefix=".refinement_history_", dir=dirname
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _append_archive(self, records: list[dict]) -> None:
        existing = []
        if os.path.exists(self._archive_path):
            try:
                with open(self._archive_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing = []
        existing.extend(records)
        with open(self._archive_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def get_cache_key(self, festival_id: str, raw_input: str) -> str:
        payload = f"{festival_id}:{raw_input.strip().lower()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get_record_count(self) -> int:
        return len(self.load_history())

    def clear_history(self) -> None:
        self._atomic_write([])


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
