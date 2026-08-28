"""
test_session_store_pluggable.py - Unit tests for pluggable session storage architecture.
Tests BaseSessionStore, JsonlSessionStore, MonolithicJsonSessionStore, and factory.
"""

import os
import json
import pytest
import tempfile
import gzip
import time
from chatybot.session_factory import get_session_store, register_session_engine
from chatybot.session_store_jsonl import JsonlSessionStore
from chatybot.session_store_monolithic import MonolithicJsonSessionStore
from chatybot.session_interface import BaseSessionStore


@pytest.fixture
def temp_sessions_dir():
    d = tempfile.mkdtemp()
    yield d


def test_factory_creation(temp_sessions_dir):
    jsonl_store = get_session_store("jsonl", temp_sessions_dir)
    assert isinstance(jsonl_store, JsonlSessionStore)

    mono_store = get_session_store("monolithic", temp_sessions_dir)
    assert isinstance(mono_store, MonolithicJsonSessionStore)

    json_store = get_session_store("json", temp_sessions_dir)
    assert isinstance(json_store, MonolithicJsonSessionStore)

    with pytest.raises(ValueError):
        get_session_store("invalid_engine", temp_sessions_dir)


@pytest.mark.parametrize("engine_name", ["jsonl", "monolithic"])
def test_session_lifecycle(engine_name, temp_sessions_dir):
    store = get_session_store(engine_name, temp_sessions_dir)

    # 1. Create session
    meta = store.create_session(
        session_id="test_sess_001",
        model_alias="test_model",
        custom_name="My Session",
        initial_prompt="Hello world",
        notes="Initial note",
    )
    assert meta["session_id"] == "test_sess_001"

    # 2. Append turns
    store.append_turn("test_sess_001", {"turn_id": 1, "prompt": "Hello", "response": "Hi there!"})
    store.append_turn(
        "test_sess_001",
        {"turn_id": 2, "prompt": "Calculate 2+2", "response": "4", "thinking": "Math logic"},
    )

    # 3. Resolve session
    assert store.resolve_session("My Session") == "test_sess_001"
    assert store.resolve_session("test_sess_001") == "test_sess_001"

    # 4. Load session
    loaded_meta, loaded_turns = store.load_session("test_sess_001")
    assert loaded_meta["custom_name"] == "My Session"
    assert len(loaded_turns) == 2
    assert loaded_turns[0]["prompt"] == "Hello"
    assert loaded_turns[1]["thinking"] == "Math logic"

    # 5. List sessions
    sessions_list = store.list_sessions()
    assert len(sessions_list) == 1
    assert sessions_list[0]["sid"] == "test_sess_001"
    assert sessions_list[0]["cname"] == "My Session"
    assert sessions_list[0]["turns_cnt"] == 2

    # 6. Replace turns
    store.replace_turns("test_sess_001", [
        {"turn_id": 1, "prompt": "Brand New Turn", "response": "Brand New Response"}
    ])
    reloaded_meta, reloaded_turns = store.load_session("test_sess_001")
    assert len(reloaded_turns) == 1
    assert reloaded_turns[0]["prompt"] == "Brand New Turn"
    assert reloaded_meta["turn_count"] == 1

    # 7. Save metadata update
    reloaded_meta["notes"] = "Updated note"
    store.save_meta("test_sess_001", reloaded_meta)
    reloaded_meta_2, _ = store.load_session("test_sess_001")
    assert reloaded_meta_2["notes"] == "Updated note"

    # 8. Merge sessions & collision check
    store.create_session("test_sess_002", "model2", custom_name="Second")
    store.append_turn("test_sess_002", {"turn_id": 1, "prompt": "Turn from 2", "response": "Resp 2"})
    merged_id = store.merge_sessions("Merged Target", ["test_sess_001", "test_sess_002"])
    merged_meta, merged_turns = store.load_session(merged_id)
    assert merged_meta["custom_name"] == "Merged Target"
    assert len(merged_turns) == 2

    # Second merge in same second should not collide
    merged_id_2 = store.merge_sessions("Merged Target 2", ["test_sess_001", "test_sess_002"])
    assert merged_id_2 != merged_id

    # 9. Compress sessions
    comp_cnt, saved_bytes = store.compress_sessions()
    assert comp_cnt >= 1

    # Verify compressed_filter listing
    compressed_sessions = store.list_sessions(compressed_filter=True)
    assert len(compressed_sessions) >= 1
    assert all(s["compressed"] for s in compressed_sessions)

    uncompressed_sessions = store.list_sessions(compressed_filter=False)
    assert all(not s["compressed"] for s in uncompressed_sessions)

    # 10. Load compressed session (verifies auto-decompression)
    c_meta, c_turns = store.load_session("test_sess_001")
    assert len(c_turns) == 1

    # 11. Uncompress with glob wildcard
    uncomp_glob = store.uncompress_sessions("test_sess*")
    assert uncomp_glob >= 1

    # Uncompress all remaining
    uncomp_cnt = store.uncompress_sessions("all")
    assert uncomp_cnt >= 0
    all_uncompressed = store.list_sessions(compressed_filter=True)
    assert len(all_uncompressed) == 0

    # 12. Metrics
    metrics = store.get_workspace_metrics()
    assert metrics["total_count"] >= 2
    assert metrics["total_bytes"] > 0

    # 13. Advisory lock & stale lock test
    lock_ok = store.acquire_lock("test_sess_001")
    assert lock_ok is True
    store.release_lock("test_sess_001")

    # 14. Prune sessions
    pruned = store.prune_sessions(keep_n=1)
    assert pruned >= 1

    # 15. Delete all
    del_cnt = store.delete_all_sessions()
    assert len(store.list_sessions()) == 0


