"""Time-Travel Context Replay engine.

Reconstructs the exact message array [{"role": "...", "content": "..."}] as it
was sent to the model at any turn in a session, runs
ContextLimiter.truncate_messages_verbose(), and produces rich diagnostics on
evicted messages, anchor overflows, and token deltas.

The system prompt is reconstructed from current config as an approximation —
the exact prompt at session time is not stored per turn (see
reconstruct_system_prompt).
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from chatybot.context_limit import ContextLimiter, TruncationDiagnostic


def clean_thinking_tokens(text: str) -> str:
    """Safely strip thinking tags from assistant responses."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<thought>.*?</thought>\s*", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def reconstruct_messages_from_turns(
    turns: List[Dict[str, Any]],
    system_prompt: str,
    up_to_turn_id: Optional[int] = None,
    include_current: bool = True,
) -> List[Dict[str, Any]]:
    """Reconstruct the message list for LLM context at a specific turn.

    Args:
        turns: full list of session turn records (command turns are ignored).
        system_prompt: reconstructed system prompt to prepend (may be empty).
        up_to_turn_id: if set, only include LLM turns up to and including the
            turn whose ``turn_id`` matches this value.
        include_current: when False, the final turn's assistant response is
            also appended (i.e. reconstruct the context the model received
            before it produced its answer). When True (default), the final
            turn stops at the user prompt — the context the model saw.
    """
    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    llm_turns = [t for t in turns if t.get("type") != "command" and "prompt" in t]
    if up_to_turn_id is not None:
        target_idx = None
        for idx, t in enumerate(llm_turns):
            if t.get("turn_id") == up_to_turn_id:
                target_idx = idx
                break
        if target_idx is not None:
            llm_turns = llm_turns[: target_idx + 1]

    if not llm_turns:
        return messages

    for turn in llm_turns[:-1]:
        messages.append({"role": "user", "content": turn.get("prompt", "")})
        resp = turn.get("response", "")
        messages.append({"role": "assistant", "content": clean_thinking_tokens(resp)})

    last_turn = llm_turns[-1]
    messages.append({"role": "user", "content": last_turn.get("prompt", "")})
    if not include_current:
        resp = last_turn.get("response", "")
        messages.append({"role": "assistant", "content": clean_thinking_tokens(resp)})

    return messages


@dataclass
class TurnSnapshot:
    """Full reconstructed + truncated state at a single turn."""
    turn_id: int
    message_count: int          # messages in the reconstructed list
    total_tokens: int           # before truncation
    truncated_tokens: int       # after truncation (if applied)
    did_truncate: bool
    evicted_indices: List[int]  # original 0-based indices removed by truncation
    anchors_alone_exceed_limit: bool
    messages: List[Dict[str, Any]]        # full reconstructed message list
    truncated_messages: List[Dict[str, Any]]  # after truncation
    is_tool_turn: bool
    model_alias: Optional[str]


@dataclass
class TurnDiff:
    """Comparison between two turns."""
    turn_a: int
    turn_b: int
    added_messages: List[Dict[str, Any]]          # present at turn_b but not turn_a
    newly_evicted: List[Dict[str, Any]]           # survived at turn_a but evicted by turn_b
    token_delta: int                              # total_tokens_b - total_tokens_a (pre-truncation)
    truncation_evicted_delta: int                 # evicted_count_b - evicted_count_a
    anchor_overflow_changed: bool                 # True if overflow state differs between turns
    snapshot_a: TurnSnapshot
    snapshot_b: TurnSnapshot


