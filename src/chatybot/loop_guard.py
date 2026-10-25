"""
Tool-Loop Guard
Detects an agentic tool loop that keeps repeating the same tool call and getting
the same result back, which some models do until max_turns runs out.

Rules (per tool loop):
- A call is identified by tool name + normalized arguments (unwrap_tool_args,
  sorted JSON), so wrapped and bare arguments are the same call.
- A repeat only counts when the result is also the same. Re-running `git status`
  after a commit, or re-reading a file after a write, returns a different
  result and is never flagged.
- Repeats are counted over the last `window` executed calls, so alternating
  loops (A, B, A, B, ...) are caught as well as consecutive ones.
- The same call twice in one turn (parallel calls) is not executed twice.
- When a call has already returned the same result `repeats - 1` times, the
  next request is not executed; the model gets a nudge instead. If it asks for
  the same call again with nothing else run in between, or the call is still
  returning the same result after one more try, the loop is stopped.

The guard only ever withholds calls. It never executes anything itself and
never skips the security check of a call it lets through.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from typing import Any

from chatybot.tool_args import unwrap_tool_args

RUN = "run"
DUPLICATE = "duplicate"
NUDGE = "nudge"
STOP = "stop"

# Tools whose repeats are expected (each call asks a person something).
EXEMPT_TOOLS = frozenset({"ask_user"})


def call_signature(tool: str, arguments: Any) -> str:
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            if isinstance(parsed, dict):
                arguments = parsed
        except Exception:
            pass
    if isinstance(arguments, dict):
        norm = unwrap_tool_args(arguments)
        return f"{tool}:{json.dumps(norm, sort_keys=True, default=str)}"
    return f"{tool}:{arguments}"


def result_digest(result: Any) -> str:
    return hashlib.sha256(str(result).encode("utf-8", "replace")).hexdigest()


@dataclass
class GuardDecision:
    action: str  # RUN | DUPLICATE | NUDGE | STOP
    message: str = ""
    repeats: int = 0


class LoopGuard:
    def __init__(self, repeats: int = 3, window: int = 8, enabled: bool = True):
        self.enabled = bool(enabled)
        self.repeats = max(2, int(repeats))
        self.window = max(2, int(window))
        self._history: deque[tuple[str, str]] = deque(maxlen=self.window)
        self._executed = 0
        self._nudged_at: dict[str, int] = {}  # signature -> executed count when nudged
        self._retried: set[str] = set()
        self._turn: dict[str, int] = {}  # signature -> 1-based position in the current turn

    def start_turn(self) -> None:
        self._turn = {}

    def _identical_results(self, sig: str) -> int:
        """How many times this call returned its most recent result, within the window."""
        digests = [d for s, d in self._history if s == sig]
        return digests.count(digests[-1]) if digests else 0

    def check(self, tool: str, arguments: Any) -> GuardDecision:
        """Decide, before dispatch, whether this call should run."""
        if not self.enabled or not tool or tool in EXEMPT_TOOLS:
            return GuardDecision(RUN)
        sig = call_signature(tool, arguments)

        if sig in self._turn:
            return GuardDecision(
                DUPLICATE,
                f"Loop guard: this is the same '{tool}' call as call #{self._turn[sig]} in this turn; "
                "it was not executed again. Use that call's result.",
            )
        self._turn[sig] = len(self._turn) + 1

        n = self._identical_results(sig)
        if n < self.repeats - 1:
            return GuardDecision(RUN, repeats=n)

        nudged_at = self._nudged_at.get(sig)
        if nudged_at is None:
            self._nudged_at[sig] = self._executed
            return GuardDecision(
                NUDGE,
                f"Loop guard: '{tool}' was already called with these arguments {n} times in this loop "
                "and returned the same result each time. It was not executed again. Do not repeat it: "
                "use the earlier result, try a different approach, or give your final answer.",
                repeats=n,
            )
        if self._executed == nudged_at or sig in self._retried:
            return GuardDecision(
                STOP,
                f"Loop guard stopped the tool loop: the model kept requesting '{tool}' with the same "
                f"arguments, which returned the same result {n} times.",
                repeats=n,
            )
        # Other tools ran since the nudge, so the result may have changed: allow one more try.
        self._retried.add(sig)
        return GuardDecision(RUN, repeats=n)

    def record(self, tool: str, arguments: Any, result: Any) -> None:
        """Record an executed call and its result (not for withheld or security-refused calls)."""
        if not self.enabled or not tool or tool in EXEMPT_TOOLS:
            return
        self._executed += 1
        sig, digest = call_signature(tool, arguments), result_digest(result)
        previous = [d for s, d in self._history if s == sig]
        if previous and previous[-1] != digest:
            # The result changed, so the call is making progress: forget any earlier nudge.
            self._nudged_at.pop(sig, None)
            self._retried.discard(sig)
        self._history.append((sig, digest))
