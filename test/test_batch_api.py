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
    supports_cancel = True  # unlike the real OpenRouter backend

    def __init__(self, fail_submit=False, final_status="completed",
                 empty_custom_ids=None):
        self.fail_submit = fail_submit
        self.final_status = final_status
        # Items whose completion body is empty (status 200, no content) —
        # mirroring the real-world gpt-oss/OpenRouter behavior.
        self.empty_custom_ids = set(empty_custom_ids or ())
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
                 **({"response": {"status_code": 200,
                                  "body": {"choices": [{"message": {"content": ""}}]}}}
                    if r["custom_id"] in self.empty_custom_ids else
                    {"response": {"status_code": 200,
                                  "body": {"choices": [{"message": {"content": "ok"}}]}}})}
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


class TestResultsInspection:
    """Native result inspection: /batch show with completions and /batch results."""

    def _completed_batch(self, mgr, name, n=2):
        """Stage, submit, and complete a batch through the fake provider."""
        meta = mgr.start(name, model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="Translate.")
        mgr.add_items(meta, [f"poem {i}" for i in range(n)], id_prefix=f"{name}_")
        mgr.end(meta)
        provider = FakeProvider()
        meta = asyncio.run(mgr.run(meta, provider))
        meta = asyncio.run(mgr.check(meta, provider))
        assert meta["status"] == STATUS_COMPLETED
        return meta, provider

    def test_show_displays_result_under_input(self, mgr, capsys):
        meta, _ = self._completed_batch(mgr, "shown")
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch show shown_0001 shown"))
        out = capsys.readouterr().out
        assert "[Input]:" in out
        assert "poem 0" in out
        assert "[Result]:" in out
        assert "ok" in out           # FakeProvider completion content
        assert "Status: 200" in out  # header line carries the result status

    def test_show_before_retrieval(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start fresh"))
        asyncio.run(run_cmd(ctx, "/batch add nothing yet"))
        asyncio.run(run_cmd(ctx, "/batch show fresh_0001 fresh"))
        out = capsys.readouterr().out
        assert "[Input]:" in out
        assert "No results yet" in out

    def test_show_error_record(self, mgr, capsys):
        meta, _ = self._completed_batch(mgr, "errb", n=1)
        # Overwrite the stored result with an error-shaped record
        records = mgr.read_results(meta["batch_id"])
        records[0] = {"custom_id": records[0]["custom_id"],
                      "status_code": 500, "content": None,
                      "error": "HTTP 500 upstream failure"}
        mgr._fsync_write(
            os.path.join(mgr.batches_dir, meta["batch_id"], "results.jsonl"),
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch show errb_0001 errb"))
        out = capsys.readouterr().out
        assert "[Error]:" in out
        assert "HTTP 500 upstream failure" in out

    def test_results_command_pagination_and_vars(self, mgr, capsys):
        self._completed_batch(mgr, "listed", n=3)
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch results listed limit=2"))
        out = capsys.readouterr().out
        assert "showing 2 of 3 records" in out
        assert "listed_0001" in out and "listed_0003" not in out
        records = ctx.app.buffer_manager.get_script_var("BATCH_RESULTS")
        assert len(records) == 3  # full list bound, pagination is display-only

        asyncio.run(run_cmd(ctx, "/batch results listed range=2: var=my_res"))
        out = capsys.readouterr().out
        assert "listed_0003" in out
        assert len(ctx.app.buffer_manager.get_script_var("my_res")) == 3

    def test_results_before_retrieval(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start waiting"))
        asyncio.run(run_cmd(ctx, "/batch add x"))
        asyncio.run(run_cmd(ctx, "/batch results waiting"))
        out = capsys.readouterr().out
        assert "No results retrieved yet" in out
        assert "/batch check waiting" in out

    def test_results_localized_subcommand(self):
        from chatybot.localization import LocalizationManager
        i18n = LocalizationManager()
        i18n.set_locale("es")
        assert i18n.translate_command_string(
            "/lote resultados mibatch limit=5") == "/batch results mibatch limit=5"


class TestShowResolutionFix:
    """Regression: /batch show must work without a batch name, including on
    completed batches (previously fell back to resolve(None), which only
    considers non-terminal batches and failed with 'No batch specified')."""

    def _completed_batch(self, mgr, name, n=1):
        meta = mgr.start(name, model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="Translate.")
        mgr.add_items(meta, [f"poem {i}" for i in range(n)], id_prefix=f"{name}_")
        mgr.end(meta)
        provider = FakeProvider()
        meta = asyncio.run(mgr.run(meta, provider))
        meta = asyncio.run(mgr.check(meta, provider))
        return meta

    def test_show_item_without_name_on_completed_batch(self, mgr, capsys):
        """The reported failure: '/batch show df1_0001' on a completed batch."""
        self._completed_batch(mgr, "df1")
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch show df1_0001"))
        out = capsys.readouterr().out
        assert "[Input]:" in out
        assert "[Result]:" in out
        assert "Error" not in out

    def test_show_batch_name_only_gives_overview(self, mgr, capsys):
        """The reported failure: '/batch show df1' (name only) must show the
        batch overview instead of erroring."""
        self._completed_batch(mgr, "df1", n=2)
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch show df1"))
        out = capsys.readouterr().out
        assert "Batch: df1" in out
        assert "Staged item IDs: df1_0001, df1_0002" in out
        assert "/batch show <item-id>" in out

    def test_show_unknown_item_clear_error(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch show no_such_item"))
        out = capsys.readouterr().out
        assert "item 'no_such_item' not found in any batch" in out
        assert "No batch specified" not in out

    def test_show_still_accepts_explicit_name(self, mgr, capsys):
        self._completed_batch(mgr, "named")
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch show named_0001 named"))
        out = capsys.readouterr().out
        assert "[Input]:" in out and "[Result]:" in out

    def test_edit_without_name_on_active_draft(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start ed1"))
        asyncio.run(run_cmd(ctx, "/batch add original text"))
        asyncio.run(run_cmd(ctx, "/batch edit ed1_0001 replacement text"))
        item = mgr.show_item(mgr.resolve("ed1"), "ed1_0001")
        assert item["text"] == "replacement text"

    def test_remove_without_name_on_active_draft(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start rm1"))
        asyncio.run(run_cmd(ctx, "/batch add doomed"))
        asyncio.run(run_cmd(ctx, "/batch remove rm1_0001"))
        assert mgr.list_items(mgr.resolve("rm1")) == []

    def test_edit_consumes_explicit_name_token(self, mgr, capsys):
        """When a token resolves the batch explicitly, it must not leak into
        the replacement text."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start ed2"))
        asyncio.run(run_cmd(ctx, "/batch add original"))
        asyncio.run(run_cmd(ctx, "/batch edit ed2_0001 ed2 the new text"))
        item = mgr.show_item(mgr.resolve("ed2"), "ed2_0001")
        assert item["text"] == "the new text"

    def test_edit_locked_item_reports_lock(self, mgr, capsys):
        """Edit on a staged (locked) item found by ID reports the lock."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start lk1"))
        asyncio.run(run_cmd(ctx, "/batch add sealed"))
        asyncio.run(run_cmd(ctx, "/batch end"))
        asyncio.run(run_cmd(ctx, "/batch edit lk1_0001 nope"))
        out = capsys.readouterr().out
        assert "only be edited while the batch is in draft" in out


# ---------------------------------------------------------------------------
# Batch Clone (Option 1)
# ---------------------------------------------------------------------------

class TestBatchClone:
    def test_manager_clone_copies_items_and_metadata(self, mgr):
        meta = mgr.start("src1", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="Original prompt")
        mgr.add_items(meta, ["item one", "item two"], id_prefix="src1_")
        mgr.end(meta)

        cloned = mgr.clone("src1", "dst1")
        assert cloned["name"] == "dst1"
        assert cloned["status"] == STATUS_DRAFT
        assert cloned["prompt"] == "Original prompt"
        assert cloned["model_alias"] == "gptoss_batch"
        assert cloned["item_count"] == 2

        items = mgr.list_items(cloned)
        assert len(items) == 2
        assert items[0]["text"] == "item one"
        assert items[1]["text"] == "item two"

    def test_manager_clone_prompt_and_model_override(self, mgr):
        meta = mgr.start("src2", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="Old prompt")
        mgr.add_items(meta, ["poem"], id_prefix="src2_")
        mgr.end(meta)

        cloned = mgr.clone(
            "src2", "dst2",
            prompt="New custom prompt",
            model_alias="custom_batch",
            model_name="openai/custom:batch",
            provider="openrouter",
        )
        assert cloned["name"] == "dst2"
        assert cloned["prompt"] == "New custom prompt"
        assert cloned["model_alias"] == "custom_batch"
        assert cloned["model"] == "openai/custom:batch"
        assert cloned["status"] == STATUS_DRAFT

    def test_clone_command_workflow_edit_remove_add(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start orig_run"))
        asyncio.run(run_cmd(ctx, "/batch add line 1"))
        asyncio.run(run_cmd(ctx, "/batch add line 2"))
        asyncio.run(run_cmd(ctx, "/batch end"))

        # Clone into a new batch with prompt override
        asyncio.run(run_cmd(ctx, '/batch clone orig_run copy_run prompt="Refined translation"'))
        out = capsys.readouterr().out
        assert "Cloned batch 'orig_run' -> 'copy_run'" in out
        assert "Refined translation" in out

        # Edit, remove, and add on the cloned draft
        asyncio.run(run_cmd(ctx, "/batch edit orig_run_0001 line 1 modified"))
        asyncio.run(run_cmd(ctx, "/batch remove orig_run_0002"))
        asyncio.run(run_cmd(ctx, "/batch add line 3 appended"))

        # Seal the cloned batch
        asyncio.run(run_cmd(ctx, "/batch end"))
        out = capsys.readouterr().out
        assert "Sealed batch 'copy_run': 2 items scanned" in out

        copy_meta = mgr.resolve("copy_run")
        items = mgr.list_items(copy_meta)
        assert len(items) == 2
        assert items[0]["text"] == "line 1 modified"
        assert items[1]["text"] == "line 3 appended"

        # Ensure original batch was untouched
        orig_meta = mgr.resolve("orig_run")
        orig_items = mgr.list_items(orig_meta)
        assert len(orig_items) == 2
        assert orig_items[0]["text"] == "line 1"
        assert orig_items[1]["text"] == "line 2"

    def test_clone_missing_args(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch clone"))
        out = capsys.readouterr().out
        assert "Usage: /batch clone" in out

    def test_clone_localization(self):
        from chatybot.localization import LocalizationManager
        i18n = LocalizationManager()
        i18n.set_locale("es")
        assert i18n.translate_command_string("/lote clonar b1 b2") == "/batch clone b1 b2"
        assert i18n.translate_command_string("/lote duplicar b1 b2") == "/batch clone b1 b2"
        i18n.set_locale("fr")
        assert i18n.translate_command_string("/lot cloner b1 b2") == "/batch clone b1 b2"
        i18n.set_locale("zh")
        assert i18n.translate_command_string("/批量 克隆 b1 b2") == "/batch clone b1 b2"
        i18n.set_locale("it")
        assert i18n.translate_command_string("/lotto clona b1 b2") == "/batch clone b1 b2"
        i18n.set_locale("ar")
        assert i18n.translate_command_string("/دفعة استنساخ b1 b2") == "/batch clone b1 b2"



class TestCloneGuards:
    """Regression: cloning must not silently destroy an existing draft."""

    def _source(self, mgr, name="srcb"):
        meta = mgr.start(name, model_alias="m", model_name="n",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["cloned item"], id_prefix=f"{name}_")
        mgr.end(meta)
        return meta

    def test_clone_into_existing_draft_refused_then_forced(self, mgr, capsys):
        self._source(mgr)
        existing = mgr.start("taken", model_alias="m", model_name="n",
                             provider="openrouter", prompt="keep")
        mgr.add_items(existing, ["PRECIOUS EXISTING ITEM"], id_prefix="taken_")

        with pytest.raises(BatchError, match="would be overwritten"):
            mgr.clone("srcb", "taken")
        # Refusal left the existing draft intact
        assert mgr.list_items(mgr.find_by_name("taken"))[0]["text"] == \
            "PRECIOUS EXISTING ITEM"

        mgr.clone("srcb", "taken", force=True)
        assert [it["text"] for it in mgr.list_items(mgr.find_by_name("taken"))] \
            == ["cloned item"]

    def test_clone_command_refusal_and_force(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start orig"))
        asyncio.run(run_cmd(ctx, "/batch add payload"))
        asyncio.run(run_cmd(ctx, "/batch end"))
        asyncio.run(run_cmd(ctx, "/batch start victim"))
        asyncio.run(run_cmd(ctx, "/batch add must survive"))
        capsys.readouterr()

        asyncio.run(run_cmd(ctx, "/batch clone orig victim"))
        out = capsys.readouterr().out
        assert "would be overwritten" in out
        items = mgr.list_items(mgr.find_by_name("victim"))
        assert [it["text"] for it in items] == ["must survive"]

        asyncio.run(run_cmd(ctx, "/batch clone orig victim force=true"))
        out = capsys.readouterr().out
        assert "Cloned batch 'orig' -> 'victim'" in out
        items = mgr.list_items(mgr.find_by_name("victim"))
        assert [it["text"] for it in items] == ["payload"]

    def test_clone_same_name_unseals_only_with_force(self, mgr):
        """'/batch clone src src' must not silently un-seal the source."""
        self._source(mgr, "sealme")
        with pytest.raises(BatchError, match="would be overwritten"):
            mgr.clone("sealme", "sealme")
        assert mgr.find_by_name("sealme")["status"] == "staged"
        cloned = mgr.clone("sealme", "sealme", force=True)
        assert cloned["status"] == STATUS_DRAFT

    def test_add_text_with_model_and_prompt_tokens_stays_intact(self, mgr, capsys):
        """/batch add must not swallow model=/prompt= tokens as options."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start t1"))
        asyncio.run(run_cmd(ctx, "/batch add compare model=gpt-4 prompt=hello world"))
        item = mgr.list_items(mgr.resolve("t1"))[0]
        assert item["text"] == "compare model=gpt-4 prompt=hello world"


class TestBatchRawPayloadTrace:
    """Tests for raw-payload tracing in batch provider network calls."""

    @pytest.fixture
    def mock_session(self, monkeypatch):
        class MockResponse:
            def __init__(self, status=200, text_data="{}"):
                self.status = status
                self._text = text_data

            async def text(self):
                return self._text

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        class MockClientSession:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

            def request(self, method, url, **kwargs):
                resp_json = {
                    "id": "batch_test_123",
                    "status": "completed",
                    "results": [
                        {
                            "custom_id": "test_0001",
                            "response": {
                                "status_code": 200,
                                "body": {"choices": [{"message": {"content": "Translated text"}}]},
                            },
                        }
                    ],
                    "usage": {"cost": 0.00042},
                }
                return MockResponse(status=200, text_data=json.dumps(resp_json))

        import aiohttp
        monkeypatch.setattr(aiohttp, "ClientSession", MockClientSession)

    def test_provider_trace_submit_and_get(self, mock_session, capsys):
        from chatybot.batch_manager import OpenRouterBatchProvider
        provider = OpenRouterBatchProvider(
            api_key="sk-or-v1-abcdef1234567890",
            base_url="https://test.api",
            trace_raw_payload=True,
        )
        reqs = [{"custom_id": "item_1", "body": {"messages": [{"role": "user", "content": "hi"}]}}]

        # Test submit
        asyncio.run(provider.submit(reqs, "test-model"))
        out = capsys.readouterr().out
        assert "Batch API Request Payload (POST):" in out
        assert "POST https://test.api/batches" in out
        assert "test-model" in out
        assert "Batch API Response Payload (POST https://test.api/batches):" in out
        assert "batch_test_123" in out

        # Test get
        asyncio.run(provider.get("batch_test_123"))
        out_get = capsys.readouterr().out
        assert "Batch API Request (GET):" in out_get
        assert "GET https://test.api/batches/batch_test_123" in out_get
        assert "Batch API Response Payload (GET https://test.api/batches/batch_test_123):" in out_get
        assert "Translated text" in out_get

    def test_provider_trace_disabled_prints_nothing(self, mock_session, capsys, monkeypatch):
        from chatybot.batch_manager import OpenRouterBatchProvider
        monkeypatch.delenv("CHATYBOT_TRACE_RAW_PAYLOAD", raising=False)
        provider = OpenRouterBatchProvider(
            api_key="sk-or-v1-abcdef1234567890",
            base_url="https://test.api",
            trace_raw_payload=False,
        )
        asyncio.run(provider.submit([], "test-model"))
        asyncio.run(provider.get("batch_test_123"))
        out = capsys.readouterr().out
        assert "Batch API Request" not in out
        assert "Batch API Response" not in out

    def test_provider_honors_env_var_trace(self, mock_session, capsys, monkeypatch):
        from chatybot.batch_manager import OpenRouterBatchProvider
        monkeypatch.setenv("CHATYBOT_TRACE_RAW_PAYLOAD", "1")
        provider = OpenRouterBatchProvider(
            api_key="sk-or-v1-abcdef1234567890",
            base_url="https://test.api",
            trace_raw_payload=False,
        )
        asyncio.run(provider.get("batch_test_123"))
        out = capsys.readouterr().out
        assert "Batch API Request (GET):" in out
        assert "Batch API Response Payload" in out

    def test_build_provider_passes_app_trace_setting(self, monkeypatch):
        from chatybot.commands.batch import _build_provider
        app = MagicMock()
        app.trace_raw_payload = True
        app.logging_manager = MagicMock()
        app.config_manager.get_model_config.return_value = {
            "name": "test-model",
            "vendor": "openrouter",
            "batch": True,
            "api_key": "MOCK_KEY_VAR",
        }
        monkeypatch.setenv("MOCK_KEY_VAR", "mock-key-val")
        meta = {"provider": "openrouter", "model_alias": "test_alias"}
        prov = _build_provider(app, meta)
        assert prov.trace_raw_payload is True
        assert prov.logging_manager == app.logging_manager


class TestBatchSamplingParams:
    """Tests for sampling parameters (temperature, max_tokens, top_p, penalties)."""

    def test_manager_start_and_build_payload_with_sampling(self, mgr):
        meta = mgr.start(
            "samp1",
            model_alias="gptoss_batch",
            model_name="openai/gpt-oss-120b:batch",
            provider="openrouter",
            temperature=0.3,
            max_tokens=256,
            top_p=0.85,
            frequency_penalty=0.5,
            presence_penalty=0.2,
        )
        assert meta["temperature"] == 0.3
        assert meta["max_tokens"] == 256
        assert meta["top_p"] == 0.85
        assert meta["frequency_penalty"] == 0.5
        assert meta["presence_penalty"] == 0.2

        items = mgr.add_items(meta, ["item text"], id_prefix="test_")
        payload = mgr.build_payload(meta, items)
        body = payload["requests"][0]["body"]
        assert body["temperature"] == 0.3
        assert body["max_tokens"] == 256
        assert body["top_p"] == 0.85
        assert body["frequency_penalty"] == 0.5
        assert body["presence_penalty"] == 0.2
        assert body.get("stream") is not True

    def test_manager_build_payload_omits_none_sampling(self, mgr):
        meta = mgr.start(
            "samp_none",
            model_alias="gptoss_batch",
            model_name="openai/gpt-oss-120b:batch",
            provider="openrouter",
        )
        items = mgr.add_items(meta, ["item text"], id_prefix="test_")
        payload = mgr.build_payload(meta, items)
        body = payload["requests"][0]["body"]
        assert "temperature" not in body
        assert "max_tokens" not in body
        assert "top_p" not in body
        assert "frequency_penalty" not in body
        assert "presence_penalty" not in body
        assert body.get("stream") is not True

    def test_manager_clone_inherits_and_overrides_sampling(self, mgr):
        orig = mgr.start(
            "orig_samp",
            model_alias="gptoss_batch",
            model_name="openai/gpt-oss-120b:batch",
            provider="openrouter",
            temperature=0.2,
            max_tokens=100,
        )
        mgr.add_items(orig, ["hello"], id_prefix="orig_")

        # Clone 1: inherit
        cloned1 = mgr.clone("orig_samp", "clone_inherit")
        assert cloned1["temperature"] == 0.2
        assert cloned1["max_tokens"] == 100

        # Clone 2: override temperature
        cloned2 = mgr.clone("orig_samp", "clone_override", temperature=0.7)
        assert cloned2["temperature"] == 0.7
        assert cloned2["max_tokens"] == 100

    def test_cli_start_with_sampling_opts(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start cli_samp temp=0.4 max_tokens=300 top_p=0.9"))
        out = capsys.readouterr().out
        assert "Opened batch draft 'cli_samp'" in out
        assert "Temperature: 0.4" in out
        meta = mgr.resolve("cli_samp")
        assert meta["temperature"] == 0.4
        assert meta["max_tokens"] == 300
        assert meta["top_p"] == 0.9

    def test_cli_start_inherits_model_config_sampling(self, mgr, capsys):
        ctx = make_ctx(mgr)
        # Model config has temperature = 0.7
        ctx.app.config_manager.get_model_config.return_value = {
            "name": "openai/gpt-oss-120b:batch",
            "vendor": "openrouter",
            "batch": True,
            "temperature": 0.7,
            "max_tokens": 512,
        }
        asyncio.run(run_cmd(ctx, "/batch start inherit_cfg"))
        out = capsys.readouterr().out
        assert "Temperature: 0.7" in out
        meta = mgr.resolve("inherit_cfg")
        assert meta["temperature"] == 0.7
        assert meta["max_tokens"] == 512

    def test_cli_clone_sampling_override(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start b_src temp=0.2"))
        capsys.readouterr()

        asyncio.run(run_cmd(ctx, "/batch clone b_src b_dst temp=0.85"))
        out = capsys.readouterr().out
        assert "Cloned batch 'b_src' -> 'b_dst'" in out
        assert "Temperature: 0.85" in out
        meta = mgr.resolve("b_dst")
        assert meta["temperature"] == 0.85

    def test_status_displays_sampling(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start status_samp temp=0.15 max_tokens=128"))
        capsys.readouterr()
        asyncio.run(run_cmd(ctx, "/batch status status_samp"))
        out = capsys.readouterr().out
        assert "Sampling:   temp=0.15, max_tokens=128" in out




class TestSamplingFixes:
    """Regressions for the sampling-parameter review findings."""

    def _ctx_with_model_temp(self, mgr, model_temperature=0.3):
        """make_ctx with a model config carrying a default temperature."""
        ctx = make_ctx(mgr)
        model_config = {
            "name": "openai/gpt-oss-120b:batch",
            "vendor": "openrouter",
            "batch": True,
            "api_key": "OPENROUTER_API_KEY",
            "temperature": model_temperature,
            "max_tokens": 1024,
            "input_cost_per_mtok": 0.10,
        }
        ctx.app.config_manager.get_model_config.return_value = model_config
        return ctx

    def test_plain_reopen_preserves_sampling(self, mgr, capsys):
        """P1 — reopening a draft must not revert user-set sampling to the
        model-config default."""
        ctx = self._ctx_with_model_temp(mgr, model_temperature=0.3)
        asyncio.run(run_cmd(ctx, "/batch start keep1 temp=0.9"))
        assert mgr.resolve("keep1")["temperature"] == 0.9
        asyncio.run(run_cmd(ctx, "/batch add item"))
        asyncio.run(run_cmd(ctx, "/batch end"))
        capsys.readouterr()
        # Plain reopen (the documented append workflow)
        asyncio.run(run_cmd(ctx, "/batch start keep1"))
        out = capsys.readouterr().out
        assert "Temperature: 0.3" not in out
        assert mgr.resolve("keep1")["temperature"] == 0.9
        # Explicit override on reopen still updates
        asyncio.run(run_cmd(ctx, "/batch start keep1 temp=0.5"))
        assert mgr.resolve("keep1")["temperature"] == 0.5

    def test_new_batch_still_inherits_model_sampling(self, mgr, capsys):
        """Creation-time model-config inheritance is unaffected by P1."""
        ctx = self._ctx_with_model_temp(mgr, model_temperature=0.7)
        asyncio.run(run_cmd(ctx, "/batch start inherit2"))
        assert mgr.resolve("inherit2")["temperature"] == 0.7

    def test_run_estimate_uses_batch_max_tokens(self, mgr, capsys, monkeypatch):
        """P2 — the pre-submit cost estimate must use the batch's own
        max_tokens, not the model config's."""
        ctx = self._ctx_with_model_temp(mgr)  # model max_tokens: 1024
        asyncio.run(run_cmd(ctx, "/batch start priced2 max_tokens=100"))
        asyncio.run(run_cmd(ctx, "/batch add " + "x" * 400))
        asyncio.run(run_cmd(ctx, "/batch end"))
        provider = FakeProvider()
        monkeypatch.setattr(batch_cmds, "_build_provider", lambda app, meta: provider)
        asyncio.run(run_cmd(ctx, "/batch run priced2"))
        out = capsys.readouterr().out
        # Expected with batch max_tokens=100 (not model 1024):
        # 400 chars -> 100 input tokens; (100 + 100*1) * 0.10/1M * 0.5
        expected = (400 // 4 + 100 * 1) * 0.10 / 1_000_000 * 0.5
        assert f"${expected:.4f}" in out
        wrong = (400 // 4 + 1024 * 1) * 0.10 / 1_000_000 * 0.5
        assert f"${wrong:.4f}" not in out

    def test_prompt_text_with_sampling_tokens_intact(self, mgr, capsys):
        """P3 — '/batch prompt' free text must not lose temp=/max_tokens=
        tokens to option parsing."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, '/batch prompt "output temp=0.5 and top_p=0.9 in prose"'))
        asyncio.run(run_cmd(ctx, "/batch start prose1"))
        meta = mgr.resolve("prose1")
        assert meta["prompt"] == "output temp=0.5 and top_p=0.9 in prose"
        assert meta.get("temperature") is None  # not parsed as an option

    def test_edit_text_with_sampling_tokens_intact(self, mgr, capsys):
        """P3 — '/batch edit' replacement text keeps temp= tokens."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start ed3"))
        asyncio.run(run_cmd(ctx, "/batch add original"))
        asyncio.run(run_cmd(ctx, "/batch edit ed3_0001 set temp=0.5 in the answer"))
        item = mgr.show_item(mgr.resolve("ed3"), "ed3_0001")
        assert item["text"] == "set temp=0.5 in the answer"


class TestCancelUnsupportedProvider:
    """OpenRouter has no cancel endpoint: /batch cancel must explain and
    offer a local-only force path instead of raising a raw HTTP 404."""

    def _inflight(self, mgr, name):
        meta = mgr.start(name, model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["x"], id_prefix=f"{name}_")
        mgr.end(meta)
        provider = FakeProvider(final_status="in_progress")
        meta = asyncio.run(mgr.run(meta, provider))
        assert meta["status"] == STATUS_SUBMITTED or meta["status"] == STATUS_IN_PROGRESS
        return meta, provider

    def test_openrouter_provider_declares_no_cancel(self):
        from chatybot.batch_manager import OpenRouterBatchProvider
        assert OpenRouterBatchProvider.supports_cancel is False

    def test_cancel_without_force_refused_informatively(self, mgr, capsys):
        meta, provider = self._inflight(mgr, "cantstop")
        provider.supports_cancel = False
        with pytest.raises(BatchError, match="cannot cancel a submitted batch"):
            asyncio.run(mgr.cancel(meta, provider))
        # State unchanged by the refusal
        assert mgr.find_by_name("cantstop")["status"] != "cancelled"

    def test_cancel_force_marks_local_only(self, mgr, capsys):
        meta, provider = self._inflight(mgr, "disown")
        provider.supports_cancel = False
        meta = asyncio.run(mgr.cancel(meta, provider, force=True))
        assert meta["status"] == "cancelled"
        out = capsys.readouterr().out
        assert "locally only" in out

    def test_cancel_command_flow_and_check_short_circuit(self, mgr, capsys, monkeypatch):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start todrop"))
        asyncio.run(run_cmd(ctx, "/batch add item"))
        asyncio.run(run_cmd(ctx, "/batch end"))
        provider = FakeProvider(final_status="in_progress")
        provider.supports_cancel = False  # mirror the real OpenRouter backend
        monkeypatch.setattr(batch_cmds, "_build_provider", lambda app, meta: provider)
        asyncio.run(run_cmd(ctx, "/batch run todrop"))
        capsys.readouterr()

        # Without force: informative refusal, no raw HTTP error
        asyncio.run(run_cmd(ctx, "/batch cancel todrop"))
        out = capsys.readouterr().out
        assert "cannot cancel a submitted batch" in out
        assert "force=true" in out
        assert mgr.find_by_name("todrop")["status"] != "cancelled"

        # With force: local cancel
        asyncio.run(run_cmd(ctx, "/batch cancel todrop force=true"))
        out = capsys.readouterr().out
        assert "Cancelled batch 'todrop'" in out
        assert "locally only" in out

        # check no longer polls a locally-cancelled batch
        calls_before = list(provider.calls)
        asyncio.run(run_cmd(ctx, "/batch check todrop"))
        out = capsys.readouterr().out
        assert "cancelled locally and is not polled anymore" in out
        assert list(provider.calls) == calls_before  # no provider traffic

    def test_cancel_supported_provider_still_remote(self, mgr, capsys):
        """Providers that do support cancel (FakeProvider default) keep the
        remote+local path."""
        meta, provider = self._inflight(mgr, "cansupport")
        assert provider.supports_cancel is True
        meta = asyncio.run(mgr.cancel(meta, provider))
        assert meta["status"] == "cancelled"
        assert provider.batches[meta["provider_id"]]["status"] == "cancelled"


class TestResultsOrdering:
    """Providers return results in arbitrary completion order; ChatyBot must
    normalize results.jsonl (and /batch results) back into staging order."""

    def test_results_written_in_staging_order(self, mgr, capsys):
        meta = mgr.start("ordered", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["one", "two", "three"], id_prefix="ordered_")
        mgr.end(meta)
        provider = FakeProvider()
        # Corrupt the provider order: return results in REVERSE completion order
        async def shuffled_submit(requests, model_name):
            batch = await FakeProvider.submit(provider, list(reversed(requests)),
                                              model_name)
            provider.calls.append(("submit", model_name, len(requests)))
            return batch
        provider.submit = shuffled_submit
        meta = asyncio.run(mgr.run(meta, provider))
        meta = asyncio.run(mgr.check(meta, provider))
        assert meta["status"] == STATUS_COMPLETED
        # results.jsonl restored to staging order despite reverse provider order
        stored = mgr.read_results(meta["batch_id"])
        assert [r["custom_id"] for r in stored] == [
            "ordered_0001", "ordered_0002", "ordered_0003"]


class TestEmptyCompletionVisibility:
    """Providers count status-200 empty completions as successes and never
    retry them; every batch surface must make them visible."""

    def _completed_with_empties(self, mgr, n=3, empty=2):
        meta = mgr.start("empt", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, [f"item {i}" for i in range(n)], id_prefix="empt_")
        mgr.end(meta)
        empty_ids = {f"empt_{i:04d}" for i in range(1, empty + 1)}
        provider = FakeProvider(empty_custom_ids=empty_ids)
        meta = asyncio.run(mgr.run(meta, provider))
        meta = asyncio.run(mgr.check(meta, provider))
        return meta, provider

    def test_meta_records_empty_count(self, mgr):
        meta, _ = self._completed_with_empties(mgr)
        assert meta["empty_results"] == 2
        # Catalog record carries it too
        rec = mgr.find_by_name("empt")
        assert rec["empty_results"] == 2
        assert rec["results_count"] == 3

    def test_check_summary_and_status_show_empties(self, mgr, capsys, monkeypatch):
        # Stage and submit, but let the /batch check COMMAND do the retrieval
        meta = mgr.start("empt", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["a", "b", "c"], id_prefix="empt_")
        mgr.end(meta)
        provider = FakeProvider(empty_custom_ids={"empt_0001", "empt_0002"})
        monkeypatch.setattr(batch_cmds, "_build_provider", lambda app, meta: provider)
        meta = asyncio.run(mgr.run(meta, provider))

        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch check empt"))
        out = capsys.readouterr().out
        assert "results: 3 written to results.jsonl (2 empty)" in out

        asyncio.run(run_cmd(ctx, "/batch status empt"))
        out = capsys.readouterr().out
        assert "Results:    3 (2 empty)" in out

    def test_results_header_and_batchlist_show_empties(self, mgr, capsys):
        self._completed_with_empties(mgr)
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch results empt"))
        out = capsys.readouterr().out
        assert "3 records, 2 empty" in out

        capsys.readouterr()
        asyncio.run(run_cmd(ctx, "/batchlist all"))
        out = capsys.readouterr().out
        assert "2 empty" in out

    def test_zero_empties_shows_no_marker(self, mgr, capsys, monkeypatch):
        meta = mgr.start("clean", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["a"], id_prefix="clean_")
        mgr.end(meta)
        provider = FakeProvider()  # no empty ids
        monkeypatch.setattr(batch_cmds, "_build_provider", lambda app, meta: provider)
        meta = asyncio.run(mgr.run(meta, provider))
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch check clean"))
        out = capsys.readouterr().out
        assert "results: 1 written to results.jsonl" in out
        assert "empty" not in out
