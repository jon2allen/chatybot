"""Tests for skill tools: search_skills and call_skill.

Tests cover:
  - search_skills: keyword matching, compact metadata (no content), limit
  - call_skill: full content retrieval, name normalization, not-found, disabled
  - call_skill: tool_config silent application and tool_state summary
  - call_skill: recursion tracking (cycle detection, depth limit, accumulation)
  - call_skill: snapshot preservation across multiple delegations
"""

import os
import tempfile

import pytest

# Redirect the skills DB path before importing skillsdb
_TEMP_DIR = tempfile.mkdtemp(prefix="chatybot_skill_tools_test_")
os.environ["CHATYBOT_TEST_SKILLS_DIR"] = _TEMP_DIR

from chatybot import skillsdb
from chatybot.tools.skill_utils import call_skill, search_skills

# Override the SKILLS_DB_PATH to use temp dir
skillsdb.SKILLS_DB_PATH = os.path.join(_TEMP_DIR, "skills.json")


@pytest.fixture(autouse=True)
def reset_skillsdb():
    """Reset the skills DB state before each test."""
    skillsdb._skills_manager = None
    skillsdb._skills_cache = None
    if os.path.exists(skillsdb.SKILLS_DB_PATH):
        os.unlink(skillsdb.SKILLS_DB_PATH)
    yield
    if skillsdb._skills_manager is not None:
        try:
            skillsdb._skills_manager.close()
        except Exception:
            pass
    skillsdb._skills_manager = None
    skillsdb._skills_cache = None
    if os.path.exists(skillsdb.SKILLS_DB_PATH):
        os.unlink(skillsdb.SKILLS_DB_PATH)


# ── search_skills tests ─────────────────────────────────────────


class TestSearchSkills:
    def test_search_returns_metadata_without_content(self):
        skillsdb.create_skill(
            name="test-interview",
            content="Detailed secret instructions for interview...",
            description="Interview assistant",
            triggers=["test interview"],
            tags=["interview", "test"],
        )

        res = search_skills("interview")
        assert res["status"] == "success"
        assert res["count"] >= 1
        matched = next(s for s in res["skills"] if s["name"] == "test-interview")
        assert matched["description"] == "Interview assistant"
        assert "content" not in matched  # Zero context pollution!

    def test_search_empty_query_returns_all(self):
        skillsdb.create_skill(
            name="skill-a",
            content="A content",
            description="Skill A",
            triggers=["skill alpha"],
        )
        skillsdb.create_skill(
            name="skill-b",
            content="B content",
            description="Skill B",
            triggers=["skill beta"],
        )

        res = search_skills("")
        assert res["status"] == "success"
        # Default skills may be seeded; verify our two are included
        names = [s["name"] for s in res["skills"]]
        assert "skill-a" in names
        assert "skill-b" in names
        assert res["count"] >= 2

    def test_search_limit(self):
        for i in range(5):
            skillsdb.create_skill(
                name=f"limit-test-{i}",
                content=f"content {i}",
                description="limit test",
                triggers=[f"limit test {i}"],
                tags=["limit-test"],
            )

        res = search_skills("limit-test", limit=2)
        assert res["status"] == "success"
        assert res["count"] == 2
        assert res["total_matched"] == 5

    def test_search_no_matches(self):
        skillsdb.create_skill(
            name="real-skill",
            content="content",
            description="real",
            triggers=["real trigger"],
        )

        res = search_skills("nonexistent-query-xyz")
        assert res["status"] == "success"
        assert res["count"] == 0


# ── call_skill tests ─────────────────────────────────────────────


class TestCallSkill:
    def test_call_returns_full_content(self):
        skillsdb.create_skill(
            name="test-interview",
            content="Detailed secret instructions for interview...",
            description="Interview assistant",
            triggers=["test interview"],
            tags=["interview", "test"],
        )

        res = call_skill("test-interview")
        assert res["status"] == "success"
        assert res["skill"]["content"] == "Detailed secret instructions for interview..."
        assert res["skill"]["name"] == "test-interview"

    def test_call_name_normalization(self):
        skillsdb.create_skill(
            name="test-interview",
            content="content",
            description="Interview assistant",
            triggers=["test interview"],
        )

        # Underscore -> hyphen normalization, case-insensitive
        res = call_skill("TEST_INTERVIEW")
        assert res["status"] == "success"
        assert res["skill"]["name"] == "test-interview"

    def test_call_not_found(self):
        res = call_skill("nonexistent-skill")
        assert res["status"] == "error"
        assert "search_skills" in res["reason"]

    def test_call_disabled_skill(self):
        doc_id = skillsdb.create_skill(
            name="disabled-skill",
            content="content",
            description="disabled",
            triggers=["disabled trigger"],
        )
        skillsdb.patch_skill_metadata(doc_id, "enabled", False)

        res = call_skill("disabled-skill")
        assert res["status"] == "error"
        assert "disabled" in res["reason"]


# ── call_skill with app (tool_config, recursion) ────────────────


