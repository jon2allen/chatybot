"""Time-Travel Context Replay commands.

Provides ``/replay`` as a top-level alias for ``/session replay`` and hosts the
shared ``handle_replay_command`` helper used by both entry points.
"""

import dataclasses
from typing import List, Optional

from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext
from chatybot.session_replayer import SessionReplayer

_KEYWORDS = {"at", "diff", "step"}


def _parse_replay_tokens(tokens: List[str], ctx: CommandContext):
    """Parse raw replay tokens into (target, mode, mode_args, limit, target_var).

    Returns (target, mode, mode_args, limit, target_var) where mode is one of
    "summary", "at", "diff", "step".
    """
    app = ctx.app
    limit: Optional[int] = None
    target: Optional[str] = None
    mode = "summary"
    mode_args: List[str] = []
    target_var: Optional[str] = None

    # Strip and collect limit= overrides and var=/target= anywhere in the token stream
    filtered: List[str] = []
    for tok in tokens:
        if tok.lower().startswith("limit="):
            try:
                limit = int(tok.split("=", 1)[1])
            except ValueError:
                pass
        elif tok.lower().startswith("var="):
            target_var = tok[4:].strip().lstrip("$")
        elif tok.lower().startswith("target="):
            target_var = tok[7:].strip().lstrip("$")
        else:
            filtered.append(tok)

    if filtered:
        first = filtered[0]
        if first.lower() not in _KEYWORDS:
            # First token is a session id / name
            target = first
            rest = filtered[1:]
        else:
            rest = filtered
    else:
        rest = []

    if rest:
        head = rest[0].lower()
        if head == "at":
            mode = "at"
            mode_args = rest[1:]
        elif head == "diff":
            mode = "diff"
            mode_args = rest[1:]
        elif head == "step":
            mode = "step"
            mode_args = rest[1:]

    if target is None:
        target = app.active_session_id or app.active_session_name

    return target, mode, mode_args, limit, target_var


def _preview(text: str, width: int = 60) -> str:
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    text = text.replace("\n", " ").strip()
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _render_summary(snapshots) -> None:
    if not snapshots:
        print("No LLM turns found in this session.")
        return
    print("\n" + "=" * 78)
    print("SESSION REPLAY — SUMMARY TIMELINE")
    header = f"{'Turn':<6}{'Msgs':<6}{'Uncut Tok':<12}{'Trunc Tok':<12}{'Evicted':<9}{'AnchorWarn':<11}"
    print(header)
    print("-" * 78)
    for s in snapshots:
        warn = "YES" if s.anchors_alone_exceed_limit else "-"
        print(
            f"{s.turn_id:<6}{s.message_count:<6}{s.total_tokens:<12}"
            f"{s.truncated_tokens:<12}{len(s.evicted_indices):<9}{warn:<11}"
        )
    print("=" * 78)
    print("Notes / Column Legend:")
    print("  • Turn:       Session interaction turn number")
    print("  • Msgs:       Total messages in prompt array before truncation")
    print("  • Uncut Tok:  Raw token count of prompt array before truncation")
    print("  • Trunc Tok:  Token count after auto-truncation/eviction to fit limit")
    print("  • Evicted:    Number of older intermediate messages dropped from prompt")
    print("  • AnchorWarn: YES if system + initial user anchors exceed context limit")
    print("")


def _render_at(snapshot, system_prompt: str) -> None:
    print("\n" + "=" * 78)
    print(f"TURN {snapshot.turn_id} — RECONSTRUCTED CONTEXT")
    print("=" * 78)
    print(f"Messages: {snapshot.message_count}  |  Uncut tokens: {snapshot.total_tokens}  "
          f"|  Truncated tokens: {snapshot.truncated_tokens}")
    print(f"Evicted indices: {snapshot.evicted_indices if snapshot.evicted_indices else 'none'}")
    print(f"Anchor overflow: {'YES (anchors alone exceed limit)' if snapshot.anchors_alone_exceed_limit else 'no'}")
    print(f"Tool turn: {'yes' if snapshot.is_tool_turn else 'no'}  |  Model: {snapshot.model_alias or 'default'}")
    print(f"System prompt (approximate): {_preview(system_prompt, 70)}")
    print("-" * 78)

    surviving_keys = {(m.get("role"), m.get("content")) for m in snapshot.truncated_messages}
    evicted_set = set(snapshot.evicted_indices)

    # Determine anchor indices (system at 0 if present, first user after it)
    anchor_idxs = set()
    rem_idx = 0
    if len(snapshot.messages) > 0 and snapshot.messages[0].get("role") == "system":
        anchor_idxs.add(0)
        rem_idx = 1
    if len(snapshot.messages) > rem_idx and snapshot.messages[rem_idx].get("role") == "user":
        anchor_idxs.add(rem_idx)

    for i, m in enumerate(snapshot.messages):
        role = m.get("role", "?")
        content = m.get("content", "")
        tokens = 0
        # cheap per-message token estimate via the limiter is not available
        # here without the limiter; show a char count proxy instead.
        clen = len(content) if isinstance(content, str) else 0
        tags = []
        if i in anchor_idxs:
            tags.append("ANCHOR")
        if i in evicted_set:
            tags.append("EVICTED")
        elif (m.get("role"), m.get("content")) not in surviving_keys and snapshot.did_truncate:
            tags.append("EVICTED")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"  [{i}] {role:<10} ({clen} chars){tag_str}")
        print(f"      {_preview(content, 72)}")
    print("=" * 78 + "\n")


