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

import aiohttp
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatybot.batch_manager import (  # noqa: E402
    BatchError,
    BatchManager,
    MistralBatchProvider,
    OpenRouterBatchProvider,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_STAGED,
    STATUS_SUBMITTING,
    STATUS_SUBMITTED,
    STATUS_SUBMIT_FAILED,
    STATUS_SUBMIT_UNKNOWN,
    make_provider,
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

    def test_abort_refuses_submit_failed(self, mgr, draft):
        mgr.add_items(draft, ["x"], id_prefix="dufu_run_")
        draft["status"] = STATUS_SUBMIT_FAILED
        mgr._write_meta(draft)
        with pytest.raises(BatchError, match="failed to submit"):
            mgr.abort(draft)
        assert mgr.find_by_name("dufu_run") is not None

    def test_purge_deletes_terminal_batch(self, mgr, draft):
        mgr.add_items(draft, ["x"], id_prefix="dufu_run_")
        draft["status"] = "completed"
        mgr._write_meta(draft)
        mgr.purge(draft)
        assert mgr.find_by_name("dufu_run") is None

    def test_purge_active_batch_refused(self, mgr, draft):
        draft["status"] = "in_progress"
        mgr._write_meta(draft)
        with pytest.raises(BatchError, match="still active"):
            mgr.purge(draft)
        assert mgr.find_by_name("dufu_run") is not None

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
        # Items whose completion body is empty (status 200, no content) -
        # mirroring the real-world gpt-oss/OpenRouter behavior.
        self.empty_custom_ids = set(empty_custom_ids or ())
        self.batches = {}
        self.calls = []

    async def submit(self, requests, model_name, *, metadata=None, session=None):
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

    async def get(self, provider_id, allow_missing=False, session=None):
        self.calls.append(("get", provider_id))
        return self.batches.get(provider_id)

    async def cancel(self, provider_id, session=None):
        self.batches[provider_id]["status"] = "cancelled"
        return self.batches[provider_id]

    async def list(self, session=None):
        return list(self.batches.values())

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

    async def fetch_results(self, batch, provider_id=None, session=None):
        return batch.get("results") or []


class TestSubmitPoll:
    def _staged(self, mgr):
        meta = mgr.start("run1", model_alias="m", model_name="model",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["a", "b"], id_prefix="run1_")
        mgr.end(meta)
        return meta

    def test_run_sidecar_then_submitted(self, mgr):
        meta = self._staged(mgr)
        observed_during_submit = []

        class InterceptProvider(FakeProvider):
            async def submit(self, requests, model_name, *, metadata=None, session=None):
                with open(mgr.index_path(), encoding="utf-8") as f:
                    observed_during_submit.extend([json.loads(line)["status"] for line in f if line.strip()])
                return await super().submit(requests, model_name, metadata=metadata)

        provider = InterceptProvider()
        meta = asyncio.run(mgr.run(meta, provider, max_cost_usd=5.0,
                                   max_open_per_provider=3))
        assert meta["status"] == STATUS_SUBMITTED
        assert meta["provider_id"] == "batch-0001"
        # Pre-POST fsynced sidecar is present during submit before the POST finishes
        assert observed_during_submit == ["staged", "submitting"]
        # Compacted on run completion
        with open(mgr.index_path(), encoding="utf-8") as f:
            final_statuses = [json.loads(line)["status"] for line in f if line.strip()]
        assert final_statuses == ["submitted"]

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

    def test_submit_failure_can_be_retried(self, mgr):
        meta = self._staged(mgr)
        # First attempt fails (e.g. bad API key or credit issue)
        bad_provider = FakeProvider(fail_submit=True)
        with pytest.raises(BatchError, match="submit_failed"):
            asyncio.run(mgr.run(meta, bad_provider))
        assert meta["status"] == STATUS_SUBMIT_FAILED

        # Second attempt succeeds with working provider
        good_provider = FakeProvider(fail_submit=False)
        meta = asyncio.run(mgr.run(meta, good_provider))
        assert meta["status"] == STATUS_SUBMITTED
        assert meta["provider_id"] == "batch-0001"

    def test_double_submit_refused_after_crash(self, mgr):
        meta = self._staged(mgr)
        meta["status"] = STATUS_SUBMITTING
        mgr._write_meta(meta)
        with pytest.raises(BatchError, match="resubmit=true"):
            asyncio.run(mgr.run(meta, FakeProvider()))

    def test_resubmit_unconfirmed_batch(self, mgr):
        meta = self._staged(mgr)
        meta["status"] = STATUS_SUBMIT_UNKNOWN
        mgr._write_meta(meta)
        # Without resubmit=true, raises error
        with pytest.raises(BatchError, match="resubmit=true"):
            asyncio.run(mgr.run(meta, FakeProvider()))
        # With resubmit=True, proceeds to submit
        meta = asyncio.run(mgr.run(meta, FakeProvider(), resubmit=True))
        assert meta["status"] == STATUS_SUBMITTED
        assert meta["provider_id"] == "batch-0001"

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

    def test_concurrency_cap_excludes_submitting_and_submit_unknown(self, mgr):
        for i in range(3):
            meta = mgr.start(f"stuck_{i}", model_alias="m", model_name="n",
                             provider="openrouter")
            mgr.add_items(meta, ["x"], id_prefix=f"s{i}_")
            mgr.end(meta)
            meta["status"] = STATUS_SUBMIT_UNKNOWN if i % 2 == 0 else STATUS_SUBMITTING
            mgr._write_meta(meta)

        # 3 stuck batches do not consume open slots
        meta = mgr.start("new_ok", model_alias="m", model_name="n", provider="openrouter")
        mgr.add_items(meta, ["x"], id_prefix="ok_")
        mgr.end(meta)
        run_res = asyncio.run(mgr.run(meta, FakeProvider(), max_open_per_provider=3))
        assert run_res["status"] == STATUS_SUBMITTED

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

    def test_purge_command(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start to_purge"))
        asyncio.run(run_cmd(ctx, "/batch add something"))
        capsys.readouterr()
        # Test purging by name
        asyncio.run(run_cmd(ctx, "/batch purge to_purge"))
        out = capsys.readouterr().out
        assert "Purged batch 'to_purge'" in out
        assert mgr.find_by_name("to_purge") is None

    def test_purge_command_by_id(self, mgr, capsys):
        meta = mgr.start("by_id_batch", model_alias="m", model_name="n", provider="openrouter")
        bid = meta["batch_id"]
        ctx = make_ctx(mgr)
        capsys.readouterr()
        # Test purging directly by batch_id
        asyncio.run(run_cmd(ctx, f"/batch purge {bid}"))
        out = capsys.readouterr().out
        assert f"Purged batch 'by_id_batch' ({bid})" in out
        assert mgr.find_by_name("by_id_batch") is None

    def test_unknown_subcommand(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch frobnicate"))
        out = capsys.readouterr().out
        assert "Unknown batch subcommand" in out

    def test_check_on_submit_failed_gives_retry_hint(self, mgr, capsys):
        meta = mgr.start("sf_run", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["x"], id_prefix="sf_")
        mgr.end(meta)
        meta["status"] = STATUS_SUBMIT_FAILED
        mgr._write_meta(meta)
        ctx = make_ctx(mgr)
        capsys.readouterr()
        asyncio.run(run_cmd(ctx, "/batch check sf_run"))
        out = capsys.readouterr().out
        assert "failed to submit" in out
        assert "/batch run sf_run" in out

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
# Command verb lint (PatternMatcher) - batch verbs must be caught unescaped
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
        """1.1 - stale instance dirs with colliding timestamps must not hang."""
        import chatybot.batch_manager as bm
        monkeypatch.setattr(bm.time, "time", lambda: 1793000000)
        # Simulate stale dirs: one without an index entry at ts, one at ts+1
        os.makedirs(os.path.join(batches_dir, "btch-1793000000-dupe"), exist_ok=True)
        os.makedirs(os.path.join(batches_dir, "btch-1793000001-dupe"), exist_ok=True)
        meta = mgr.start("dupe", model_alias="m", model_name="n", provider="openrouter")
        assert meta["batch_id"] == "btch-1793000002-dupe"

    def test_fix_estimate_counts_prompt_per_item(self, mgr):
        """1.2 - the system prompt is sent once per item; the estimate must
        multiply prompt chars by the item count."""
        meta = mgr.start("costy", model_alias="m", model_name="n",
                         provider="openrouter", prompt="p" * 200)  # 200 chars/item
        mgr.add_items(meta, ["x" * 400] * 3, id_prefix="costy_")
        est = mgr.estimate_cost_usd(meta, mgr.list_items(meta),
                                    max_tokens=0, input_cost_per_mtok=1.0)
        # (3*400 item chars + 3*200 prompt chars) // 4 = 450 tokens
        assert est == pytest.approx(450 * 1.0 / 1_000_000 * 0.5)

    def test_fix_run_uses_batch_model_not_active(self, mgr, capsys, monkeypatch):
        """1.3 - /batch run must work after the user switched the active chat
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
        """2.1 - a completed batch must not burn its name forever."""
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
        """2.1 - in-flight batches remain immutable (name refused while open)."""
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
        """2.2 - text starting with a word matching an existing batch name
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
        """2.4 - a batch whose model alias was removed from chat_config.toml
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
        """3.1 - auto-IDs stay sequential across bulk adds and follow-up calls."""
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
        """4 - zh and ar must have at least one keyword mapping to 'clear'."""
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

    def test_results_detail_shows_prompt_input_and_result(self, mgr, capsys):
        self._completed_batch(mgr, "detailed", n=2)
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch results detailed detail"))
        out = capsys.readouterr().out
        assert "[Template Prompt]: Translate." in out
        assert "[Input]:" in out
        assert "poem 0" in out
        assert "poem 1" in out
        assert "[Result]:" in out
        assert "detailed_0001" in out
        assert "detailed_0002" in out

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
        """P1 - reopening a draft must not revert user-set sampling to the
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
        """P2 - the pre-submit cost estimate must use the batch's own
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
        """P3 - '/batch prompt' free text must not lose temp=/max_tokens=
        tokens to option parsing."""
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, '/batch prompt "output temp=0.5 and top_p=0.9 in prose"'))
        asyncio.run(run_cmd(ctx, "/batch start prose1"))
        meta = mgr.resolve("prose1")
        assert meta["prompt"] == "output temp=0.5 and top_p=0.9 in prose"
        assert meta.get("temperature") is None  # not parsed as an option

    def test_edit_text_with_sampling_tokens_intact(self, mgr, capsys):
        """P3 - '/batch edit' replacement text keeps temp= tokens."""
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
        async def shuffled_submit(requests, model_name, *, metadata=None):
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


class TestRefactoredHelpers:
    """Tests for refactored helpers and edge-case fixes."""

    def test_is_empty_result(self):
        from chatybot.batch_manager import is_empty_result
        assert is_empty_result({"status_code": 200, "content": "", "error": None}) is True
        assert is_empty_result({"status_code": 200, "content": "   ", "error": None}) is True
        assert is_empty_result({"status_code": 200, "content": "Valid answer", "error": None}) is False
        assert is_empty_result({"status_code": 500, "content": "", "error": "rate limit"}) is False

    def test_opt_bool(self):
        from chatybot.commands.batch import _opt_bool
        assert _opt_bool({"force": "true"}, "force") is True
        assert _opt_bool({"force": "1"}, "force") is True
        assert _opt_bool({"force": "yes"}, "force") is True
        assert _opt_bool({"force": "YES "}, "force") is True
        assert _opt_bool({"force": "false"}, "force") is False
        assert _opt_bool({"force": "no"}, "force") is False
        assert _opt_bool({}, "force", default=True) is True
        assert _opt_bool({}, "force", default=False) is False

    def test_preview(self):
        from chatybot.commands.batch import _preview
        assert _preview(None) == ""
        assert _preview("Short text") == "Short text"
        long_str = "A" * 70
        assert _preview(long_str, max_len=60) == "A" * 60 + "..."

    def test_parse_paging(self, capsys):
        from chatybot.commands.batch import _parse_paging
        # Defaults
        assert _parse_paging({}) == (0, 10)
        # limit=
        assert _parse_paging({"limit": "5"}) == (0, 5)
        # range=start:end
        assert _parse_paging({"range": "2:6"}) == (2, 4)
        # range=:end (open start)
        assert _parse_paging({"range": ":7"}) == (0, 7)
        # range=start: (open end)
        assert _parse_paging({"range": "3:"}) == (3, None)
        # single number range
        assert _parse_paging({"range": "4"}) == (4, 10)
        # Invalid values fallback gracefully
        assert _parse_paging({"limit": "invalid"}) == (0, 10)
        assert "Invalid limit value" in capsys.readouterr().out
        assert _parse_paging({"range": "bad:format:extra"}) == (0, 10)
        assert "Invalid range format" in capsys.readouterr().out

    def test_abort_submitting_orphan_without_provider_id(self, mgr):
        """A batch in STATUS_SUBMITTING or STATUS_SUBMIT_UNKNOWN without a provider ID
        can be aborted cleanly because it's only a local record."""
        meta = mgr.start("crashed_orphan", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="co_")
        mgr.end(meta)
        meta["status"] = "submitting"
        mgr._write_meta(meta)

        mgr.abort(meta)
        assert mgr.find_by_name("crashed_orphan") is None

        # Also works for STATUS_SUBMIT_UNKNOWN
        meta_unk = mgr.start("unk_orphan", model_alias="gptoss_batch",
                             model_name="openai/gpt-oss-120b:batch",
                             provider="openrouter", prompt="p")
        mgr.add_items(meta_unk, ["item1"], id_prefix="uo_")
        mgr.end(meta_unk)
        meta_unk["status"] = STATUS_SUBMIT_UNKNOWN
        mgr._write_meta(meta_unk)
        mgr.abort(meta_unk)
        assert mgr.find_by_name("unk_orphan") is None

    def test_run_with_precomputed_estimate(self, mgr):
        meta = mgr.start("fast_est", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="fe_")
        mgr.end(meta)
        provider = FakeProvider()
        meta = asyncio.run(mgr.run(meta, provider, precomputed_estimate=0.0042))
        assert meta["status"] == "submitted"

    def test_clean_var_name(self):
        from chatybot.commands.paging import clean_var_name
        assert clean_var_name("$MY_VAR") == "MY_VAR"
        assert clean_var_name("  $$RESULT  ") == "RESULT"
        assert clean_var_name(None, default="DEFAULT") == "DEFAULT"
        assert clean_var_name("", default="DEF") == ""

    def test_abort_submitting_warns(self, mgr):
        meta = mgr.start("warn_orphan", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="wo_")
        mgr.end(meta)
        meta["status"] = "submitting"
        meta["provider_id"] = "remote_id_123"
        mgr._write_meta(meta)

        with pytest.raises(BatchError, match="submitting"):
            mgr.abort(meta)
        assert mgr.find_by_name("warn_orphan") is not None

    def test_batch_config_delegation(self):
        from chatybot.commands.batch import _batch_config
        class FakeApp:
            class FakeConfigManager:
                called = False
                def get_batch_config(self):
                    self.called = True
                    return {"max_cost_usd": 12.5}
            config_manager = FakeConfigManager()
        app = FakeApp()
        cfg = _batch_config(app)
        assert cfg == {"max_cost_usd": 12.5}
        assert app.config_manager.called is True

    def test_stray_add_when_newest_is_submitted(self, mgr, capsys):
        ctx = make_ctx(mgr)
        # Create a batch and move it to submitted
        meta = mgr.start("submitted_b", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="sb_")
        mgr.end(meta)
        meta["status"] = "submitted"
        meta["provider_id"] = "prov_123"
        mgr._write_meta(meta)

        # A stray /batch add with no draft open should say 'no active draft found'
        capsys.readouterr()
        asyncio.run(run_cmd(ctx, "/batch add orphaned item"))
        out = capsys.readouterr().out
        assert "Error: no batch specified and no active draft found." in out
        assert "Start one with: /batch start <name>" in out
        assert "already been submitted" not in out


# ---------------------------------------------------------------------------
# Phase 2: Mistral Batch provider (inline batching)
# ---------------------------------------------------------------------------

class FakeMistralProvider:
    """In-memory Mistral-shaped provider for testing inline batch + Files API
    result retrieval. Results come from output_file/error_file (not inline)."""
    name = "mistral"
    supports_cancel = True

    def __init__(self, fail_submit=False, final_status="SUCCESS",
                 empty_custom_ids=None):
        self.fail_submit = fail_submit
        self.final_status = final_status
        self.empty_custom_ids = set(empty_custom_ids or ())
        self.batches = {}
        self.files = {}  # file_id -> JSONL content
        self.calls = []

    async def submit(self, requests, model_name, *, metadata=None, session=None):
        self.calls.append(("submit", model_name, len(requests), metadata))
        if self.fail_submit:
            raise RuntimeError("HTTP 401: unauthorized")
        bid = f"job-{len(self.calls):04d}"
        # Build output file content (JSONL) - one line per request
        output_lines = []
        for r in requests:
            cid = r["custom_id"]
            if cid in self.empty_custom_ids:
                content = ""
            else:
                content = "ok"
            output_lines.append(json.dumps({
                "custom_id": cid,
                "response": {
                    "status_code": 200,
                    "body": {"choices": [{"message": {"content": content}}]},
                },
            }))
        output_file_id = f"file-out-{len(self.calls):04d}"
        self.files[output_file_id] = "\n".join(output_lines)
        self.batches[bid] = {
            "id": bid,
            "status": self.final_status,
            "total_requests": len(requests),
            "succeeded_requests": len(requests),
            "failed_requests": 0,
            "output_file": output_file_id,
            "error_file": None,
            "metadata": metadata,
        }
        return self.batches[bid]

    async def get(self, provider_id, allow_missing=False, session=None):
        self.calls.append(("get", provider_id))
        return self.batches.get(provider_id)

    async def cancel(self, provider_id, session=None):
        self.batches[provider_id]["status"] = "CANCELLED"
        return self.batches[provider_id]

    async def list(self, session=None):
        return list(self.batches.values())

    async def fetch_results(self, batch, provider_id=None, session=None):
        output_file_id = batch.get("output_file")
        if not output_file_id:
            return []
        content = self.files.get(output_file_id, "")
        results = []
        for line in content.strip().split("\n"):
            if line:
                results.append(json.loads(line))
        return results

    @staticmethod
    def normalize_status(batch):
        from chatybot.batch_manager import MISTRAL_STATUS_MAP
        return MISTRAL_STATUS_MAP.get(batch.get("status", ""),
                                       batch.get("status", ""))

    @staticmethod
    def counts_of(batch):
        return (batch.get("total_requests"),
                batch.get("succeeded_requests"),
                batch.get("failed_requests"))

    @staticmethod
    def normalize_result(entry):
        return MistralBatchProvider.normalize_result(entry)

    @staticmethod
    def telemetry_of(batch):
        return MistralBatchProvider.telemetry_of(batch)


class TestMistralProvider:
    """Tests for the Mistral inline batch backend (Phase 2)."""

    def _staged(self, mgr):
        meta = mgr.start("mrun", model_alias="mistral_batch",
                         model_name="mistral-large-latest",
                         provider="mistral", prompt="Translate.")
        mgr.add_items(meta, ["a", "b"], id_prefix="mrun_")
        mgr.end(meta)
        return meta

    def test_make_provider_mistral(self):
        provider = make_provider(
            {"vendor": "mistral", "base_url": "https://api.mistral.ai/v1"},
            api_key="fake_key",
        )
        assert isinstance(provider, MistralBatchProvider)
        assert provider.name == "mistral"
        assert provider.supports_cancel is True

    def test_make_provider_openrouter_default(self):
        provider = make_provider(
            {"vendor": "openrouter"},
            api_key="fake_key",
        )
        assert isinstance(provider, OpenRouterBatchProvider)

    def test_mistral_submit_sends_metadata(self, mgr):
        meta = self._staged(mgr)
        provider = FakeMistralProvider()
        meta = asyncio.run(mgr.run(meta, provider, max_cost_usd=5.0,
                                    max_open_per_provider=3))
        assert meta["status"] == STATUS_SUBMITTED
        assert meta["provider_id"] == "job-0001"
        # Metadata with client_token should have been passed
        _, _, _, md = provider.calls[0]
        assert md is not None
        assert md["client_token"] == meta["batch_id"]

    def test_mistral_check_downloads_results_from_files_api(self, mgr, batches_dir):
        meta = self._staged(mgr)
        provider = FakeMistralProvider()
        meta = asyncio.run(mgr.run(meta, provider))
        meta = asyncio.run(mgr.check(meta, provider))
        assert meta["status"] == STATUS_COMPLETED
        # Mistral has no exact cost - telemetry returns None
        assert meta["cost_usd"] is None
        results = mgr.read_results(meta["batch_id"])
        assert len(results) == 2
        assert results[0]["custom_id"] == "mrun_0001"
        assert results[0]["content"] == "ok"

    def test_mistral_cancel_supported(self, mgr):
        meta = self._staged(mgr)
        provider = FakeMistralProvider(final_status="RUNNING")
        meta = asyncio.run(mgr.run(meta, provider))
        meta = asyncio.run(mgr.cancel(meta, provider))
        assert meta["status"] == "cancelled"

    def test_mistral_inline_limit_refused(self):
        provider = MistralBatchProvider(api_key="fake")
        too_many = [{"custom_id": str(i), "body": {}} for i in range(10_001)]
        with pytest.raises(BatchError, match="Inline batch limit exceeded"):
            asyncio.run(provider.submit(too_many, "mistral-large-latest"))

    def test_mistral_normalize_status_map(self):
        assert MistralBatchProvider.normalize_status({"status": "QUEUED"}) == "submitted"
        assert MistralBatchProvider.normalize_status({"status": "RUNNING"}) == "in_progress"
        assert MistralBatchProvider.normalize_status({"status": "SUCCESS"}) == "completed"
        assert MistralBatchProvider.normalize_status({"status": "FAILED"}) == "failed"
        assert MistralBatchProvider.normalize_status({"status": "TIMEOUT_EXCEEDED"}) == "expired"
        assert MistralBatchProvider.normalize_status({"status": "CANCELLATION_REQUESTED"}) == "in_progress"
        assert MistralBatchProvider.normalize_status({"status": "CANCELLED"}) == "cancelled"

    def test_mistral_normalize_result_response_body(self):
        entry = {"custom_id": "x", "response": {
            "status_code": 200,
            "body": {"choices": [{"message": {"content": "hello"}}]},
        }}
        r = MistralBatchProvider.normalize_result(entry)
        assert r["custom_id"] == "x"
        assert r["status_code"] == 200
        assert r["content"] == "hello"

    def test_mistral_normalize_result_output_choices(self):
        entry = {"custom_id": "y", "output": {
            "choices": [{"message": {"content": "world"}}],
        }}
        r = MistralBatchProvider.normalize_result(entry)
        assert r["custom_id"] == "y"
        assert r["status_code"] == 200
        assert r["content"] == "world"

    def test_mistral_normalize_result_error(self):
        entry = {"custom_id": "z", "error": {"message": "bad request"}}
        r = MistralBatchProvider.normalize_result(entry)
        assert r["custom_id"] == "z"
        assert r["content"] is None
        assert "error" in r

    def test_mistral_telemetry_no_cost(self):
        t = MistralBatchProvider.telemetry_of({"status": "SUCCESS"})
        assert t["cost_usd"] is None
        assert t["host_backend"] is None

    def test_build_provider_allows_mistral(self, mgr):
        """The command-layer _build_provider should accept vendor=mistral."""
        from chatybot.commands.batch import _build_provider
        meta = self._staged(mgr)
        meta["status"] = STATUS_STAGED
        mgr._write_meta(meta)
        app = SimpleNamespace()
        model_config = {
            "name": "mistral-large-latest",
            "vendor": "mistral",
            "batch": True,
            "api_key": "MISTRAL_API_KEY",
            "base_url": "https://api.mistral.ai/v1",
        }
        app.config_manager = MagicMock()
        app.config_manager.get_model_config.return_value = model_config
        app.trace_raw_payload = False
        app.logging_manager = None
        os.environ["MISTRAL_API_KEY"] = "fake_test_key"
        try:
            provider = _build_provider(app, meta)
            assert isinstance(provider, MistralBatchProvider)
        finally:
            del os.environ["MISTRAL_API_KEY"]

    def test_build_provider_rejects_unknown_vendor(self, mgr):
        from chatybot.commands.batch import _build_provider, BatchError as CmdBatchError
        meta = mgr.start("bad", model_alias="x", model_name="y",
                         provider="unsupported_vendor")
        mgr.add_items(meta, ["a"], id_prefix="bad_")
        mgr.end(meta)
        app = SimpleNamespace()
        with pytest.raises(CmdBatchError, match="not implemented"):
            _build_provider(app, meta)


class TestMultimodalBatch:
    """Tests for multimodal / imagebank support in the Batch API subsystem."""

    def test_batch_add_imagebank_option(self, mgr):
        ctx = make_ctx(mgr)
        ctx.buffer_manager.image_banks["imagebank1"] = "data:image/jpeg;base64,fakeimage123"
        asyncio.run(run_cmd(ctx, "/batch start mm_test model=gptoss_batch"))
        asyncio.run(run_cmd(ctx, "/batch add imagebank=1"))
        meta = mgr.find_by_name("mm_test")
        items = mgr.list_items(meta)
        assert len(items) == 1
        assert items[0]["custom_id"] == "ib1_0001"
        assert items[0]["image"] == "data:image/jpeg;base64,fakeimage123"
        assert items[0]["origin"] == "imagebank1"

    def test_batch_add_imagebank_placeholder(self, mgr):
        ctx = make_ctx(mgr)
        ctx.buffer_manager.image_banks["imagebank2"] = "data:image/png;base64,fakepng456"
        asyncio.run(run_cmd(ctx, "/batch start mm_test2 model=gptoss_batch"))
        asyncio.run(run_cmd(ctx, "/batch add What colors are here: {imagebank2}"))
        meta = mgr.find_by_name("mm_test2")
        items = mgr.list_items(meta)
        assert len(items) == 1
        assert items[0]["custom_id"] == "ib2_0001"
        assert items[0]["image"] == "data:image/png;base64,fakepng456"
        assert items[0]["text"] == "What colors are here:"

    def test_batch_add_empty_imagebank_error(self, mgr, capsys):
        ctx = make_ctx(mgr)
        ctx.buffer_manager.image_banks["imagebank3"] = ""
        asyncio.run(run_cmd(ctx, "/batch start mm_empty model=gptoss_batch"))
        asyncio.run(run_cmd(ctx, "/batch add imagebank=3"))
        out = capsys.readouterr().out
        assert "imagebank3 is empty" in out
        meta = mgr.find_by_name("mm_empty")
        assert len(mgr.list_items(meta)) == 0

    def test_batch_add_image_url_with_text(self, mgr):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start url_test model=gptoss_batch"))
        asyncio.run(run_cmd(ctx, '/batch add Filename: photo.jpg image=https://example.com/photo.jpg'))
        meta = mgr.find_by_name("url_test")
        items = mgr.list_items(meta)
        assert len(items) == 1
        assert items[0]["image"] == "https://example.com/photo.jpg"
        assert items[0]["text"] == "Filename: photo.jpg"
        assert items[0]["origin"] == "image_url"

    def test_batch_add_image_url_no_text_error(self, mgr, capsys):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start url_err model=gptoss_batch"))
        asyncio.run(run_cmd(ctx, "/batch add image=https://example.com/photo.jpg"))
        out = capsys.readouterr().out
        assert "Usage:" in out
        meta = mgr.find_by_name("url_err")
        assert len(mgr.list_items(meta)) == 0

    def test_batch_add_image_data_uri_with_text(self, mgr):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start datauri_test model=gptoss_batch"))
        asyncio.run(run_cmd(ctx,
            '/batch add Describe this image=data:image/jpeg;base64,/9j/4AAQ'))
        meta = mgr.find_by_name("datauri_test")
        items = mgr.list_items(meta)
        assert len(items) == 1
        assert items[0]["image"] == "data:image/jpeg;base64,/9j/4AAQ"
        assert items[0]["text"] == "Describe this"

    def test_build_payload_image_url(self, mgr):
        meta = mgr.start("url_payload", model_alias="mistral_batch",
                         model_name="mistral-large-latest",
                         provider="mistral", prompt="Analyze.")
        mgr.add_items(meta, ["Filename: test.jpg"], id_prefix="img_",
                      image="https://example.com/test.jpg")
        items = mgr.list_items(meta)
        payload = mgr.build_payload(meta, items)
        req = payload["requests"][0]
        body = req["body"]
        msg = body["messages"][1]  # [system, user]
        assert msg["role"] == "user"
        content = msg["content"]
        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "Filename: test.jpg"}
        assert content[1] == {"type": "image_url",
                              "image_url": {"url": "https://example.com/test.jpg"}}

    def test_build_payload_multimodal(self, mgr):
        meta = mgr.start("mm_payload", model_alias="mistral_batch",
                         model_name="mistral-large-latest",
                         provider="mistral", prompt="Analyze images.")
        mgr.add_items(meta, ["Identify subject"], id_prefix="ib1_",
                      image="data:image/jpeg;base64,payloadimage")
        items = mgr.list_items(meta)
        payload = mgr.build_payload(meta, items)
        req = payload["requests"][0]
        body = req["body"]
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == "Analyze images."
        user_msg = body["messages"][1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert user_msg["content"][0] == {"type": "text", "text": "Identify subject"}
        assert user_msg["content"][1] == {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,payloadimage"}
        }

    def test_build_payload_image_only(self, mgr):
        meta = mgr.start("mm_img_only", model_alias="mistral_batch",
                         model_name="mistral-large-latest",
                         provider="mistral", prompt="List 3 colors.")
        mgr.add_items(meta, [""], id_prefix="ib1_",
                      image="data:image/jpeg;base64,payloadimage")
        items = mgr.list_items(meta)
        payload = mgr.build_payload(meta, items)
        user_msg = payload["requests"][0]["body"]["messages"][1]
        assert len(user_msg["content"]) == 1
        assert user_msg["content"][0]["type"] == "image_url"

    def test_multimodal_show_item_and_items(self, mgr, capsys):
        ctx = make_ctx(mgr)
        ctx.buffer_manager.image_banks["imagebank1"] = "data:image/jpeg;base64," + "A" * 1000
        asyncio.run(run_cmd(ctx, "/batch start mm_show model=gptoss_batch"))
        asyncio.run(run_cmd(ctx, "/batch add imagebank=1"))
        asyncio.run(run_cmd(ctx, "/batch items mm_show"))
        out = capsys.readouterr().out
        assert "[image imagebank1]" in out
        asyncio.run(run_cmd(ctx, "/batch show ib1_0001 mm_show"))
        out2 = capsys.readouterr().out
        assert "[Attached Image: imagebank1 (1023 bytes)]" in out2
        assert "A" * 50 not in out2

    def test_mistral_html_400_hint(self):
        from chatybot.batch_manager import MistralBatchProvider
        err = MistralBatchProvider._http_error(
            400,
            "<!doctype html><html><title>Bad Request (400)</title><body><h1>Bad Request (400)</h1></body></html>",
            "https://api.mistral.ai/v1/batch/jobs"
        )
        assert "Mistral's edge gateway rejected the request with HTML 400 Bad Request" in str(err)
        assert "Ensure images are compressed" in str(err)


class TestBatchPayloadSizeLimits:
    def test_format_bytes(self):
        from chatybot.commands.batch import _format_bytes
        assert _format_bytes(0) == ""
        assert _format_bytes(500) == "500 B"
        assert _format_bytes(1024) == "1.0 KB"
        assert _format_bytes(2048) == "2.0 KB"
        assert _format_bytes(1024 * 1024) == "1.00 MB"
        assert _format_bytes(2500000) == "2.38 MB"
        assert _format_bytes(2 * 1024 * 1024 * 1024) == "2.00 GB"

    def test_check_payload_limits_mistral(self, mgr):
        meta = {"provider": "mistral", "name": "test_m"}
        items_small = [{"custom_id": "1", "text": "hello"}]
        items_image = [{"custom_id": "1", "text": "hello", "image": "data:image/jpeg;base64,123"}]

        # Under 2 MB: no warnings
        assert mgr.check_payload_limits(meta, items_small, 500 * 1024) == []

        # 2 MB - 4 MB: approaching limit
        w_warn = mgr.check_payload_limits(meta, items_small, int(2.5 * 1024 * 1024))
        assert len(w_warn) == 1
        assert "approaches Mistral's inline body limit" in w_warn[0]

        # 2 MB - 4 MB with image: image compression hint
        w_img = mgr.check_payload_limits(meta, items_image, int(2.5 * 1024 * 1024))
        assert len(w_img) == 1
        assert "compress attached images" in w_img[0]

        # >= 4 MB: exceeds limit
        w_exceed = mgr.check_payload_limits(meta, items_image, int(4.5 * 1024 * 1024))
        assert len(w_exceed) == 1
        assert "exceeds Mistral's inline body limit" in w_exceed[0]
        assert "HTTP 400 Bad Request" in w_exceed[0]

        # Exceeding item count (>10,000)
        items_10001 = [{"custom_id": str(i), "text": "x"} for i in range(10001)]
        w_count = mgr.check_payload_limits(meta, items_10001, 1000)
        assert any("exceeds Mistral's inline limit" in w for w in w_count)

    def test_check_payload_limits_openrouter(self, mgr):
        meta = {"provider": "openrouter", "name": "test_or"}
        items = [{"custom_id": "1", "text": "hello"}]

        # Under 100 MB: no warnings
        assert mgr.check_payload_limits(meta, items, 50 * 1024 * 1024) == []

        # 100 MB - 200 MB: approaching limit
        w_warn = mgr.check_payload_limits(meta, items, 150 * 1024 * 1024)
        assert len(w_warn) == 1
        assert "approaching OpenRouter's 200 MB limit" in w_warn[0]

        # >= 200 MB: exceeds limit
        w_exceed = mgr.check_payload_limits(meta, items, 210 * 1024 * 1024)
        assert len(w_exceed) == 1
        assert "exceeds OpenRouter's 200 MB batch limit" in w_exceed[0]
        assert "HTTP 413" in w_exceed[0]

    def test_end_returns_size_and_warnings(self, mgr):
        meta = mgr.start("m_size_test", model_alias="mistral_batch",
                         model_name="mistral-large-latest",
                         provider="mistral", prompt="Analyze.")
        # Add a large item that puts payload > 2 MB
        large_base64 = "data:image/jpeg;base64," + "A" * (2500000)
        mgr.add_items(meta, ["desc"], id_prefix="m_sz_", image=large_base64)

        result = mgr.end(meta)
        assert result["item_count"] == 1
        assert result["payload_bytes"] > 2500000
        assert len(result["warnings"]) == 1
        assert "approaches Mistral's inline body limit" in result["warnings"][0]

        # Verify meta persisted payload_bytes
        persisted = mgr.read_meta(meta["batch_id"])
        assert persisted["payload_bytes"] == result["payload_bytes"]

    def test_cli_end_displays_size_and_warning(self, mgr, capsys):
        ctx = make_ctx(mgr)
        mistral_cfg = {
            "name": "mistral-large-latest",
            "vendor": "mistral",
            "batch": True,
            "api_key": "MISTRAL_API_KEY",
        }
        ctx.config_manager.config["models"]["mistral_batch"] = mistral_cfg
        ctx.config_manager.get_model_config.side_effect = lambda a: ctx.config_manager.config["models"].get(a, mistral_cfg)
        ctx.config_manager.list_batch_capable_models.return_value = ["gptoss_batch", "mistral_batch"]
        ctx.buffer_manager.image_banks["imagebank1"] = "data:image/jpeg;base64," + "B" * (4500000)
        asyncio.run(run_cmd(ctx, "/batch start cli_warn model=mistral_batch"))
        asyncio.run(run_cmd(ctx, "/batch add imagebank=1"))
        asyncio.run(run_cmd(ctx, "/batch end"))
        out = capsys.readouterr().out

        assert "payload compiled to requests.json (" in out
        assert "Warning: Payload size" in out
        assert "exceeds Mistral's inline body limit" in out

        # Status also shows payload
        asyncio.run(run_cmd(ctx, "/batch status cli_warn"))
        status_out = capsys.readouterr().out
        assert "Payload:" in status_out


# ---------------------------------------------------------------------------
# Regression & Bug Fix Verification (The 7 Hardening Fixes)
# ---------------------------------------------------------------------------

class TestBatchApiBugFixes:
    def test_submit_timeout_sets_submit_unknown_state(self, mgr):
        meta = mgr.start("timeout_run", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="tr_")
        mgr.end(meta)

        class TimeoutProvider:
            name = "openrouter"
            supports_cancel = True
            async def submit(self, requests, model_name, *, metadata=None, session=None):
                raise asyncio.TimeoutError("Gateway POST timeout")

        with pytest.raises(BatchError, match="Submission unconfirmed"):
            asyncio.run(mgr.run(meta, TimeoutProvider()))

        # Status must be submit_unknown to indicate unconfirmed submission
        persisted = mgr.read_meta(meta["batch_id"])
        assert persisted["status"] == STATUS_SUBMIT_UNKNOWN

        # Re-running without resubmit=true is refused
        with pytest.raises(BatchError, match="resubmit=true"):
            asyncio.run(mgr.run(meta, TimeoutProvider()))

        # Purging the submit_unknown record is allowed
        mgr.purge(persisted)
        assert mgr.find_by_name("timeout_run") is None

    def test_check_wait_limits_consecutive_404(self, mgr):
        meta = mgr.start("lost_run", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="lr_")
        mgr.end(meta)
        meta["status"] = STATUS_SUBMITTED
        meta["provider_id"] = "prov_404_id"
        mgr._write_meta(meta)

        class NotFoundProvider:
            async def get(self, provider_id, allow_missing=False):
                return None
            def normalize_status(self, batch):
                return "in_progress"

        with pytest.raises(BatchError, match="404 Not Found 3 consecutive times"):
            asyncio.run(mgr.check(meta, NotFoundProvider(), wait=True, max_consecutive_404=3, poll_start_seconds=0.001))

    def test_check_wait_limits_max_duration(self, mgr):
        meta = mgr.start("long_run", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="long_")
        mgr.end(meta)
        meta["status"] = STATUS_SUBMITTED
        meta["provider_id"] = "prov_long_id"
        mgr._write_meta(meta)

        class EndlessProvider:
            async def get(self, provider_id, allow_missing=False):
                return {"status": "in_progress"}
            def normalize_status(self, batch):
                return "in_progress"

        with pytest.raises(BatchError, match="Polling timeout reached"):
            asyncio.run(mgr.check(meta, EndlessProvider(), wait=True, max_wait_seconds=0.01, poll_start_seconds=0.001))

    def test_end_scans_prompt_template_for_secrets(self, mgr):
        meta = mgr.start("leak_prompt", model_alias="gptoss_batch",
                         model_name="openai/gpt-oss-120b:batch",
                         provider="openrouter",
                         prompt="GitHub token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890")
        mgr.add_items(meta, ["harmless item"], id_prefix="lp_")

        with pytest.raises(BatchError, match="Security scan failed"):
            mgr.end(meta)

        # Batch stays draft and cannot seal
        persisted = mgr.read_meta(meta["batch_id"])
        assert persisted["status"] == STATUS_DRAFT

    def test_detect_provider_in_make_provider(self):
        # Base URL contains mistral.ai but vendor is omitted
        cfg = {
            "name": "mistral-large-latest",
            "base_url": "https://api.mistral.ai/v1",
        }
        provider = make_provider(cfg, api_key="secret_key")
        assert isinstance(provider, MistralBatchProvider)

    def test_detect_provider_in_start_command(self, mgr):
        ctx = make_ctx(mgr)
        mistral_unspecified_vendor = {
            "name": "mistral-large-latest",
            "base_url": "https://api.mistral.ai/v1",
            "batch": True,
            "api_key": "MISTRAL_API_KEY",
        }
        ctx.config_manager.config["models"]["mistral_autodetect"] = mistral_unspecified_vendor
        ctx.config_manager.get_model_config.side_effect = lambda a: ctx.config_manager.config["models"].get(a, mistral_unspecified_vendor)
        ctx.config_manager.list_batch_capable_models.return_value = ["mistral_autodetect"]

        asyncio.run(run_cmd(ctx, "/batch start auto_prov model=mistral_autodetect"))
        meta = mgr.find_by_name("auto_prov")
        assert meta["provider"] == "mistral"

    def test_cancelled_batch_retrieves_partial_results(self, mgr):
        meta = mgr.start("partial_cancel", model_alias="mistral_batch",
                         model_name="mistral-large-latest",
                         provider="mistral", prompt="p")
        mgr.add_items(meta, ["item1", "item2"], id_prefix="pc_")
        mgr.end(meta)

        provider = FakeMistralProvider(final_status="CANCELLED")
        # Submit to populate provider files and get real provider_id
        submitted = asyncio.run(provider.submit([{"custom_id": "pc_0001", "body": {}}], "mistral-large-latest"))
        meta["status"] = STATUS_SUBMITTED
        meta["provider_id"] = submitted["id"]
        mgr._write_meta(meta)

        meta = asyncio.run(mgr.check(meta, provider))
        assert meta["status"] == "cancelled"
        assert meta["results_count"] == 1
        results = mgr.read_results(meta["batch_id"])
        assert len(results) == 1
        assert results[0]["custom_id"] == "pc_0001"

    def test_estimate_cost_usd_output_pricing_and_default(self, mgr):
        meta = mgr.start("cost_calc", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        items = [{"text": "x" * 400}]  # 400 chars -> 100 tokens

        # 1. max_tokens=None falls back to default 1000 output tokens
        est_default = mgr.estimate_cost_usd(meta, items, max_tokens=None, input_cost_per_mtok=2.0)
        # prompt="p" (1 char) -> total chars 401 // 4 = 100 input tokens
        # input: 100 * 2.0 / 1e6 * 0.5 = 0.0001
        # output: 1000 * 2.0 / 1e6 * 0.5 = 0.001
        # total: 0.0011
        assert est_default == pytest.approx(0.0011)

        # 2. explicit output_cost_per_mtok (e.g. $4.0 vs input $2.0)
        est_separate = mgr.estimate_cost_usd(
            meta, items, max_tokens=500,
            input_cost_per_mtok=2.0,
            output_cost_per_mtok=4.0,
        )
        # input: 100 * 2.0 / 1e6 * 0.5 = 0.0001
        # output: 500 * 4.0 / 1e6 * 0.5 = 0.0010
        # total: 0.0011
        assert est_separate == pytest.approx(0.0011)

        # 3. max_tokens=0 explicitly counts 0 output tokens
        est_zero = mgr.estimate_cost_usd(meta, items, max_tokens=0, input_cost_per_mtok=2.0)
        assert est_zero == pytest.approx(0.0001)


class TestBatchPerformanceOptimizations:
    def test_skip_index_write_on_add_remove_and_compaction(self, mgr):
        meta = mgr.start("opt_test", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        with open(mgr.index_path(), encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == 1
        assert json.loads(lines[0])["item_count"] == 0

        # Adding items should NOT append to index.jsonl
        mgr.add_items(meta, ["item 1", "item 2"], id_prefix="opt_test_")
        with open(mgr.index_path(), encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == 1  # Still 1 line!

        # list_index() overlays live item_count from meta.json
        recs = mgr.list_index()
        assert recs[0]["item_count"] == 2

        # Removing an item should NOT append to index.jsonl
        mgr.remove_item(meta, "opt_test_0001")
        with open(mgr.index_path(), encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == 1  # Still 1 line!
        recs = mgr.list_index()
        assert recs[0]["item_count"] == 1

        # end() compacts the index
        mgr.end(meta)
        with open(mgr.index_path(), encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == 1
        staged_rec = json.loads(lines[0])
        assert staged_rec["status"] == STATUS_STAGED
        assert staged_rec["item_count"] == 1

    def test_find_batches_containing_fast_paths(self, mgr):
        meta1 = mgr.start("batch_one", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        mgr.add_items(meta1, ["text1"], id_prefix="batch_one_")

        meta2 = mgr.start("batch_two", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        mgr.add_items(meta2, ["text2"], id_prefix="batch_two_")

        # 1. Active draft is batch_two: finding batch_two_0001 returns [meta2] via active draft check
        matches_active = mgr.find_batches_containing("batch_two_0001")
        assert len(matches_active) == 1
        assert matches_active[0]["batch_id"] == meta2["batch_id"]

        # 2. Prefix match for batch_one_0001 resolves batch_one via find_by_name prefix candidate
        matches_prefix = mgr.find_batches_containing("batch_one_0001")
        assert len(matches_prefix) == 1
        assert matches_prefix[0]["batch_id"] == meta1["batch_id"]

        # 3. editable_only filters out non-draft batches without reading their items
        mgr.end(meta1)
        assert meta1["status"] == STATUS_STAGED
        assert mgr.find_batches_containing("batch_one_0001", editable_only=True) == []

    def test_shared_session_in_check_and_run(self, mgr):
        meta = mgr.start("session_test", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="session_test_")
        mgr.end(meta)

        sessions_seen = []

        class SessionSpyProvider(FakeProvider):
            async def submit(self, requests, model_name, *, metadata=None, session=None):
                sessions_seen.append(("submit", session))
                return await super().submit(requests, model_name, metadata=metadata)

            async def get(self, provider_id, allow_missing=False, session=None):
                sessions_seen.append(("get", session))
                return await super().get(provider_id, allow_missing=allow_missing)

            async def fetch_results(self, batch, provider_id, session=None):
                sessions_seen.append(("fetch_results", session))
                return await super().fetch_results(batch, provider_id)

        spy = SessionSpyProvider()
        asyncio.run(mgr.run(meta, spy))
        assert len(sessions_seen) == 1
        sub_type, sub_session = sessions_seen[0]
        assert sub_type == "submit"
        assert isinstance(sub_session, aiohttp.ClientSession)

        sessions_seen.clear()
        asyncio.run(mgr.check(meta, spy, wait=True))
        assert len(sessions_seen) >= 2  # get + fetch_results
        check_sessions = [sess for _, sess in sessions_seen]
        assert all(isinstance(s, aiohttp.ClientSession) for s in check_sessions)
        # All calls within check(wait=True) shared the exact same ClientSession instance
        assert len(set(id(s) for s in check_sessions)) == 1


class TestBatchReviewFixes:
    """Tests for code review findings R1-R4 (Mistral fetch, JSONDecodeError, stuck submitting, cancel signature)."""

    def test_r1_real_mistral_provider_check(self, mgr, monkeypatch):
        meta = mgr.start("mistral_real", model_alias="devstral", model_name="mistral-large-latest",
                         provider="mistral", prompt="Translate to French")
        mgr.add_items(meta, ["hello world"], id_prefix="req_")
        mgr.end(meta)

        # Transition to submitted with provider ID
        meta["status"] = STATUS_SUBMITTED
        meta["provider_id"] = "job_mistral_xyz_789"
        mgr._write_meta(meta)

        real_provider = MistralBatchProvider(api_key="mock-mistral-key")

        async def fake_request(session, method, url, json_body=None, allow_missing_404=False):
            if "/batch/jobs/job_mistral_xyz_789" in url:
                return {
                    "id": "job_mistral_xyz_789",
                    "status": "SUCCESS",
                    "output_file": "file_output_123",
                    "total_requests": 1,
                    "succeeded_requests": 1,
                    "failed_requests": 0,
                }
            return None

        async def fake_download_text(url, session=None):
            assert "file_output_123" in url
            return json.dumps({
                "custom_id": "req_0001",
                "response": {
                    "status_code": 200,
                    "body": {"choices": [{"message": {"content": "bonjour le monde"}}]},
                },
            }) + "\n"

        monkeypatch.setattr(real_provider, "_request", fake_request)
        monkeypatch.setattr(real_provider, "_download_text", fake_download_text)

        checked = asyncio.run(mgr.check(meta, real_provider))
        assert checked["status"] == STATUS_COMPLETED
        assert checked["results_count"] == 1

        results = mgr.read_results(meta["batch_id"])
        assert len(results) == 1
        assert results[0]["custom_id"] == "req_0001"
        assert results[0]["content"] == "bonjour le monde"

    def test_r1_fetch_results_failure_reporting(self, mgr, capsys):
        meta = mgr.start("fetch_fail", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="fetch_fail_")
        mgr.end(meta)

        meta["status"] = STATUS_SUBMITTED
        meta["provider_id"] = "batch_fail_123"
        mgr._write_meta(meta)

        class FailingFetchProvider(FakeProvider):
            def __init__(self):
                super().__init__()
                self.fail_fetch = True

            async def fetch_results(self, batch, provider_id=None, session=None):
                if self.fail_fetch:
                    raise RuntimeError("Download socket disconnected during file transfer")
                return await super().fetch_results(batch, provider_id=provider_id, session=session)

        prov = FailingFetchProvider()
        prov.batches["batch_fail_123"] = {
            "id": "batch_fail_123",
            "status": "completed",
            "request_counts": {"total": 1, "completed": 1, "failed": 0},
            "results": [{"custom_id": "fetch_fail_0001", "response": {"status_code": 200, "body": {"choices": [{"message": {"content": "ok"}}]}}}],
        }

        checked = asyncio.run(mgr.check(meta, prov))
        out = capsys.readouterr().out
        assert "Error fetching batch results for 'fetch_fail'" in out
        assert "Download socket disconnected during file transfer" in out
        assert "Retry with '/batch check fetch_fail'" in out
        # results.jsonl must NOT be written and finalized_at must NOT be set
        results_path = os.path.join(mgr.batches_dir, meta["batch_id"], "results.jsonl")
        assert not os.path.exists(results_path)
        assert checked.get("finalized_at") is None

        # Now simulate retry succeeding
        prov.fail_fetch = False
        retry_checked = asyncio.run(mgr.check(checked, prov))
        assert os.path.exists(results_path)
        assert retry_checked["results_count"] == 1
        assert retry_checked.get("finalized_at") is not None

    def test_r2_json_decode_error_ambiguous(self, mgr):
        decode_err = None
        try:
            json.loads("<!DOCTYPE html><html><head><title>504 Gateway Time-out</title></head></html>")
        except json.JSONDecodeError as e:
            decode_err = e

        assert decode_err is not None
        assert isinstance(decode_err, ValueError)
        # JSONDecodeError and UnicodeDecodeError must be treated as ambiguous (False), not definitive rejection
        assert not BatchManager._is_definitive_submit_rejection(decode_err)
        unicode_err = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        assert not BatchManager._is_definitive_submit_rejection(unicode_err)
        # HTTP 4xx remains definitive
        class Http400Error(Exception):
            status = 400
        assert BatchManager._is_definitive_submit_rejection(Http400Error("bad request"))

        # Verify mgr.run leaves batch in STATUS_SUBMIT_UNKNOWN
        meta = mgr.start("json_err_test", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="json_err_")
        mgr.end(meta)

        class DecodeErrorProvider(FakeProvider):
            async def submit(self, requests, model_name, *, metadata=None, session=None):
                raise decode_err

        with pytest.raises(BatchError) as exc_info:
            asyncio.run(mgr.run(meta, DecodeErrorProvider()))

        assert "resubmit=true" in str(exc_info.value).lower()
        # Batch must stay in STATUS_SUBMIT_UNKNOWN to prevent duplicate submissions
        fresh_meta = mgr.resolve("json_err_test")
        assert fresh_meta["status"] == STATUS_SUBMIT_UNKNOWN

    def test_r3_submitting_batch_recovery_hints(self, mgr):
        meta = mgr.start("stuck_batch", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="stuck_")
        mgr.end(meta)

        meta["status"] = STATUS_SUBMIT_UNKNOWN
        meta["provider_id"] = None
        mgr._write_meta(meta)

        prov = FakeProvider()

        # check() raises with guidance mentioning dashboard, resubmit=true, and /batch purge
        with pytest.raises(BatchError) as exc_check:
            asyncio.run(mgr.check(meta, prov))
        assert "dashboard" in str(exc_check.value).lower()
        assert "resubmit=true" in str(exc_check.value)
        assert "/batch purge" in str(exc_check.value)

        # run() without resubmit=true raises with guidance
        with pytest.raises(BatchError) as exc_run:
            asyncio.run(mgr.run(meta, prov))
        assert "dashboard" in str(exc_run.value).lower()
        assert "resubmit=true" in str(exc_run.value)

        # run() with resubmit=true succeeds
        resubmitted = asyncio.run(mgr.run(meta, prov, resubmit=True))
        assert resubmitted["status"] == STATUS_SUBMITTED
        assert resubmitted["provider_id"] == "batch-0001"

    def test_r3_batch_remote_command(self, mgr, monkeypatch, capsys):
        from chatybot.commands.batch import _sc_remote
        from chatybot.commands.context import CommandContext

        class DummyApp:
            trace_raw_payload = False
            logging_manager = None
            class DummyConfigMgr:
                def list_batch_capable_models(self):
                    return ["batch_model"]
                def get_model_config(self, alias):
                    return {"vendor": "openrouter", "api_key": "MOCK_KEY", "batch": True}
            config_manager = DummyConfigMgr()

        monkeypatch.setenv("MOCK_KEY", "key-123")

        class RemoteListProvider(FakeProvider):
            async def list(self, session=None):
                return [
                    {"id": "batch_remote_001", "status": "completed", "model": "openai/gpt-4o", "created_at": 1700000000},
                    {"id": "batch_remote_002", "status": "in_progress", "model": "openai/gpt-4o-mini", "created_at": 1700000500},
                ]

        monkeypatch.setattr("chatybot.commands.batch.make_provider", lambda cfg, key, **kw: RemoteListProvider())

        # Create a local batch tracking batch_remote_001
        loc = mgr.start("my_local_run", model_alias="m", model_name="n", provider="openrouter")
        mgr.add_items(loc, ["item1"], id_prefix="ml_")
        mgr.end(loc)
        loc["provider_id"] = "batch_remote_001"
        mgr._write_meta(loc)

        ctx = CommandContext(buffer_manager=None, config_manager=DummyApp.config_manager,
                             i18n=None, session_store=None, app=DummyApp())

        from chatybot.commands.registry import CommandAction
        res = asyncio.run(_sc_remote(ctx, mgr, ""))
        assert res.action == CommandAction.HANDLED
        out = capsys.readouterr().out
        assert "[Remote Batches (openrouter) - org-wide account]" in out
        assert "batch_remote_001" in out
        assert "(local: my_local_run)" in out
        assert "batch_remote_002" in out
        assert "adopt=" not in out

    def test_r4_openrouter_cancel_with_id_raises_batch_error(self):
        prov = OpenRouterBatchProvider(api_key="mock-key")
        with pytest.raises(BatchError) as exc_info:
            asyncio.run(prov.cancel("any_provider_id"))
        assert "OpenRouter does not support cancelling" in str(exc_info.value)


class TestBatchReviewFixesItems8To13:
    def test_item8_reopen_with_different_model_refused(self, mgr, capsys):
        ctx = make_ctx(mgr)
        mistral_cfg = {"name": "mistral-large-latest", "vendor": "mistral", "batch": True, "api_key": "M_KEY"}
        ctx.config_manager.config["models"]["mistral_batch"] = mistral_cfg
        ctx.config_manager.get_model_config.side_effect = lambda a: ctx.config_manager.config["models"].get(a, mistral_cfg)
        ctx.config_manager.list_batch_capable_models.return_value = ["gptoss_batch", "mistral_batch"]

        # Create with gptoss_batch
        asyncio.run(run_cmd(ctx, "/batch start immut_m model=gptoss_batch"))
        meta = mgr.resolve("immut_m")
        assert meta["model_alias"] == "gptoss_batch"
        capsys.readouterr()

        # Reopen with different model is refused
        asyncio.run(run_cmd(ctx, "/batch start immut_m model=mistral_batch"))
        out = capsys.readouterr().out
        assert "Error: batch 'immut_m' uses model 'gptoss_batch'; clone it to change models." in out
        # Direct API also raises BatchError
        with pytest.raises(BatchError, match="clone it to change models"):
            mgr.start("immut_m", "mistral_batch", "mistral-large-latest", "mistral")

    def test_item9_pending_prompt_cleared_after_start_and_not_on_reopen(self, mgr, capsys):
        ctx = make_ctx(mgr)
        # Set pending prompt without open draft
        asyncio.run(run_cmd(ctx, '/batch prompt "One-time prompt"'))
        capsys.readouterr()

        # Consumed by first batch
        asyncio.run(run_cmd(ctx, "/batch start p_batch1"))
        b1 = mgr.resolve("p_batch1")
        assert b1["prompt"] == "One-time prompt"

        # Next batch must NOT get the consumed prompt
        asyncio.run(run_cmd(ctx, "/batch start p_batch2"))
        b2 = mgr.resolve("p_batch2")
        assert b2.get("prompt") is None

        # Reopening an existing batch must not overwrite its prompt with a pending prompt
        asyncio.run(run_cmd(ctx, "/batch start p_batch3"))
        asyncio.run(run_cmd(ctx, "/batch add item3"))
        asyncio.run(run_cmd(ctx, '/batch prompt "Original prompt"'))
        asyncio.run(run_cmd(ctx, '/batch end'))
        assert mgr.resolve("p_batch3")["prompt"] == "Original prompt"

        # Now set another pending prompt when no draft is open
        asyncio.run(run_cmd(ctx, '/batch prompt "Unrelated pending"'))
        # Reopen p_batch3
        asyncio.run(run_cmd(ctx, "/batch start p_batch3"))
        assert mgr.resolve("p_batch3")["prompt"] == "Original prompt"

    def test_item10_active_draft_targets_most_recently_touched(self, mgr):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start older_draft"))
        asyncio.run(run_cmd(ctx, "/batch add item_older_1"))

        asyncio.run(run_cmd(ctx, "/batch start newer_draft"))
        asyncio.run(run_cmd(ctx, "/batch add item_newer_1"))

        # Reopening older_draft must make it the active draft
        asyncio.run(run_cmd(ctx, "/batch start older_draft"))
        asyncio.run(run_cmd(ctx, "/batch add item_older_2"))

        # Verify item_older_2 went into older_draft, not newer_draft
        items_older = mgr.list_items(mgr.resolve("older_draft"))
        items_newer = mgr.list_items(mgr.resolve("newer_draft"))
        assert len(items_older) == 2
        assert len(items_newer) == 1
        assert items_older[1]["text"] == "item_older_2"

    def test_item11_apostrophes_and_spacing_preserved(self, mgr):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start text_batch"))
        raw_sentence = "I can't stop and won't stop now"
        asyncio.run(run_cmd(ctx, f"/batch add {raw_sentence}"))

        items = mgr.list_items(mgr.resolve("text_batch"))
        assert len(items) == 1
        assert items[0]["text"] == raw_sentence

        # Test spacing and option extraction together
        asyncio.run(run_cmd(ctx, "/batch add multiple   spaced    words id=custom_space_1"))
        items = mgr.list_items(mgr.resolve("text_batch"))
        assert len(items) == 2
        assert items[1]["custom_id"] == "custom_space_1"
        assert items[1]["text"] == "multiple   spaced    words"

        # Test edit preserving apostrophes and spacing
        asyncio.run(run_cmd(ctx, "/batch edit custom_space_1 replaced   can't   won't"))
        updated_item = mgr.show_item(mgr.resolve("text_batch"), "custom_space_1")
        assert updated_item["text"] == "replaced   can't   won't"

    def test_item12_dump_payload_after_reopen_shows_live_items(self, mgr):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start dump_reopen"))
        asyncio.run(run_cmd(ctx, "/batch add item1"))
        asyncio.run(run_cmd(ctx, "/batch end"))

        meta_sealed = mgr.resolve("dump_reopen")
        assert os.path.exists(mgr._requests_path(meta_sealed["batch_id"]))

        # Reopen and add another item
        asyncio.run(run_cmd(ctx, "/batch start dump_reopen"))
        meta_reopened = mgr.resolve("dump_reopen")
        assert meta_reopened["status"] == STATUS_DRAFT
        # Old requests.json was cleaned up
        assert not os.path.exists(mgr._requests_path(meta_reopened["batch_id"]))

        asyncio.run(run_cmd(ctx, "/batch add item2"))
        payload_str = mgr.dump_payload(meta_reopened)
        payload = json.loads(payload_str)
        texts = [req["body"]["messages"][-1]["content"] for req in payload["requests"]]
        assert texts == ["item1", "item2"]

    def test_item13_commands_batch_imports_json_and_computes_wire_bytes(self, mgr, capsys):
        import chatybot.commands.batch as batch_module
        assert hasattr(batch_module, "json")

        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start dump_calc"))
        asyncio.run(run_cmd(ctx, "/batch add test_calc_item"))
        capsys.readouterr()

        asyncio.run(run_cmd(ctx, "/batch dump dump_calc"))
        out = capsys.readouterr().out
        assert "Batch payload for 'dump_calc' (" in out
        assert "B):" in out


class TestBatchReviewFollowupFixes:
    def test_pre_network_validation_fails_with_submit_failed(self, mgr):
        # 1. Corrupt local requests.json fails before network POST, marked submit_failed
        meta = mgr.start("corrupt_req", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="cr_")
        mgr.end(meta)

        # Corrupt requests.json
        req_path = mgr._requests_path(meta["batch_id"])
        with open(req_path, "w", encoding="utf-8") as f:
            f.write("{invalid json")

        prov = FakeProvider()
        with pytest.raises(BatchError) as exc_info:
            asyncio.run(mgr.run(meta, prov))
        assert "submit_failed" in str(exc_info.value)
        assert "may have reached the provider" not in str(exc_info.value)
        fresh_meta = mgr.resolve("corrupt_req")
        assert fresh_meta["status"] == STATUS_SUBMIT_FAILED

    def test_mistral_inline_limit_fails_before_network(self, mgr):
        meta = mgr.start("mistral_over", model_alias="m", model_name="m", provider="mistral", prompt="p")
        # Fake a staged batch with > 10,000 items in requests.json
        meta["status"] = STATUS_STAGED
        mgr._write_meta(meta)
        req_path = mgr._requests_path(meta["batch_id"])
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump({"requests": [{"custom_id": f"id_{i}", "body": {}} for i in range(10_001)]}, f)

        prov = FakeProvider()
        with pytest.raises(BatchError) as exc_info:
            asyncio.run(mgr.run(meta, prov))
        assert "Inline batch limit exceeded" in str(exc_info.value)
        assert "submit_failed" in str(exc_info.value)
        assert "may have reached the provider" not in str(exc_info.value)
        assert mgr.resolve("mistral_over")["status"] == STATUS_SUBMIT_FAILED

    def test_non_utf8_response_treated_as_submit_unknown(self, mgr):
        meta = mgr.start("utf8_err", model_alias="m", model_name="m", provider="openrouter", prompt="p")
        mgr.add_items(meta, ["item1"], id_prefix="u8_")
        mgr.end(meta)

        class UnicodeDecodeErrorProvider(FakeProvider):
            async def submit(self, requests, model_name, *, metadata=None, session=None):
                raise UnicodeDecodeError("utf-8", b"\x80abc", 0, 1, "invalid start byte")

        with pytest.raises(BatchError) as exc_info:
            asyncio.run(mgr.run(meta, UnicodeDecodeErrorProvider()))
        assert "submit_unknown" in str(exc_info.value)
        assert "may have reached the provider" in str(exc_info.value)
        assert mgr.resolve("utf8_err")["status"] == STATUS_SUBMIT_UNKNOWN

    def test_batch_remote_active_draft_branch(self, mgr, monkeypatch, capsys):
        from chatybot.commands.batch import _sc_remote
        from chatybot.commands.context import CommandContext

        class DummyApp:
            trace_raw_payload = False
            logging_manager = None
            class DummyConfigMgr:
                def list_batch_capable_models(self):
                    return []
                def get_model_config(self, alias):
                    return {"vendor": "openrouter", "api_key": "MOCK_KEY", "batch": True}
            config_manager = DummyConfigMgr()

        monkeypatch.setenv("MOCK_KEY", "key-123")

        class RemoteProvider(FakeProvider):
            async def list(self, session=None):
                return [{"id": "r_100", "status": "completed", "model": "m", "created_at": 100}]

        monkeypatch.setattr("chatybot.commands.batch.make_provider", lambda cfg, key, **kw: RemoteProvider())

        # Start an active draft with openrouter provider
        draft = mgr.start("act_remote_draft", model_alias="m", model_name="m", provider="openrouter")
        mgr.add_items(draft, ["x"], id_prefix="ar_")

        ctx = CommandContext(buffer_manager=None, config_manager=DummyApp.config_manager,
                             i18n=None, session_store=None, app=DummyApp())

        from chatybot.commands.registry import CommandAction
        # With no target passed, _sc_remote must resolve via active draft
        res = asyncio.run(_sc_remote(ctx, mgr, ""))
        assert res.action == CommandAction.HANDLED
        out = capsys.readouterr().out
        assert "[Remote Batches (openrouter) - org-wide account]" in out
        assert "r_100" in out

    def test_quotes_preserved_when_not_exact_wrap(self, mgr):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start quote_test"))
        # Multiple quotes inside text
        text_with_quotes = '"Hello," she said, "goodbye."'
        asyncio.run(run_cmd(ctx, f"/batch add {text_with_quotes}"))

        # Single wrapping pair
        asyncio.run(run_cmd(ctx, '/batch add "Wrapped text exactly"'))

        items = mgr.list_items(mgr.resolve("quote_test"))
        assert len(items) == 2
        assert items[0]["text"] == text_with_quotes
        assert items[1]["text"] == "Wrapped text exactly"

    def test_options_inside_text_not_extracted(self, mgr):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start option_test"))
        # Option-like phrase in the middle of text
        sentence = "Set id=5 in the config file"
        asyncio.run(run_cmd(ctx, f"/batch add {sentence}"))

        # Leading and trailing options
        asyncio.run(run_cmd(ctx, "/batch add id=custom_tail Another sentence split=none"))

        items = mgr.list_items(mgr.resolve("option_test"))
        assert len(items) == 2
        assert items[0]["text"] == sentence
        assert items[0]["custom_id"] != "5"
        assert items[1]["custom_id"] == "custom_tail"
        assert items[1]["text"] == "Another sentence"

    def test_edit_preserves_trailing_batch_name_in_text(self, mgr):
        ctx = make_ctx(mgr)
        asyncio.run(run_cmd(ctx, "/batch start dufu"))
        asyncio.run(run_cmd(ctx, "/batch add original text id=dufu_0001"))

        # Trailing word matching batch name must NOT be stripped
        asyncio.run(run_cmd(ctx, "/batch edit dufu_0001 Write a poem in the style of dufu"))
        item = mgr.show_item(mgr.resolve("dufu"), "dufu_0001")
        assert item["text"] == "Write a poem in the style of dufu"

        # Explicit batch name before text
        asyncio.run(run_cmd(ctx, "/batch edit dufu_0001 dufu Another poem for dufu"))
        item = mgr.show_item(mgr.resolve("dufu"), "dufu_0001")
        assert item["text"] == "Another poem for dufu"

        # Explicit batch= option
        asyncio.run(run_cmd(ctx, "/batch edit dufu_0001 batch=dufu Third poem ending in dufu"))
        item = mgr.show_item(mgr.resolve("dufu"), "dufu_0001")
        assert item["text"] == "Third poem ending in dufu"

    def test_list_index_constant_time_order(self, mgr):
        # Create b1, b2, update b1, update b2, update b1
        meta1 = mgr.start("b1", model_alias="m", model_name="m", provider="openrouter")
        meta2 = mgr.start("b2", model_alias="m", model_name="m", provider="openrouter")
        mgr.set_prompt(meta1, "p1")
        mgr.set_prompt(meta2, "p2")
        mgr.set_prompt(meta1, "p1_updated")

        idx = mgr.list_index()
        # Most recently touched batch should be last
        assert idx[-1]["batch_id"] == meta1["batch_id"]
        assert idx[-2]["batch_id"] == meta2["batch_id"]