class _FakeApp:
    """Minimal app stub for testing tool_config and recursion tracking."""

    def __init__(self):
        self.tool_mode = False
        self.tool_auto = False
        self.max_turns = 25
        self.tool_overrides: dict[str, bool] = {}
        self.tool_context = ""
        self._turn_skills_loaded: list[str] = []
        self._tool_state_snapshot = None
        self.buffer_manager = _FakeBufferManager()

    def _save_tool_state_snapshot(self) -> None:
        self._tool_state_snapshot = {
            "tool_mode": self.tool_mode,
            "tool_overrides": dict(self.tool_overrides),
            "tool_auto": self.tool_auto,
            "max_turns": self.max_turns,
        }

    def generate_tool_context(self) -> str:
        self.tool_context = "fake_tool_context"
        return self.tool_context


class _FakeBufferManager:
    def set_script_var(self, name, value):
        pass


class TestCallSkillToolConfig:
    def test_tool_config_applied_silently(self):
        skillsdb.create_skill(
            name="test-agentic",
            content="Use read_file to inspect code.",
            description="Agentic test skill",
            triggers=["test agentic"],
            tool_config={
                "mode": "on",
                "enable_tools": ["read_file", "grep_search"],
                "disable_tools": ["write_file"],
                "auto_loop": True,
                "max_turns": 15,
            },
        )

        app = _FakeApp()
        res = call_skill("test-agentic", app=app)
        assert res["status"] == "success"
        assert "tool_state" in res
        assert res["tool_state"]["changed"] is True
        assert "enabled: read_file, grep_search" in res["tool_state"]["changes"]
        assert "disabled: write_file" in res["tool_state"]["changes"]
        assert app.tool_overrides.get("read_file") is True
        assert app.tool_overrides.get("write_file") is False
        assert app.max_turns == 15
        assert app.tool_auto is True
        assert app.tool_mode is True

    def test_depth_returned_with_app(self):
        skillsdb.create_skill(
            name="depth-test",
            content="content",
            description="depth",
            triggers=["depth trigger"],
        )
        app = _FakeApp()
        res = call_skill("depth-test", app=app)
        assert res["status"] == "success"
        assert res["depth"] == 1


class TestCallSkillRecursion:
    def test_cycle_detection(self):
        app = _FakeApp()
        app._turn_skills_loaded = ["skill-a"]

        skillsdb.create_skill(
            name="skill-a",
            content="Call skill-a again (circular)",
            description="Circular skill",
            triggers=["circular test"],
        )

        res = call_skill("skill-a", app=app)
        assert res["status"] == "error"
        assert "Circular skill delegation detected" in res["reason"]
        assert "skill-a -> skill-a" in res["reason"]

    def test_depth_limit(self):
        app = _FakeApp()
        app._turn_skills_loaded = ["a", "b", "c", "d", "e"]  # At the limit

        skillsdb.create_skill(
            name="skill-f",
            content="Too deep",
            description="Depth test",
            triggers=["depth test"],
        )

        res = call_skill("skill-f", app=app)
        assert res["status"] == "error"
        assert "Maximum skill delegations per tool loop" in res["reason"]
        assert "5" in res["reason"]

    def test_accumulates_across_turns(self):
        app = _FakeApp()
        app._turn_skills_loaded = []

        skillsdb.create_skill(
            name="skill-x",
            content="Test X",
            description="Test",
            triggers=["test x"],
        )
        skillsdb.create_skill(
            name="skill-y",
            content="Test Y",
            description="Test",
            triggers=["test y"],
        )

        # First call
        res1 = call_skill("skill-x", app=app)
        assert res1["status"] == "success"
        assert app._turn_skills_loaded == ["skill-x"]

        # Second call (different skill, should succeed)
        res2 = call_skill("skill-y", app=app)
        assert res2["status"] == "success"
        assert app._turn_skills_loaded == ["skill-x", "skill-y"]

        # Third call (circular -- skill-x already loaded)
        res3 = call_skill("skill-x", app=app)
        assert res3["status"] == "error"
        assert "Circular" in res3["reason"]


class TestCallSkillSnapshot:
    def test_snapshot_not_overwritten(self):
        skillsdb.create_skill(
            name="skill-config-a",
            content="Skill A",
            description="Config A",
            triggers=["config a"],
            tool_config={"mode": "on", "enable_tools": ["read_file"], "disable_tools": ["write_file"]},
        )
        skillsdb.create_skill(
            name="skill-config-b",
            content="Skill B",
            description="Config B",
            triggers=["config b"],
            tool_config={"mode": "on", "enable_tools": ["grep_search"], "disable_tools": ["run_command"]},
        )

        app = _FakeApp()
        app._turn_skills_loaded = []
        app._tool_state_snapshot = None

        # First delegation saves snapshot
        call_skill("skill-config-a", app=app)
        snapshot_after_a = app._tool_state_snapshot
        assert snapshot_after_a is not None

        # Second delegation should NOT overwrite the snapshot
        call_skill("skill-config-b", app=app)
        assert app._tool_state_snapshot is snapshot_after_a  # Same object, not replaced
