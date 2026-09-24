"""Tests for the skills database system.

Tests cover:
  - CorpusManager.patch_metadata
  - skillsdb: create, list, get, search, enable/disable, delete, trigger matching
  - skillsdb: default skill seeding
  - skillsdb: export/import SKILL.md
"""

import json
import os
import tempfile
import shutil

import pytest

# We need to redirect the skills DB path before importing skillsdb
# so it uses a temp directory instead of ~/.local/share/chatybot/

_TEMP_DIR = tempfile.mkdtemp(prefix="chatybot_skills_test_")

# Patch the path before import
os.environ["CHATYBOT_TEST_SKILLS_DIR"] = _TEMP_DIR

from chatybot.tinydb1.corpus_manager import CorpusManager
from chatybot import skillsdb

# Override the SKILLS_DB_PATH to use temp dir
skillsdb.SKILLS_DB_PATH = os.path.join(_TEMP_DIR, "skills.json")


@pytest.fixture(autouse=True)
def reset_skillsdb():
    """Reset the skills DB state before each test."""
    # Reset global state
    skillsdb._skills_manager = None
    skillsdb._skills_cache = None
    # Remove the test DB file if it exists
    if os.path.exists(skillsdb.SKILLS_DB_PATH):
        os.unlink(skillsdb.SKILLS_DB_PATH)
    yield
    # Cleanup after test
    if skillsdb._skills_manager is not None:
        try:
            skillsdb._skills_manager.close()
        except Exception:
            pass
    skillsdb._skills_manager = None
    skillsdb._skills_cache = None
    if os.path.exists(skillsdb.SKILLS_DB_PATH):
        os.unlink(skillsdb.SKILLS_DB_PATH)


# ── CorpusManager.patch_metadata tests ──────────────────────────


class TestPatchMetadata:
    def test_patch_single_key(self):
        db_path = os.path.join(_TEMP_DIR, "test_patch.json")
        try:
            manager = CorpusManager(db_path)
            doc_id = manager.add_item("test", "item1", "content", {"a": 1, "b": 2})
            assert manager.patch_metadata(doc_id, "c", 3) is True
            item = manager.get_item(doc_id)
            assert item["metadata"]["a"] == 1
            assert item["metadata"]["b"] == 2
            assert item["metadata"]["c"] == 3
            manager.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_patch_existing_key(self):
        db_path = os.path.join(_TEMP_DIR, "test_patch2.json")
        try:
            manager = CorpusManager(db_path)
            doc_id = manager.add_item("test", "item1", "content", {"enabled": True})
            assert manager.patch_metadata(doc_id, "enabled", False) is True
            item = manager.get_item(doc_id)
            assert item["metadata"]["enabled"] is False
            manager.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_patch_nonexistent_item(self):
        db_path = os.path.join(_TEMP_DIR, "test_patch3.json")
        try:
            manager = CorpusManager(db_path)
            assert manager.patch_metadata(99999, "key", "val") is False
            manager.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


# ── skillsdb tests ───────────────────────────────────────────────


class TestSkillsdbCreate:
    def test_create_skill_basic(self):
        doc_id = skillsdb.create_skill(
            name="test-skill",
            content="Test content",
            description="A test skill",
            triggers=["test trigger"],
            tags=["test"],
        )
        assert doc_id > 0
        skill = skillsdb.get_skill_by_name("test-skill")
        assert skill is not None
        assert skill["name"] == "test-skill"
        assert skill["content"] == "Test content"
        assert skill["metadata"]["description"] == "A test skill"
        assert skill["metadata"]["triggers"] == ["test trigger"]
        assert skill["metadata"]["enabled"] is True
        assert skill["metadata"]["source"] == "manual"

    def test_create_skill_with_tool_config(self):
        tc = {"mode": "on", "enable_tools": ["read_file"], "auto_loop": True, "max_turns": 10}
        doc_id = skillsdb.create_skill(
            name="agentic-skill",
            content="Agentic content",
            tool_config=tc,
        )
        skill = skillsdb.get_skill_by_name("agentic-skill")
        assert skill["metadata"]["tool_config"] == tc

    def test_create_skill_without_tool_config(self):
        skillsdb.create_skill(name="guidance-skill", content="Guidance")
        skill = skillsdb.get_skill_by_name("guidance-skill")
        assert "tool_config" not in skill["metadata"]


