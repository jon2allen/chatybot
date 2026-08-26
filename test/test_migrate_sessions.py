"""
test_migrate_sessions.py - Unit tests for the standalone session migration utility.
Tests dry-run, live conversion, gzip support, error resilience, and non-destructive archival.
"""

import os
import json
import gzip
import pytest
import tempfile
from chatybot.migrate_sessions import find_legacy_sessions, convert_single_session, run_migration


@pytest.fixture
def migration_env():
    sessions_dir = tempfile.mkdtemp()
    backup_dir = tempfile.mkdtemp()

    # Create 3 legacy sessions: 2 plain .json, 1 .json.gz
    s1 = {
        "session_id": "legacy_sess_1",
        "model_alias": "mistral_1",
        "created_at": "2026-08-20T10:00:00",
        "updated_at": "2026-08-20T10:05:00",
        "first_prompt_slug": "test_prompt_one",
        "custom_name": "Old Session 1",
        "notes": "Note 1",
        "turns": [
            {"turn_id": 1, "prompt": "Hello 1", "response": "World 1"},
            {"turn_id": 2, "prompt": "Hello 2", "response": "World 2", "thinking": "Think trace"},
        ],
    }
    with open(os.path.join(sessions_dir, "legacy_sess_1.json"), "w", encoding="utf-8") as f:
        json.dump(s1, f)

    s2 = {
        "session_id": "legacy_sess_2",
        "model_alias": "cohere_north",
        "created_at": "2026-08-21T11:00:00",
        "updated_at": "2026-08-21T11:15:00",
        "first_prompt_slug": "test_prompt_two",
        "custom_name": None,
        "notes": None,
        "turns": [{"turn_id": 1, "prompt": "Alpha", "response": "Beta"}],
    }
    with open(os.path.join(sessions_dir, "legacy_sess_2.json"), "w", encoding="utf-8") as f:
        json.dump(s2, f)

    s3_gz = {
        "session_id": "legacy_sess_3",
        "model_alias": "gemma_4",
        "created_at": "2026-08-22T12:00:00",
        "updated_at": "2026-08-22T12:30:00",
        "first_prompt_slug": "compressed_prompt",
        "custom_name": "Gz Session",
        "notes": "Gz Note",
        "turns": [{"turn_id": 1, "prompt": "Gz prompt", "response": "Gz response"}],
    }
    with gzip.open(os.path.join(sessions_dir, "legacy_sess_3.json.gz"), "wt", encoding="utf-8") as f:
        json.dump(s3_gz, f)

    yield sessions_dir, backup_dir


def test_find_legacy_sessions(migration_env):
    sessions_dir, _ = migration_env
    found = find_legacy_sessions(sessions_dir)
    assert len(found) == 3


def test_dry_run_migration(migration_env):
    sessions_dir, backup_dir = migration_env

    migrated, errors = run_migration(sessions_dir, backup_dir, dry_run=True)
    assert migrated == 3
    assert errors == 0

    # Verify no files were moved or created
    found_after = find_legacy_sessions(sessions_dir)
    assert len(found_after) == 3
    assert not os.path.exists(os.path.join(sessions_dir, "legacy_sess_1"))


def test_live_migration(migration_env):
    sessions_dir, backup_dir = migration_env

    migrated, errors = run_migration(sessions_dir, backup_dir, dry_run=False)
    assert migrated == 3
    assert errors == 0

    # 1. Check legacy files removed from sessions_dir
    assert len(find_legacy_sessions(sessions_dir)) == 0

    # 2. Check backups created
    assert os.path.exists(os.path.join(backup_dir, "legacy_sess_1.json"))
    assert os.path.exists(os.path.join(backup_dir, "legacy_sess_2.json"))
    assert os.path.exists(os.path.join(backup_dir, "legacy_sess_3.json.gz"))

    # 3. Check JSONL directories
    s1_dir = os.path.join(sessions_dir, "legacy_sess_1")
    assert os.path.isdir(s1_dir)
    assert os.path.exists(os.path.join(s1_dir, "meta.json"))
    assert os.path.exists(os.path.join(s1_dir, "turns.jsonl"))

    with open(os.path.join(s1_dir, "meta.json"), "r", encoding="utf-8") as f:
        meta = json.load(f)
        assert meta["session_id"] == "legacy_sess_1"
        assert meta["turn_count"] == 2
        assert meta["custom_name"] == "Old Session 1"

    with open(os.path.join(s1_dir, "turns.jsonl"), "r", encoding="utf-8") as f:
        turns = [json.loads(line) for line in f if line.strip()]
        assert len(turns) == 2
        assert turns[0]["prompt"] == "Hello 1"
        assert turns[1]["thinking"] == "Think trace"

    # 4. Check compressed session preserved
    s3_dir = os.path.join(sessions_dir, "legacy_sess_3")
    assert os.path.isdir(s3_dir)
    assert os.path.exists(os.path.join(s3_dir, "turns.jsonl.gz"))


def test_migration_corrupted_file(migration_env):
    sessions_dir, backup_dir = migration_env

    # Add a corrupted JSON file
    corrupt_path = os.path.join(sessions_dir, "corrupt_session.json")
    with open(corrupt_path, "w") as f:
        f.write("{ invalid json")

    migrated, errors = run_migration(sessions_dir, backup_dir, dry_run=False)
    assert migrated == 3
    assert errors == 1
