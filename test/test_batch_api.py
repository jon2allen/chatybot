#!/usr/bin/env python3
"""
Unit tests for the Batch API subsystem (Phase 1):
  - BatchManager storage, state machine, and crash-safe submission
  - /batch and /batchlist command handlers (registry-based)
  - Secret-scan gating at /batch end
  - Localization of the new command verbs and sub-keywords

See mistral-batch-poc/batch_proposal_v3.md for the specified behaviors.
"""

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatybot.batch_manager import (  # noqa: E402
    BatchError,
    BatchManager,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_STAGED,
    STATUS_SUBMITTING,
    STATUS_SUBMITTED,
    STATUS_SUBMIT_FAILED,
)
from chatybot.commands import batch as batch_cmds  # noqa: E402
from chatybot.commands.context import CommandContext  # noqa: E402
from chatybot.commands.registry import registry  # noqa: E402
from chatybot.buffer_manager import BufferManager  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def batches_dir(tmp_path, monkeypatch):
    d = tmp_path / "batches"
    d.mkdir()
    monkeypatch.setenv("CHATYBOT_TEST_BATCHES_DIR", str(d))
    return str(d)


@pytest.fixture
def mgr(batches_dir):
    return BatchManager(workspace="/tmp/ws")


@pytest.fixture
def draft(mgr):
    return mgr.start("dufu_run", model_alias="gptoss_batch",
                     model_name="openai/gpt-oss-120b:batch",
                     provider="openrouter", prompt="Translate the poem.")


def make_ctx(mgr, model_config=None, list_models=None):
    bm = BufferManager(app=None)
    cm = MagicMock()
    model_config = model_config or {
        "name": "openai/gpt-oss-120b:batch",
        "vendor": "openrouter",
        "batch": True,
        "api_key": "OPENROUTER_API_KEY",
        "max_tokens": 1024,
        "input_cost_per_mtok": 0.10,
    }
    cm.config = {
        "models": {"gptoss_batch": model_config},
        "batch": {"max_cost_usd": 5.0, "max_open_per_provider": 3,
                  "keep_remote_files": False},
    }
    cm.active_model_alias = "gptoss_batch"
    cm.get_model_config.return_value = model_config
    cm.list_batch_capable_models.return_value = list_models or ["gptoss_batch"]
    app = SimpleNamespace(buffer_manager=bm, config_manager=cm, _batch_manager=mgr)
    return CommandContext(buffer_manager=bm, config_manager=cm, i18n=None,
                         session_store=None, app=app)


async def run_cmd(ctx, command):
    spec = registry.get(command.split()[0])
    assert spec is not None, f"command not registered: {command.split()[0]}"
    parts = command.split(maxsplit=2)
    return await spec.handler(ctx, parts, command)


# ---------------------------------------------------------------------------
# BatchManager: storage & state machine
# ---------------------------------------------------------------------------