def _render_diff(diff) -> None:
    print("\n" + "=" * 78)
    print(f"DIFF: TURN {diff.turn_a} -> TURN {diff.turn_b}")
    print("=" * 78)
    print(f"Token delta (pre-truncation): {diff.token_delta:+d}")
    print(f"Evicted-count delta: {diff.truncation_evicted_delta:+d}")
    print(f"Anchor overflow changed: {'yes' if diff.anchor_overflow_changed else 'no'}")
    print("-" * 78)

    print(f"Added messages ({len(diff.added_messages)}):")
    if diff.added_messages:
        for m in diff.added_messages:
            print(f"  + {m.get('role', '?'):<10} {_preview(m.get('content', ''), 64)}")
    else:
        print("  (none)")

    print(f"Newly evicted messages ({len(diff.newly_evicted)}):")
    if diff.newly_evicted:
        for m in diff.newly_evicted:
            print(f"  - {m.get('role', '?'):<10} {_preview(m.get('content', ''), 64)}")
    else:
        print("  (none)")
    print("=" * 78 + "\n")


async def handle_replay_command(ctx: CommandContext, raw_tokens: List[str]) -> CommandResult:
    """Shared replay handler invoked by /session replay and /replay."""
    app = ctx.app
    target, mode, mode_args, limit, target_var = _parse_replay_tokens(raw_tokens, ctx)

    if not target:
        print("No active session. Usage: /session replay [<id>] [at <N> | diff <A> <B> | step] [limit=<N>]")
        return CommandResult.ok()

    replayer = SessionReplayer(app)
    try:
        meta, turns = replayer.load(target)
    except Exception as e:
        print(f"Error: could not load session '{target}': {e}")
        return CommandResult.ok()

    system_prompt = replayer.reconstruct_system_prompt(meta, turns)
    llm_turns = [t for t in turns if t.get("type") != "command" and "prompt" in t]
    if not llm_turns:
        print("No LLM turns in this session to replay.")
        return CommandResult.ok()

    if mode == "summary":
        snapshots = replayer.replay_all(target, limit=limit, turns=turns, system_prompt=system_prompt)
        data = [dataclasses.asdict(s) for s in snapshots] if snapshots else []
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('REPLAY', data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, data, allow_protected=True)
        _render_summary(snapshots)
        return CommandResult.ok()

    if mode == "at":
        if not mode_args:
            print("Usage: /session replay [id] at <N>")
            return CommandResult.ok()
        try:
            turn_n = int(mode_args[0])
        except ValueError:
            print(f"Invalid turn number: {mode_args[0]}")
            return CommandResult.ok()
        snap = replayer.snapshot_at_turn(turns, system_prompt, turn_id=turn_n, limit=limit)
        if snap is None:
            print(f"Turn {turn_n} not found. Available turn ids: {[t.get('turn_id') for t in llm_turns]}")
            return CommandResult.ok()
        data = dataclasses.asdict(snap)
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('REPLAY', data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, data, allow_protected=True)
        _render_at(snap, system_prompt)
        return CommandResult.ok()

    if mode == "diff":
        if len(mode_args) < 2:
            print("Usage: /session replay [id] diff <A> <B>")
            return CommandResult.ok()
        try:
            turn_a = int(mode_args[0])
            turn_b = int(mode_args[1])
        except ValueError:
            print(f"Invalid turn numbers: {mode_args[:2]}")
            return CommandResult.ok()
        diff = replayer.diff_turns(target, turn_a, turn_b, limit=limit, turns=turns, system_prompt=system_prompt)
        if diff is None:
            print(f"Could not build diff for turns {turn_a} / {turn_b}. Available turn ids: {[t.get('turn_id') for t in llm_turns]}")
            return CommandResult.ok()
        data = dataclasses.asdict(diff)
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('REPLAY', data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, data, allow_protected=True)
        _render_diff(diff)
        return CommandResult.ok()

    if mode == "step":
        snapshots = replayer.replay_all(target, limit=limit, turns=turns, system_prompt=system_prompt)
        if not snapshots:
            print("No turns to step through.")
            return CommandResult.ok()
        data = [dataclasses.asdict(s) for s in snapshots] if snapshots else []
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('REPLAY', data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, data, allow_protected=True)
        print("\nInteractive replay stepper. Press Enter to advance, 'q' to quit.")
        for s in snapshots:
            print("\n" + "-" * 78)
            print(f"Turn {s.turn_id} | msgs={s.message_count} uncut={s.total_tokens} "
                  f"trunc={s.truncated_tokens} evicted={len(s.evicted_indices)} "
                  f"anchor_warn={'YES' if s.anchors_alone_exceed_limit else '-'}")
            try:
                cmd = input("[Enter]=next q=quit show=full> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nStepper exited.")
                break
            if cmd in ("q", "quit", "exit"):
                break
            if cmd in ("show", "s", "full"):
                _render_at(s, system_prompt)
        print("\nStepper finished.")
        return CommandResult.ok()

    return CommandResult.ok()


@command(
    "/replay",
    help="Replay and inspect session context window history",
    args="[<id>] [at <N> | diff <A> <B> | step] [limit=<N>]",
    category="session",
)
async def cmd_replay(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    raw_tokens: List[str] = []
    for p in parts[1:]:
        raw_tokens.extend(p.strip().split())
    return await handle_replay_command(ctx, raw_tokens)