def test_corrupted_jsonl_lines_handled(temp_sessions_dir):
    store = JsonlSessionStore(temp_sessions_dir)
    store.create_session("corrupt_sess", "model")
    turns_path = store._turns_path("corrupt_sess")
    with open(turns_path, "w", encoding="utf-8") as f:
        f.write('{"turn_id": 1, "prompt": "valid", "response": "ok"}\n')
        f.write('GARBAGE NON-JSON LINE\n')
        f.write('{"turn_id": 2, "prompt": "valid 2", "response": "ok 2"}\n')

    meta, turns = store.load_session("corrupt_sess")
    assert len(turns) == 2


def test_custom_session_engine(temp_sessions_dir):
    class CustomDummyStore(BaseSessionStore):
        def create_session(self, *args, **kwargs):
            return {"dummy": True}

        def append_turn(self, *args, **kwargs):
            pass

        def replace_turns(self, *args, **kwargs):
            pass

        def save_meta(self, *args, **kwargs):
            pass

        def load_session(self, *args, **kwargs):
            return {}, []

        def resolve_session(self, *args, **kwargs):
            return "dummy"

        def list_sessions(self, *args, **kwargs):
            return []

        def delete_session(self, *args, **kwargs):
            return True

        def delete_all_sessions(self, *args, **kwargs):
            return 0

        def merge_sessions(self, *args, **kwargs):
            return "dummy_merged"

        def compress_sessions(self, *args, **kwargs):
            return 0, 0

        def uncompress_sessions(self, *args, **kwargs):
            return 0

        def prune_sessions(self, *args, **kwargs):
            return 0

        def get_workspace_metrics(self, *args, **kwargs):
            return {}

        def acquire_lock(self, *args, **kwargs):
            return True

        def release_lock(self, *args, **kwargs):
            pass

    register_session_engine("custom_dummy", CustomDummyStore)
    custom_instance = get_session_store("custom_dummy", temp_sessions_dir)
    assert isinstance(custom_instance, CustomDummyStore)
    assert custom_instance.create_session("sid", "model") == {"dummy": True}