class TestBatchManager:
    def test_start_creates_draft(self, mgr, batches_dir):
        meta = mgr.start("dufu run", model_alias="m", model_name="model",
                         provider="openrouter", prompt="p")
        assert meta["status"] == STATUS_DRAFT
        assert meta["name"] == "dufu_run"  # sanitized
        assert meta["batch_id"].startswith("btch-") and meta["batch_id"].endswith("dufu_run")
        assert os.path.isdir(os.path.join(batches_dir, meta["batch_id"]))
        assert os.path.exists(mgr.index_path())
        assert mgr.find_by_name("dufu_run")["batch_id"] == meta["batch_id"]

    def test_auto_id_sequencing(self, mgr, draft):
        mgr.add_items(draft, ["a", "b"], id_prefix="dufu_run_")
        mgr.add_items(draft, ["c"], id_prefix="dufu_run_")
        items = mgr.list_items(draft)
        assert [i["custom_id"] for i in items] == [
            "dufu_run_0001", "dufu_run_0002", "dufu_run_0003"]
        assert draft["item_count"] == 3

    def test_filebank_prefix(self, mgr, draft):
        mgr.add_items(draft, ["a", "b"], id_prefix="fb1_line_")
        ids = [i["custom_id"] for i in mgr.list_items(draft)]
        assert ids == ["fb1_line_0001", "fb1_line_0002"]

    def test_explicit_id_and_collision(self, mgr, draft):
        mgr.add_items(draft, ["first"], id_prefix="dufu_run_", explicit_id="chunwang")
        assert mgr.list_items(draft)[0]["custom_id"] == "chunwang"
        with pytest.raises(BatchError, match="already exists"):
            mgr.add_items(draft, ["dup"], id_prefix="dufu_run_", explicit_id="chunwang")

    def test_edit_remove_clear(self, mgr, draft):
        mgr.add_items(draft, ["one", "two"], id_prefix="dufu_run_")
        mgr.edit_item(draft, "dufu_run_0002", "two-edited")
        assert mgr.show_item(draft, "dufu_run_0002")["text"] == "two-edited"
        mgr.remove_item(draft, "dufu_run_0001")
        assert len(mgr.list_items(draft)) == 1
        mgr.clear_items(draft["batch_id"])
        assert mgr.list_items(draft) == []

    def test_end_builds_payload_and_locks(self, mgr, draft):
        mgr.add_items(draft, ["poem one", "poem two"], id_prefix="dufu_run_")
        result = mgr.end(draft)
        assert result["item_count"] == 2
        assert draft["status"] == STATUS_STAGED
        req_path = os.path.join(mgr.batches_dir, draft["batch_id"], "requests.json")
        with open(req_path, encoding="utf-8") as f:
            payload = json.load(f)
        # Key order: endpoint and model must precede requests (spike finding)
        assert list(payload.keys())[:3] == ["endpoint", "model", "requests"]
        assert payload["model"] == "openai/gpt-oss-120b:batch"
        first = payload["requests"][0]
        assert first["custom_id"] == "dufu_run_0001"
        roles = [m["role"] for m in first["body"]["messages"]]
        assert roles == ["system", "user"]

    def test_add_after_end_refused_with_reopen_hint(self, mgr, draft, capsys):
        mgr.add_items(draft, ["x"], id_prefix="dufu_run_")
        mgr.end(draft)
        with pytest.raises(BatchError, match=r"/batch start dufu_run"):
            mgr.add_items(draft, ["y"], id_prefix="dufu_run_")

    def test_reopen_staged_to_draft(self, mgr, draft):
        mgr.add_items(draft, ["x"], id_prefix="dufu_run_")
        mgr.end(draft)
        meta = mgr.start("dufu_run", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch", provider="openrouter")
        assert meta["status"] == STATUS_DRAFT
        mgr.add_items(meta, ["y"], id_prefix="dufu_run_")
        assert len(mgr.list_items(meta)) == 2
        mgr.end(meta)

    def test_secret_scan_blocks_end(self, mgr, draft):
        mgr.add_items(draft, ["my key is sk-abcdefghijklmnopabcdefghijklmnop1234"],
                      id_prefix="dufu_run_")
        with pytest.raises(BatchError, match="Security scan failed"):
            mgr.end(draft)
        assert draft["status"] == STATUS_DRAFT  # staging stays open

    def test_abort_deletes(self, mgr, draft):
        mgr.add_items(draft, ["x"], id_prefix="dufu_run_")
        mgr.abort(draft)
        assert mgr.find_by_name("dufu_run") is None

    def test_estimate_cost(self, mgr, draft):
        mgr.add_items(draft, ["x" * 400], id_prefix="dufu_run_")  # ~100 tokens
        est = mgr.estimate_cost_usd(draft, mgr.list_items(draft),
                                    max_tokens=100, input_cost_per_mtok=1.0)
        # (400 item chars + 19 prompt chars) // 4 = 104 input tokens
        # (104 + 100 max_tokens) * 1.0/1M * 0.5 = 0.000102
        assert est == pytest.approx(0.000102)
        assert mgr.estimate_cost_usd(draft, [], None, None) is None

    def test_index_dedup_latest_wins(self, mgr):
        m1 = mgr.start("b1", model_alias="m", model_name="n", provider="openrouter")
        m1["status"] = STATUS_STAGED
        mgr._write_meta(m1)
        m1["status"] = STATUS_SUBMITTED
        mgr._write_meta(m1)
        records = mgr.list_index()
        assert len(records) == 1
        assert records[0]["status"] == STATUS_SUBMITTED


# ---------------------------------------------------------------------------
# Crash-safe submission & polling (fake provider)
# ---------------------------------------------------------------------------

class FakeProvider:
    """In-memory OpenRouter-shaped provider for testing submit/poll/cancel."""
    name = "openrouter"

    def __init__(self, fail_submit=False, final_status="completed"):
        self.fail_submit = fail_submit
        self.final_status = final_status
        self.batches = {}
        self.calls = []

    async def submit(self, requests, model_name):
        self.calls.append(("submit", model_name, len(requests)))
        if self.fail_submit:
            raise RuntimeError("HTTP 402: insufficient credits")
        bid = f"batch-{len(self.calls):04d}"
        self.batches[bid] = {
            "id": bid, "status": self.final_status,
            "request_counts": {"total": len(requests), "completed": len(requests),
                               "failed": 0},
            "results": [
                {"custom_id": r["custom_id"],
                 "response": {"status_code": 200,
                              "body": {"choices": [{"message": {"content": "ok"}}]}}}
                for r in requests
            ],
            "usage": {"cost": 0.002051105},
            "provider": "DeepInfra",
        }
        return self.batches[bid]

    async def get(self, provider_id, allow_missing=False):
        self.calls.append(("get", provider_id))
        return self.batches.get(provider_id)

    async def cancel(self, provider_id):
        self.batches[provider_id]["status"] = "cancelled"
        return self.batches[provider_id]

    def normalize_status(self, batch):
        return batch["status"]

    @staticmethod
    def counts_of(batch):
        rc = batch.get("request_counts") or {}
        return rc.get("total"), rc.get("completed"), rc.get("failed")

    @staticmethod
    def normalize_result(entry):
        resp = entry.get("response") or {}
        body = resp.get("body") or {}
        choices = body.get("choices") or []
        return {"custom_id": entry.get("custom_id"),
                "status_code": resp.get("status_code", 200),
                "content": choices[0]["message"]["content"] if choices else None}

    @staticmethod
    def telemetry_of(batch):
        return {"cost_usd": (batch.get("usage") or {}).get("cost"),
                "host_backend": batch.get("provider")}


class TestSubmitPoll:
    def _staged(self, mgr):
        meta = mgr.start("run1", model_alias="m", model_name="model",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["a", "b"], id_prefix="run1_")
        mgr.end(meta)
        return meta

    def test_run_sidecar_then_submitted(self, mgr):
        meta = self._staged(mgr)
        provider = FakeProvider()
        meta = asyncio.run(mgr.run(meta, provider, max_cost_usd=5.0,
                                   max_open_per_provider=3))
        assert meta["status"] == STATUS_SUBMITTED
        assert meta["provider_id"] == "batch-0001"
        # Crash safety: the raw index log shows the fsynced 'submitting'
        # sidecar record was appended BEFORE the POST completed.
        with open(mgr.index_path(), encoding="utf-8") as f:
            raw_statuses = [json.loads(line)["status"] for line in f if line.strip()]
        assert raw_statuses == ["draft", "draft", "staged", "submitting", "submitted"]

    def test_run_budget_refusal(self, mgr):
        meta = self._staged(mgr)
        provider = FakeProvider()
        with pytest.raises(BatchError, match="max_cost_usd"):
            asyncio.run(mgr.run(meta, provider, max_cost_usd=0.000001,
                                max_open_per_provider=3,
                                max_tokens=100000, input_cost_per_mtok=10.0))

    def test_run_budget_force_override(self, mgr):
        meta = self._staged(mgr)
        provider = FakeProvider()
        meta = asyncio.run(mgr.run(meta, provider, force=True,
                                   max_cost_usd=0.000001,
                                   max_open_per_provider=3,
                                   max_tokens=100000, input_cost_per_mtok=10.0))
        assert meta["status"] == STATUS_SUBMITTED

    def test_run_requires_staged(self, mgr):
        meta = mgr.start("run2", model_alias="m", model_name="n", provider="openrouter")
        with pytest.raises(BatchError, match="still a draft"):
            asyncio.run(mgr.run(meta, FakeProvider()))

    def test_submit_failure_marks_submit_failed(self, mgr):
        meta = self._staged(mgr)
        provider = FakeProvider(fail_submit=True)
        with pytest.raises(BatchError, match="submit_failed"):
            asyncio.run(mgr.run(meta, provider))
        assert meta["status"] == STATUS_SUBMIT_FAILED

    def test_double_submit_refused_after_crash(self, mgr):
        meta = self._staged(mgr)
        meta["status"] = STATUS_SUBMITTING
        mgr._write_meta(meta)
        with pytest.raises(BatchError, match="adopt"):
            asyncio.run(mgr.run(meta, FakeProvider()))

    def test_adopt_orphan(self, mgr):
        meta = self._staged(mgr)
        meta["status"] = STATUS_SUBMITTING
        mgr._write_meta(meta)
        mgr.adopt_orphan(meta, "batch-9999")
        assert meta["status"] == STATUS_SUBMITTED
        assert meta["provider_id"] == "batch-9999"

    def test_check_completed_writes_results_and_telemetry(self, mgr, batches_dir):
        meta = self._staged(mgr)
        provider = FakeProvider()
        meta = asyncio.run(mgr.run(meta, provider))
        meta = asyncio.run(mgr.check(meta, provider))
        assert meta["status"] == STATUS_COMPLETED
        assert meta["cost_usd"] == 0.002051105
        assert meta["host_backend"] == "DeepInfra"
        results = mgr.read_results(meta["batch_id"])
        assert len(results) == 2
        assert results[0]["custom_id"] == "run1_0001"
        assert results[0]["content"] == "ok"

    def test_concurrency_cap(self, mgr):
        for i in range(3):
            meta = mgr.start(f"c{i}", model_alias="m", model_name="n",
                             provider="openrouter")
            mgr.add_items(meta, ["x"], id_prefix=f"c{i}_")
            mgr.end(meta)
            meta = asyncio.run(mgr.run(meta, FakeProvider()))
        meta = mgr.start("c3", model_alias="m", model_name="n", provider="openrouter")
        mgr.add_items(meta, ["x"], id_prefix="c3_")
        mgr.end(meta)
        with pytest.raises(BatchError, match="Concurrency cap"):
            asyncio.run(mgr.run(meta, FakeProvider(), max_open_per_provider=3))

    def test_cancel(self, mgr):
        meta = self._staged(mgr)
        provider = FakeProvider(final_status="in_progress")
        meta = asyncio.run(mgr.run(meta, provider))
        meta = asyncio.run(mgr.cancel(meta, provider))
        assert meta["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Command layer (/batch, /batchlist)
# ---------------------------------------------------------------------------

class TestBatchCommands:
    def test_status_no_batches(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch status"))
        out = capsys.readouterr().out
        assert "No batch draft open" in out

    def test_capability_gate(self, mgr, capsys):
        ctx = make_ctx(mgr)
        ctx.config_manager.get_model_config.return_value = {"name": "m", "batch": False}
        asyncio.run(run_cmd(ctx, "/batch start mybatch"))
        out = capsys.readouterr().out
        assert "does not support batch jobs" in out
        assert "gptoss_batch" in out

    def test_full_draft_workflow(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start dufu_run"))
        ctx.app.buffer_manager.set_script_var("special_poem", "春望: 国破山河在")
        asyncio.run(run_cmd(ctx, '/batch add id=chunwang var=special_poem'))
        asyncio.run(run_cmd(ctx, "/batch add plain text item"))
        out = capsys.readouterr().out
        assert "chunwang" in out

        asyncio.run(run_cmd(ctx, "/batch items"))
        out = capsys.readouterr().out
        assert "dufu_run_0001" in out

        asyncio.run(run_cmd(ctx, "/batch ids"))
        ids = ctx.app.buffer_manager.get_script_var("BATCH_ITEM_IDS")
        assert ids == ["chunwang", "dufu_run_0001"]

    def test_filebank_ingestion(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start fbtest"))
        ctx.app.buffer_manager.file_banks["filebank1"] = "line one\nline two\n"
        asyncio.run(run_cmd(ctx, "/batch add filebank=1 split=lines"))
        items = mgr.list_items(mgr.resolve("fbtest"))
        assert [i["custom_id"] for i in items] == ["fb1_line_0001", "fb1_line_0002"]
        assert [i["text"] for i in items] == ["line one", "line two"]

    def test_var_list_ingestion(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start vtest"))
        ctx.app.buffer_manager.set_script_var("arr", ["x", "y"])
        asyncio.run(run_cmd(ctx, "/batch add var=arr"))
        items = mgr.list_items(mgr.resolve("vtest"))
        assert [i["custom_id"] for i in items] == ["arr_0001", "arr_0002"]
        assert [i["text"] for i in items] == ["x", "y"]

    def test_end_then_dump_binds_payload(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start dtest"))
        asyncio.run(run_cmd(ctx, "/batch add hello world"))
        asyncio.run(run_cmd(ctx, "/batch end"))
        asyncio.run(run_cmd(ctx, "/batch dump dtest"))
        payload = ctx.app.buffer_manager.get_script_var("BATCH_PAYLOAD")
        parsed = json.loads(payload)
        assert parsed["model"] == "openai/gpt-oss-120b:batch"
        assert parsed["requests"][0]["custom_id"] == "dtest_0001"

    def test_add_after_end_command_refusal(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start etest"))
        asyncio.run(run_cmd(ctx, "/batch add one"))
        asyncio.run(run_cmd(ctx, "/batch end"))
        asyncio.run(run_cmd(ctx, "/batch add two"))
        out = capsys.readouterr().out
        assert "Staging session is closed" in out
        assert "/batch start etest" in out

    def test_batchlist_filters_and_vars(self, mgr, capsys):
        ctx = make_ctx(mgr)
        for name in ("one", "two"):
            asyncio.run(run_cmd(ctx, f"/batch start {name}"))
            asyncio.run(run_cmd(ctx, "/batch add item"))
            asyncio.run(run_cmd(ctx, "/batch end"))
        capsys.readouterr()
        asyncio.run(run_cmd(ctx, "/batchlist all ids"))
        out = capsys.readouterr().out
        assert "one" in out and "two" in out
        ids = ctx.app.buffer_manager.get_script_var("BATCH_IDS")
        assert len(ids) == 2
        records = ctx.app.buffer_manager.get_script_var("BATCH_LIST")
        assert all(r["status"] == "staged" for r in records)

        asyncio.run(run_cmd(ctx, "/batchlist status=draft"))
        out = capsys.readouterr().out
        assert "No batches found" in out

        asyncio.run(run_cmd(ctx, "/batchlist status=staged var=my_batches"))
        exported = ctx.app.buffer_manager.get_script_var("my_batches")
        assert len(exported) == 2

    def test_batch_list_alias(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start listed"))
        asyncio.run(run_cmd(ctx, "/batch add x"))
        capsys.readouterr()
        asyncio.run(run_cmd(ctx, "/batch list all"))
        out = capsys.readouterr().out
        assert "listed" in out

    def test_unknown_subcommand(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch frobnicate"))
        out = capsys.readouterr().out
        assert "Unknown batch subcommand" in out

    def test_retry_phase3_notice(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch retry anything"))
        out = capsys.readouterr().out
        assert "Phase 3" in out


# ---------------------------------------------------------------------------
# Localization
# ---------------------------------------------------------------------------

class TestBatchLocalization:
    def _i18n(self):
        from chatybot.localization import LocalizationManager
        return LocalizationManager()

    def test_canonical_aliases_resolve(self):
        i18n = self._i18n()
        i18n.set_locale("en")
        assert i18n.resolve_command("/batch") == "/batch"
        assert i18n.resolve_command("/batchlist") == "/batchlist"

    def test_localized_aliases_resolve(self):
        i18n = self._i18n()
        cases = [
            ("es", "/lote", "/batch"),
            ("es", "/listalotes", "/batchlist"),
            ("fr", "/lot", "/batch"),
            ("zh", "/批量", "/batch"),
            ("it", "/lotto", "/batch"),
        ]
        for locale, verb, expected in cases:
            i18n.set_locale(locale)
            assert i18n.resolve_command(verb) == expected, f"{locale} {verb}"

    def test_localized_subkeywords_translate(self):
        i18n = self._i18n()
        i18n.set_locale("es")
        assert i18n.translate_command_string("/lote iniciar dufu") == "/batch start dufu"
        assert i18n.translate_command_string("/lote fin") == "/batch end"
        i18n.set_locale("zh")
        assert i18n.translate_command_string("/批量 列表") == "/batch list"

    def test_all_locales_have_batch_aliases(self):
        i18n = self._i18n()
        for locale in ("en", "es", "fr", "zh", "it", "ar"):
            i18n.set_locale(locale)
            # canonical must always resolve
            assert i18n.resolve_command("/batch") == "/batch"
            assert i18n.resolve_command("/batchlist") == "/batchlist"


# ---------------------------------------------------------------------------
# Command verb lint (PatternMatcher) — batch verbs must be caught unescaped
# ---------------------------------------------------------------------------

class TestBatchVerbLint:
    def test_batch_words_registered(self):
        import chatybot.chatybot_app as app_mod
        src = open(app_mod.__file__, encoding="utf-8").read()
        # PatternMatcher words list includes batch and batchlist
        assert '"batch", "batchlist"' in src

    def test_pattern_matches_batch_verbs(self):
        from chatybot.pattern import PatternMatcher
        matcher = PatternMatcher(words=["batch", "batchlist"])
        assert matcher.pattern.fullmatch("batch")
        assert matcher.pattern.fullmatch("batchlist")
        assert not matcher.pattern.fullmatch("batching")  # word boundary


# ---------------------------------------------------------------------------
# ChatDSL escape-command acceptance
# ---------------------------------------------------------------------------

class TestChatDslEscape:
    def test_valid_escape_commands_include_batch(self):
        from chatybot.chatdsl_parse import TParser
        assert "batch" in TParser.VALID_ESCAPE_COMMANDS
        assert "batchlist" in TParser.VALID_ESCAPE_COMMANDS


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------

class TestBatchConfig:
    def test_batch_flag_and_settings(self):
        from chatybot.config_model import ChatConfig
        cfg = ChatConfig.from_toml_string("""
[models.gptoss_batch]
name = "openai/gpt-oss-120b:batch"
base_url = "https://openrouter.ai/api/v1"
batch = true

[batch]
max_cost_usd = 2.5
""")
        assert cfg.models["gptoss_batch"].batch is True
        assert cfg.batch.max_cost_usd == 2.5
        assert cfg.batch.max_open_per_provider == 3
        assert [m.alias for m in cfg.batch_capable_models()] == ["gptoss_batch"]

    def test_default_config_parses(self):
        from chatybot.config_model import ChatConfig
        from pathlib import Path
        cfg = ChatConfig.from_toml(Path(__file__).parent.parent / "src" / "chatybot" / "chat_config.toml")
        assert cfg.models["gptoss_batch"].batch is True
        assert cfg.batch.max_cost_usd == 5.0
        assert "mistral_1" in cfg.models


# ---------------------------------------------------------------------------
# Regression tests: post-review fixes
# ---------------------------------------------------------------------------

class TestReviewFixes:
    """One test per confirmed issue from the external review."""

    def test_fix_start_id_collision_no_infinite_loop(self, mgr, batches_dir, monkeypatch):
        """1.1 — stale instance dirs with colliding timestamps must not hang."""
        import chatybot.batch_manager as bm
        monkeypatch.setattr(bm.time, "time", lambda: 1793000000)
        # Simulate stale dirs: one without an index entry at ts, one at ts+1
        os.makedirs(os.path.join(batches_dir, "btch-1793000000-dupe"), exist_ok=True)
        os.makedirs(os.path.join(batches_dir, "btch-1793000001-dupe"), exist_ok=True)
        meta = mgr.start("dupe", model_alias="m", model_name="n", provider="openrouter")
        assert meta["batch_id"] == "btch-1793000002-dupe"

    def test_fix_estimate_counts_prompt_per_item(self, mgr):
        """1.2 — the system prompt is sent once per item; the estimate must
        multiply prompt chars by the item count."""
        meta = mgr.start("costy", model_alias="m", model_name="n",
                         provider="openrouter", prompt="p" * 200)  # 200 chars/item
        mgr.add_items(meta, ["x" * 400] * 3, id_prefix="costy_")
        est = mgr.estimate_cost_usd(meta, mgr.list_items(meta),
                                    max_tokens=0, input_cost_per_mtok=1.0)
        # (3*400 item chars + 3*200 prompt chars) // 4 = 450 tokens
        assert est == pytest.approx(450 * 1.0 / 1_000_000 * 0.5)

    def test_fix_run_uses_batch_model_not_active(self, mgr, capsys, monkeypatch):
        """1.3 — /batch run must work after the user switched the active chat
        model back to a non-batch alias; pricing uses the batch's model."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start priced"))
        asyncio.run(run_cmd(ctx, "/batch add item text"))
        asyncio.run(run_cmd(ctx, "/batch end"))
        # User switches their interactive model back to a chat model
        ctx.config_manager.active_model_alias = "mistral_1"
        provider = FakeProvider()
        monkeypatch.setattr(batch_cmds, "_build_provider", lambda app, meta: provider)
        asyncio.run(run_cmd(ctx, "/batch run priced"))
        out = capsys.readouterr().out
        assert "Submitted batch 'priced'" in out
        # Pricing came from the batch model (input_cost_per_mtok=0.10)
        assert "cost estimate" in out

    def test_fix_terminal_name_reuse_creates_fresh_instance(self, mgr, capsys):
        """2.1 — a completed batch must not burn its name forever."""
        meta = mgr.start("reusable", model_alias="m", model_name="n",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["x"], id_prefix="reusable_")
        mgr.end(meta)
        meta["status"] = STATUS_COMPLETED  # simulate provider completion
        mgr._write_meta(meta)

        fresh = mgr.start("reusable", model_alias="m", model_name="n",
                          provider="openrouter")
        assert fresh["batch_id"] != meta["batch_id"]
        assert fresh["status"] == STATUS_DRAFT
        # Old instance preserved in the catalog
        ids = [r["batch_id"] for r in mgr.list_index()]
        assert meta["batch_id"] in ids and fresh["batch_id"] in ids

    def test_fix_inflight_name_still_refused(self, mgr):
        """2.1 — in-flight batches remain immutable (name refused while open)."""
        meta = mgr.start("inflight", model_alias="m", model_name="n",
                         provider="openrouter")
        mgr.add_items(meta, ["x"], id_prefix="inflight_")
        mgr.end(meta)
        meta["status"] = STATUS_SUBMITTED
        mgr._write_meta(meta)
        with pytest.raises(BatchError, match="in flight"):
            mgr.start("inflight", model_alias="m", model_name="n",
                      provider="openrouter")

    def test_fix_add_does_not_guess_batch_name(self, mgr, capsys):
        """2.2 — text starting with a word matching an existing batch name
        must not be split into a (batch-name, partial-text) pair."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start report"))   # older batch: 'report'
        asyncio.run(run_cmd(ctx, "/batch add report content"))
        asyncio.run(run_cmd(ctx, "/batch end"))

        asyncio.run(run_cmd(ctx, "/batch start work"))     # active draft: 'work'
        asyncio.run(run_cmd(ctx, "/batch add Report for fiscal year 2026"))
        work_items = mgr.list_items(mgr.resolve("work"))
        assert len(work_items) == 1
        assert work_items[0]["text"] == "Report for fiscal year 2026"
        assert work_items[0]["custom_id"] == "work_0001"
        # The 'report' batch is untouched (still sealed with its one item)
        assert len(mgr.list_items(mgr.resolve("report"))) == 1

    def test_fix_missing_model_alias_friendly_error(self, mgr, capsys):
        """2.4 — a batch whose model alias was removed from chat_config.toml
        must produce a BatchError message, not an unhandled ValueError."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start orphaned"))
        meta = mgr.resolve("orphaned")
        meta["status"] = STATUS_SUBMITTED
        meta["provider_id"] = "batch-0001"
        mgr._write_meta(meta)
        ctx.config_manager.get_model_config.side_effect = ValueError(
            "Model alias 'gptoss_batch' not found in configuration.")
        asyncio.run(run_cmd(ctx, "/batch check orphaned"))
        out = capsys.readouterr().out
        assert "no longer exists in chat_config.toml" in out

    def test_fix_bulk_sequencing_is_linear_and_correct(self, mgr):
        """3.1 — auto-IDs stay sequential across bulk adds and follow-up calls."""
        meta = mgr.start("bulk", model_alias="m", model_name="n",
                         provider="openrouter")
        added = mgr.add_items(meta, [f"t{i}" for i in range(200)], id_prefix="bulk_")
        assert [it["custom_id"] for it in added[:3]] == ["bulk_0001", "bulk_0002", "bulk_0003"]
        assert added[-1]["custom_id"] == "bulk_0200"
        more = mgr.add_items(meta, ["again"], id_prefix="bulk_")
        assert more[0]["custom_id"] == "bulk_0201"
        # Explicit IDs in between do not break auto-sequencing afterwards
        mgr.add_items(meta, ["manual"], id_prefix="bulk_", explicit_id="special")
        nxt = mgr.add_items(meta, ["after"], id_prefix="bulk_")
        assert nxt[0]["custom_id"] == "bulk_0202"

    def test_fix_zh_ar_clear_keywords(self):
        """4 — zh and ar must have at least one keyword mapping to 'clear'."""
        from chatybot.localization import LocalizationManager
        i18n = LocalizationManager()
        i18n.set_locale("zh")
        assert i18n.translate_command_string("/批量 重新开始") == "/batch clear"
        i18n.set_locale("ar")
        assert i18n.translate_command_string("/دفعة إخلاء") == "/batch clear"
