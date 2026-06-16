"""Tests for history_manager.py"""

import json
import os
import tempfile
import pytest
from src.llm.history_manager import HistoryManager


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def history(temp_dir):
    return HistoryManager(temp_dir, max_records=10)


class TestHistoryManager:
    def test_empty_history(self, history):
        assert history.load_history() == []
        assert history.get_recent(5) == []

    def test_add_record(self, history):
        record = {
            "festival_id": "mid-autumn",
            "raw_input": "cat with mooncake",
            "refined_prompt": "dingdingcat holding a mooncake",
            "user_action": "approved",
        }
        record_id = history.add_record(record)
        assert record_id is not None

        records = history.load_history()
        assert len(records) == 1
        assert records[0]["festival_id"] == "mid-autumn"
        assert "id" in records[0]
        assert "timestamp" in records[0]
        assert records[0]["schema_version"] == 1

    def test_auto_id_and_timestamp(self, history):
        record = {"festival_id": "christmas"}
        record_id = history.add_record(record)
        records = history.load_history()
        assert records[0]["id"] is not None
        assert records[0]["timestamp"] is not None
        assert record_id == records[0]["id"]

    def test_get_recent(self, history):
        for i in range(8):
            history.add_record({
                "festival_id": f"festival-{i}",
                "raw_input": f"input {i}",
            })
        recent = history.get_recent(3)
        assert len(recent) == 3
        assert recent[-1]["raw_input"] == "input 7"
        assert recent[-2]["raw_input"] == "input 6"

    def test_max_records_pruning(self, history):
        for i in range(15):
            history.add_record({
                "festival_id": f"festival-{i}",
                "raw_input": f"input {i}",
            })
        records = history.load_history()
        assert len(records) == 10
        assert records[0]["raw_input"] == "input 5"

    def test_archive_on_overflow(self, history):
        for i in range(25):
            history.add_record({
                "festival_id": f"festival-{i}",
                "raw_input": f"input {i}",
            })
        records = history.load_history()
        assert len(records) == 10

    def test_atomic_write(self, history):
        history.add_record({"festival_id": "test", "raw_input": "hello"})
        records = history.load_history()
        assert len(records) == 1
        assert records[0]["raw_input"] == "hello"

    def test_update_record(self, history):
        record_id = history.add_record({
            "festival_id": "test",
            "raw_input": "original",
            "user_action": "approved",
        })
        updated = history.update_record(record_id, {"user_action": "edited", "user_edited_prompt": "changed"})
        assert updated is True

        records = history.load_history()
        assert records[0]["user_action"] == "edited"
        assert records[0]["user_edited_prompt"] == "changed"

    def test_update_nonexistent_record(self, history):
        updated = history.update_record("nonexistent-id", {"user_action": "edited"})
        assert updated is False

    def test_get_cache_key(self, history):
        key1 = history.get_cache_key("mid-autumn", "cat with mooncake")
        key2 = history.get_cache_key("mid-autumn", "cat with mooncake")
        key3 = history.get_cache_key("mid-autumn", "cat with lantern")
        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 64  # SHA256 hex digest

    def test_clear_history(self, history):
        history.add_record({"festival_id": "test"})
        history.clear_history()
        assert history.load_history() == []

    def test_corrupted_file_handled(self, temp_dir):
        file_path = os.path.join(temp_dir, "refinement_history.json")
        with open(file_path, "w") as f:
            f.write("not valid json {{")

        hm = HistoryManager(temp_dir)
        assert hm.load_history() == []
        hm.add_record({"festival_id": "test"})
        assert len(hm.load_history()) == 1

    def test_record_count(self, history):
        assert history.get_record_count() == 0
        history.add_record({"festival_id": "test"})
        assert history.get_record_count() == 1
        history.add_record({"festival_id": "test2"})
        assert history.get_record_count() == 2