class TestSkillsdbList:
    def test_list_all_skills(self):
        skillsdb.create_skill(name="skill-a", content="A")
        skillsdb.create_skill(name="skill-b", content="B")
        skills = skillsdb.list_skills()
        assert len(skills) >= 2

    def test_list_enabled_only(self):
        skillsdb.create_skill(name="enabled-one", content="E")
        doc_id = skillsdb.create_skill(name="disabled-one", content="D")
        skillsdb.patch_skill_metadata(doc_id, "enabled", False)
        enabled = skillsdb.list_skills(enabled_only=True)
        names = [s["name"] for s in enabled]
        assert "enabled-one" in names
        assert "disabled-one" not in names


class TestSkillsdbTriggerMatching:
    def test_trigger_match(self):
        skillsdb.create_skill(
            name="my-review",
            content="Review code",
            triggers=["my review trigger"],
        )
        matched = skillsdb.get_matching_skills("please my review trigger now")
        names = [s["name"] for s in matched]
        assert "my-review" in names

    def test_no_trigger_match(self):
        skillsdb.create_skill(
            name="no-match",
            content="No match",
            triggers=["zzz no match zzz"],
        )
        matched = skillsdb.get_matching_skills("write a poem about cats")
        names = [s["name"] for s in matched]
        assert "no-match" not in names

    def test_disabled_skill_not_matched(self):
        doc_id = skillsdb.create_skill(
            name="disabled-skill",
            content="Review",
            triggers=["zzz disabled trigger zzz"],
        )
        skillsdb.patch_skill_metadata(doc_id, "enabled", False)
        matched = skillsdb.get_matching_skills("zzz disabled trigger zzz")
        names = [s["name"] for s in matched]
        assert "disabled-skill" not in names

    def test_case_insensitive_match(self):
        skillsdb.create_skill(
            name="ci-skill",
            content="Test",
            triggers=["ZZZ Case Test ZZZ"],
        )
        matched = skillsdb.get_matching_skills("please zzz case test zzz now")
        names = [s["name"] for s in matched]
        assert "ci-skill" in names


class TestSkillsdbEnableDisable:
    def test_enable_skill(self):
        doc_id = skillsdb.create_skill(name="toggle", content="T")
        skillsdb.patch_skill_metadata(doc_id, "enabled", False)
        skill = skillsdb.get_skill_by_name("toggle")
        assert skill["metadata"]["enabled"] is False

        skillsdb.patch_skill_metadata(doc_id, "enabled", True)
        skill = skillsdb.get_skill_by_name("toggle")
        assert skill["metadata"]["enabled"] is True

    def test_disabled_not_in_cache(self):
        doc_id = skillsdb.create_skill(
            name="cached",
            content="C",
            triggers=["test cached"],
        )
        skillsdb.patch_skill_metadata(doc_id, "enabled", False)
        enabled = skillsdb._get_enabled_skills()
        names = [s["name"] for s in enabled]
        assert "cached" not in names


class TestSkillsdbGlobEnableDisable:
    """Test /skill enable and disable with glob patterns, 'all', and exact names."""

    def test_enable_all(self):
        # Disable all defaults first
        for skill in skillsdb.list_skills():
            skillsdb.patch_skill_metadata(
                getattr(skill, "doc_id", skill.get("doc_id")), "enabled", False
            )
        # Create a test skill (will be disabled by the above loop)
        skillsdb.create_skill(name="glob-test-1", content="T")
        skillsdb.create_skill(name="glob-test-2", content="T")

        # Enable all via glob
        from chatybot.commands.skills import _enable_disable_skill
        result = _enable_disable_skill("all", enable=True)
        assert result.action.value == "handled"

        enabled = skillsdb.list_skills(enabled_only=True)
        names = [s["name"] for s in enabled]
        assert "glob-test-1" in names
        assert "glob-test-2" in names

    def test_disable_glob_pattern(self):
        skillsdb.create_skill(name="glob-a", content="A")
        skillsdb.create_skill(name="glob-b", content="B")
        skillsdb.create_skill(name="other", content="O")

        from chatybot.commands.skills import _enable_disable_skill
        _enable_disable_skill("glob-*", enable=False)

        enabled = skillsdb.list_skills(enabled_only=True)
        names = [s["name"] for s in enabled]
        assert "glob-a" not in names
        assert "glob-b" not in names
        assert "other" in names

    def test_enable_exact_name_fallback(self):
        skillsdb.create_skill(name="exact-name", content="E")
        # Disable it first
        skill = skillsdb.get_skill_by_name("exact-name")
        skillsdb.patch_skill_metadata(
            getattr(skill, "doc_id", skill.get("doc_id")), "enabled", False
        )

        from chatybot.commands.skills import _enable_disable_skill
        _enable_disable_skill("exact-name", enable=True)

        skill = skillsdb.get_skill_by_name("exact-name")
        assert skill["metadata"]["enabled"] is True

    def test_no_match_returns_ok(self):
        from chatybot.commands.skills import _enable_disable_skill
        result = _enable_disable_skill("zzz-no-match-zzz", enable=True)
        assert result.action.value == "handled"