class SessionReplayer:
    """Replay engine: loads sessions, reconstructs messages, runs verbose truncation.

    Constructed with the ChatybotApp (or any object exposing the attributes
    used below) so the system prompt can be approximated from live config.
    """

    def __init__(self, app: Any):
        self.app = app
        self.config_manager = getattr(app, "config_manager", None)
        self.context_limiter: ContextLimiter = getattr(app, "context_limiter", None) or ContextLimiter()

    # -- session loading -------------------------------------------------

    def load(self, target: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Load session meta + turns via the app's session store."""
        store = self.app._get_session_store()
        return store.load_session(target)

    # -- system prompt reconstruction -----------------------------------

    def reconstruct_system_prompt(self, meta: dict, turns: list) -> str:
        """Reconstruct the system prompt that would have been active.

        Approximate — the exact prompt at session time is not stored per
        turn. Built to mirror chat_completion (chatybot_app.py:1249-1319):
          1. config_manager.system_message (base)
          2. Tool context + agentic instructions (if any turn has agentic_loop)
          3. Reasoning-mode suffix ("detailed thinking off")
          4. Model-specific suffixes (gemma4)

        The result is flagged as approximate in the CLI output.
        """
        base = ""
        if self.config_manager is not None:
            base = getattr(self.config_manager, "system_message", "") or ""

        parts: List[str] = [base]
        has_tool_turns = any(t.get("agentic_loop") for t in turns)
        if has_tool_turns:
            tool_ctx = self._get_tool_context()
            if tool_ctx:
                parts.append(tool_ctx)
            agentic = self._get_agentic_instructions()
            if agentic:
                parts.append(agentic)

        model_alias = meta.get("model_alias", "") or ""
        suffix = self._get_model_suffix(model_alias)
        if suffix:
            parts.append(suffix)

        return "\n".join(p for p in parts if p)

    def _get_tool_context(self) -> str:
        app = self.app
        return getattr(app, "live_tool_context", "") or getattr(app, "tool_context", "") or ""

    def _get_agentic_instructions(self) -> str:
        app = self.app
        instr = (
            getattr(app, "live_agentic_instructions", "")
            or getattr(app, "agentic_instructions", "")
            or getattr(app, "default_agentic_instructions", "")
            or ""
        )
        return instr

    def _get_model_suffix(self, model_alias: str) -> str:
        """Return a system-prompt suffix for special models, mirroring
        chat_completion reasoning/gemma4 handling. Returns "" for normal models.
        """
        app = self.app
        reasoning_mode = bool(getattr(app, "reasoning_mode", True))
        thoughtstyle = getattr(app, "thoughtstyle", "none")
        model_name = ""
        if self.config_manager is not None and model_alias:
            try:
                model_name = self.config_manager.get_model_config(model_alias).get("name", "")
            except Exception:
                model_name = ""

        name_lower = (model_name or "").lower()
        is_reasoning_model = any(k in name_lower for k in ("nvidia", "qwen", "glm"))
        suffix = ""
        if is_reasoning_model and not reasoning_mode:
            suffix = (suffix + "\ndetailed thinking off") if suffix else "detailed thinking off"

        is_gemma_4 = "gemma4" in name_lower
        if not reasoning_mode and thoughtstyle == "gemma4" and is_gemma_4:
            gemma4_suffix = " disable reasoning and thought. </thought off>"
            suffix = (suffix + gemma4_suffix) if suffix else gemma4_suffix
        return suffix

    # -- snapshots -------------------------------------------------------

    def snapshot_at_turn(
        self,
        turns: List[Dict[str, Any]],
        system_prompt: str,
        turn_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Optional[TurnSnapshot]:
        """Build a TurnSnapshot for the turn matching ``turn_id`` (or the last)."""
        llm_turns = [t for t in turns if t.get("type") != "command" and "prompt" in t]
        if not llm_turns:
            return None

        target_turn = None
        if turn_id is None:
            target_turn = llm_turns[-1]
        else:
            for t in llm_turns:
                if t.get("turn_id") == turn_id:
                    target_turn = t
                    break
        if target_turn is None:
            return None

        messages = reconstruct_messages_from_turns(
            turns, system_prompt, up_to_turn_id=target_turn.get("turn_id"),
            include_current=True,
        )
        diag = self.context_limiter.truncate_messages_verbose(messages, limit=limit)

        return TurnSnapshot(
            turn_id=target_turn.get("turn_id", 0),
            message_count=len(messages),
            total_tokens=diag.original_tokens,
            truncated_tokens=diag.truncated_tokens,
            did_truncate=diag.did_truncate,
            evicted_indices=diag.evicted_indices,
            anchors_alone_exceed_limit=diag.anchors_alone_exceed_limit,
            messages=messages,
            truncated_messages=diag.truncated_messages,
            is_tool_turn=bool(target_turn.get("agentic_loop")),
            model_alias=target_turn.get("model_alias"),
        )

    def replay_all(
        self,
        target: str,
        limit: Optional[int] = None,
    ) -> List[TurnSnapshot]:
        """Produce a snapshot for every LLM turn in the session."""
        meta, turns = self.load(target)
        system_prompt = self.reconstruct_system_prompt(meta, turns)
        llm_turns = [t for t in turns if t.get("type") != "command" and "prompt" in t]
        snapshots: List[TurnSnapshot] = []
        for t in llm_turns:
            snap = self.snapshot_at_turn(turns, system_prompt, turn_id=t.get("turn_id"), limit=limit)
            if snap is not None:
                snapshots.append(snap)
        return snapshots

    def diff_turns(
        self,
        target: str,
        turn_a: int,
        turn_b: int,
        limit: Optional[int] = None,
    ) -> Optional[TurnDiff]:
        """Compare the reconstructed context at turn_a vs turn_b."""
        meta, turns = self.load(target)
        system_prompt = self.reconstruct_system_prompt(meta, turns)
        snap_a = self.snapshot_at_turn(turns, system_prompt, turn_id=turn_a, limit=limit)
        snap_b = self.snapshot_at_turn(turns, system_prompt, turn_id=turn_b, limit=limit)
        if snap_a is None or snap_b is None:
            return None

        # Messages present at b but not a (by role+content identity)
        a_keys = {(m.get("role"), m.get("content")) for m in snap_a.messages}
        added = [m for m in snap_b.messages if (m.get("role"), m.get("content")) not in a_keys]

        # Messages that survived at a but were evicted by b's truncation
        b_surviving_keys = {(m.get("role"), m.get("content")) for m in snap_b.truncated_messages}
        newly_evicted = [
            m for m in snap_a.messages
            if (m.get("role"), m.get("content")) not in b_surviving_keys
            and (m.get("role"), m.get("content")) not in {
                (mm.get("role"), mm.get("content")) for mm in snap_b.messages
            }
        ]

        return TurnDiff(
            turn_a=turn_a,
            turn_b=turn_b,
            added_messages=added,
            newly_evicted=newly_evicted,
            token_delta=snap_b.total_tokens - snap_a.total_tokens,
            truncation_evicted_delta=len(snap_b.evicted_indices) - len(snap_a.evicted_indices),
            anchor_overflow_changed=(
                snap_a.anchors_alone_exceed_limit != snap_b.anchors_alone_exceed_limit
            ),
            snapshot_a=snap_a,
            snapshot_b=snap_b,
        )
