"""Time-Travel Agentic Loop Replay engine.

Reconstructs the ``temp_history`` message array the agentic tool loop
(``execute_tool_loop``) built and sent to the model at each step of a loop,
runs ``ContextLimiter.truncate_messages_verbose()``, and produces rich
diagnostics on how tool results inflated the context window and when
truncation would have evicted messages.

Parallel to ``session_replayer.py`` (context replay) but scoped to the
agentic loop steps within a single session turn.

The assistant tool-call messages are NOT stored in the agentic_loop records
(only the tool name, arguments, result, status, timing are). They are
reconstructed here as JSON code blocks — an approximation of what the model
emitted. The tool-result user messages are reconstructed exactly from the
stored records, matching the format used in ``execute_tool_loop``.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from chatybot.context_limit import ContextLimiter, TruncationDiagnostic
from chatybot.session_replayer import SessionReplayer, clean_thinking_tokens


def _format_tool_call_message(tool: str, arguments: Dict[str, Any]) -> str:
    """Approximate the assistant tool-call message the model produced.

    The exact text the model emitted (markdown fences, Gemma XML syntax, etc.)
    is not stored per step, so we reconstruct a canonical JSON code block.
    """
    return f"```json\n{json.dumps({'tool': tool, 'arguments': arguments}, ensure_ascii=False)}\n```"


def _format_tool_result_message(tool: str, arguments: Dict[str, Any], result: str) -> str:
    """Reconstruct the tool-result user message exactly as execute_tool_loop builds it."""
    args_str = json.dumps(arguments, ensure_ascii=False)
    return f"Tool execution results:\nTool: {tool}\nArguments: {args_str}\nResult: {result}"


def reconstruct_agentic_messages(
    session_turns: List[Dict[str, Any]],
    agentic_turn_id: int,
    system_prompt: str,
    up_to_step: int,
) -> List[Dict[str, Any]]:
    """Reconstruct the temp_history message array the agentic loop saw at ``up_to_step``.

    Args:
        session_turns: all LLM turns in the session (command turns ignored).
        agentic_turn_id: turn_id of the turn whose agentic_loop we replay.
        system_prompt: reconstructed system prompt to prepend (may be empty).
        up_to_step: 1-based step index within the loop. Step 0 means no tool
            steps have run yet (just system + prior turns + the prompt).

    The reconstruction mirrors execute_tool_loop (chatybot_app.py:3903-4054):
      1. system prompt (added by chat_completion, included here for accuracy)
      2. prior session turns as user/assistant pairs (chat_history[:-1])
      3. the agentic turn's prompt (chat_history[-1][0])
      4. for each step 1..up_to_step: assistant tool-call + tool-result user msg
    """
    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Locate the agentic turn
    agentic_turn: Optional[Dict[str, Any]] = None
    for t in session_turns:
        if t.get("turn_id") == agentic_turn_id:
            agentic_turn = t
            break

    # Prior session turns (those before the agentic turn), as user/assistant pairs
    for t in session_turns:
        if t.get("turn_id") == agentic_turn_id:
            break
        if t.get("type") == "command":
            continue
        if "prompt" not in t:
            continue
        messages.append({"role": "user", "content": t.get("prompt", "")})
        messages.append({"role": "assistant", "content": clean_thinking_tokens(t.get("response", ""))})

    if agentic_turn is None:
        return messages

    # The agentic turn's prompt (the initial_prompt the loop operated on)
    messages.append({"role": "user", "content": agentic_turn.get("prompt", "")})

    loop = agentic_turn.get("agentic_loop") or []
    if not isinstance(loop, list):
        loop = []
    steps = loop[:max(0, up_to_step)]

    for rec in steps:
        if not isinstance(rec, dict):
            continue
        tool = rec.get("tool", "unknown")
        arguments = rec.get("arguments", {}) or {}
        result = rec.get("result", "")
        messages.append({"role": "assistant", "content": _format_tool_call_message(tool, arguments)})
        messages.append({"role": "user", "content": _format_tool_result_message(tool, arguments, result)})

    return messages


@dataclass
class AgenticStepSnapshot:
    """Full reconstructed + truncated state at a single agentic loop step."""
    step: int                  # 1-based step within the loop (0 = pre-loop baseline)
    turn_id: int               # session turn this loop belongs to
    tool: str                  # tool invoked at this step ("" for step 0)
    status: str                # "success"/"error"/"" for step 0
    message_count: int
    total_tokens: int          # before truncation
    truncated_tokens: int      # after truncation
    did_truncate: bool
    evicted_indices: List[int]
    anchors_alone_exceed_limit: bool
    messages: List[Dict[str, Any]]
    truncated_messages: List[Dict[str, Any]]
    duration_ms: float


@dataclass
class AgenticStepDiff:
    """Comparison between two steps within an agentic loop."""
    step_a: int
    step_b: int
    added_messages: List[Dict[str, Any]]
    newly_evicted: List[Dict[str, Any]]
    token_delta: int
    truncation_evicted_delta: int
    anchor_overflow_changed: bool
    snapshot_a: AgenticStepSnapshot
    snapshot_b: AgenticStepSnapshot


class AgenticReplayer:
    """Replay engine for agentic tool loops.

    Reuses ``SessionReplayer`` for session loading and system-prompt
    reconstruction so the loop context matches what context replay produces.
    """

    def __init__(self, app: Any):
        self.app = app
        self._session_replayer = SessionReplayer(app)
        self.context_limiter: ContextLimiter = getattr(app, "context_limiter", None) or ContextLimiter()

    # -- session / turn resolution --------------------------------------

    def _load_turns(self, target: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        return self._session_replayer.load(target)

    def _find_agentic_turn(
        self, turns: List[Dict[str, Any]], turn_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        llm_turns = [t for t in turns if t.get("type") != "command" and "prompt" in t]
        if turn_id is not None:
            for t in llm_turns:
                if t.get("turn_id") == turn_id:
                    return t
            return None
        # Default: the most recent turn that has an agentic_loop
        for t in reversed(llm_turns):
            al = t.get("agentic_loop")
            if isinstance(al, list) and al:
                return t
        return None

    # -- snapshots -------------------------------------------------------

    def snapshot_at_step(
        self,
        turns: List[Dict[str, Any]],
        agentic_turn_id: int,
        system_prompt: str,
        step: int,
        limit: Optional[int] = None,
    ) -> Optional[AgenticStepSnapshot]:
        """Build an AgenticStepSnapshot for the given step (0 = pre-loop baseline)."""
        agentic_turn = self._find_agentic_turn(turns, agentic_turn_id)
        if agentic_turn is None:
            return None
        loop = agentic_turn.get("agentic_loop") or []
        if not isinstance(loop, list):
            loop = []
        if step < 0 or step > len(loop):
            return None

        messages = reconstruct_agentic_messages(turns, agentic_turn_id, system_prompt, step)
        diag = self.context_limiter.truncate_messages_verbose(messages, limit=limit)

        tool = ""
        status = ""
        duration_ms = 0.0
        if step >= 1 and step <= len(loop):
            rec = loop[step - 1]
            if isinstance(rec, dict):
                tool = rec.get("tool", "")
                status = rec.get("status", "")
                duration_ms = float(rec.get("duration_ms", 0) or 0)

        return AgenticStepSnapshot(
            step=step,
            turn_id=agentic_turn_id,
            tool=tool,
            status=status,
            message_count=len(messages),
            total_tokens=diag.original_tokens,
            truncated_tokens=diag.truncated_tokens,
            did_truncate=diag.did_truncate,
            evicted_indices=diag.evicted_indices,
            anchors_alone_exceed_limit=diag.anchors_alone_exceed_limit,
            messages=messages,
            truncated_messages=diag.truncated_messages,
            duration_ms=duration_ms,
        )

    def replay_loop(
        self,
        target: str,
        turn_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[AgenticStepSnapshot]:
        """Produce a snapshot for every step of the loop (including step 0 baseline)."""
        meta, turns = self._load_turns(target)
        system_prompt = self._session_replayer.reconstruct_system_prompt(meta, turns)
        agentic_turn = self._find_agentic_turn(turns, turn_id)
        if agentic_turn is None:
            return []
        agentic_turn_id = agentic_turn.get("turn_id")
        loop = agentic_turn.get("agentic_loop") or []
        if not isinstance(loop, list):
            loop = []

        snapshots: List[AgenticStepSnapshot] = []
        # Step 0 = pre-loop baseline (system + prior turns + prompt, no tool steps)
        snap0 = self.snapshot_at_step(turns, agentic_turn_id, system_prompt, 0, limit=limit)
        if snap0 is not None:
            snapshots.append(snap0)
        for i in range(1, len(loop) + 1):
            snap = self.snapshot_at_step(turns, agentic_turn_id, system_prompt, i, limit=limit)
            if snap is not None:
                snapshots.append(snap)
        return snapshots

    def diff_steps(
        self,
        target: str,
        turn_id: Optional[int],
        step_a: int,
        step_b: int,
        limit: Optional[int] = None,
    ) -> Optional[AgenticStepDiff]:
        """Compare the reconstructed context at step_a vs step_b of a loop."""
        meta, turns = self._load_turns(target)
        system_prompt = self._session_replayer.reconstruct_system_prompt(meta, turns)
        agentic_turn = self._find_agentic_turn(turns, turn_id)
        if agentic_turn is None:
            return None
        agentic_turn_id = agentic_turn.get("turn_id")
        snap_a = self.snapshot_at_step(turns, agentic_turn_id, system_prompt, step_a, limit=limit)
        snap_b = self.snapshot_at_step(turns, agentic_turn_id, system_prompt, step_b, limit=limit)
        if snap_a is None or snap_b is None:
            return None

        a_keys = {(m.get("role"), m.get("content")) for m in snap_a.messages}
        added = [m for m in snap_b.messages if (m.get("role"), m.get("content")) not in a_keys]

        b_surviving_keys = {(m.get("role"), m.get("content")) for m in snap_b.truncated_messages}
        b_all_keys = {(m.get("role"), m.get("content")) for m in snap_b.messages}
        newly_evicted = [
            m for m in snap_a.messages
            if (m.get("role"), m.get("content")) not in b_surviving_keys
            and (m.get("role"), m.get("content")) not in b_all_keys
        ]

        return AgenticStepDiff(
            step_a=step_a,
            step_b=step_b,
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