class TestSkillsdbDelete:
    def test_delete_skill(self):
        doc_id = skillsdb.create_skill(name="deletable", content="D")
        assert skillsdb.delete_skill(doc_id) is True
        assert skillsdb.get_skill_by_name("deletable") is None

    def test_delete_nonexistent(self):
        assert skillsdb.delete_skill(99999) is False

    def test_delete_nonexistent_no_exception(self):
        """delete_skill on a non-existent ID should return False, not raise."""
        # This tests the fix for Issue 1: TinyDB raises KeyError on
        # non-existent doc_id if contains() guard is missing.
        result = skillsdb.delete_skill(88888)
        assert result is False


class TestSkillsdbSearch:
    def test_search_by_name(self):
        skillsdb.create_skill(name="python-helper", content="Python", description="Helps with Python")
        results = skillsdb.search_skills("python")
        assert any(r["name"] == "python-helper" for r in results)

    def test_search_by_content(self):
        skillsdb.create_skill(name="searcher", content="find bugs in code", description="")
        results = skillsdb.search_skills("bugs")
        assert any(r["name"] == "searcher" for r in results)

    def test_search_by_tags(self):
        skillsdb.create_skill(name="tagged", content="T", tags=["security", "audit"])
        results = skillsdb.search_skills("security")
        assert any(r["name"] == "tagged" for r in results)


class TestSkillsdbExportImport:
    def test_export_import_roundtrip(self):
        skillsdb.create_skill(
            name="exportable",
            content="Export me",
            description="Test export",
            triggers=["export test"],
            tags=["test"],
        )
        export_path = os.path.join(_TEMP_DIR, "exported.md")
        assert skillsdb.export_skill_to_skillmd("exportable", export_path) is True
        assert os.path.exists(export_path)

        # Import as a new skill
        doc_id = skillsdb.import_skill_from_skillmd(export_path)
        assert doc_id is not None
        skill = skillsdb.get_skill_by_name("exportable")
        assert skill is not None
        assert skill["content"] == "Export me"

    def test_import_nonexistent_file(self):
        assert skillsdb.import_skill_from_skillmd("/nonexistent/path.md") is None


class TestDefaultSkills:
    def test_default_skills_seeded(self):
        """When the DB is first created, default skills should be seeded."""
        # Force lazy init — this should create the DB and seed defaults
        manager = skillsdb._ensure_manager()
        skills = skillsdb.list_skills()
        skill_names = [s["name"] for s in skills]
        assert "code-review" in skill_names
        assert "debug-error" in skill_names
        assert "write-test" in skill_names
        assert "research-agent" in skill_names
        assert "compare-models" in skill_names
        assert "batch-translate" in skill_names
        assert "db-research-log" in skill_names

    def test_default_skill_has_tool_config(self):
        skillsdb._ensure_manager()
        skill = skillsdb.get_skill_by_name("code-review")
        assert skill is not None
        tc = skill["metadata"].get("tool_config")
        assert tc is not None
        assert tc["mode"] == "on"
        assert "read_file" in tc["enable_tools"]
        assert "write_file" in tc["disable_tools"]
        assert tc["auto_loop"] is True

    def test_default_skill_without_tool_config(self):
        skillsdb._ensure_manager()
        skill = skillsdb.get_skill_by_name("compare-models")
        assert skill is not None
        assert "tool_config" not in skill.get("metadata", {})

    def test_default_skill_triggers(self):
        skillsdb._ensure_manager()
        matched = skillsdb.get_matching_skills("can you review code in this file?")
        assert any(s["name"] == "code-review" for s in matched)


# ── Cleanup ──────────────────────────────────────────────────────


def teardown_module():
    """Clean up temp directory after all tests."""
    shutil.rmtree(_TEMP_DIR, ignore_errors=True)
