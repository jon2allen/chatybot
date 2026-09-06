#! /usr/bin/env python3
"""
Context Limit Module
Manages user-configurable context limits, token counting, warning triggers,
and automatic conversation history truncation.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Union


@dataclass
class TruncationDiagnostic:
    """Comprehensive diagnostic struct produced by truncate_messages_verbose."""
    original_messages: List[Dict[str, Any]]
    truncated_messages: List[Dict[str, Any]]
    did_truncate: bool
    original_tokens: int
    truncated_tokens: int
    effective_limit: int           # raw limit (before pct adjustment)
    target_limit: int             # pct-adjusted limit actually enforced
    anchor_count: int
    evicted_count: int             # how many messages were dropped
    evicted_indices: List[int]     # original 0-based indices that were removed
    content_truncated: bool        # True if string truncation fired on a message
    anchors_alone_exceed_limit: bool  # infinite-loop warning condition


class ContextLimiter:
    """
    Manages user-configurable context limits, token counting using heuristic,
    warning triggers, and automatic conversation history truncation.
    """

    def __init__(self, default_limit: Optional[int] = None, auto_truncate: bool = False, truncate_pct: float = 100.0):
        self.context_limit: Optional[int] = default_limit
        self.auto_truncate: bool = auto_truncate
        self.truncate_pct: float = truncate_pct
        self._user_set_limit: bool = False

    def count_tokens_text(self, text: str) -> int:
        """
        Count tokens in a string using byte/character estimation heuristic (~4 bytes per token).
        """
        if not text:
            return 0
        byte_count = len(text.encode("utf-8"))
        return max(1, math.ceil(byte_count / 4)) if byte_count > 0 else 0

    def count_tokens_message(self, message: Dict[str, Any]) -> int:
        """
        Count tokens in a single message dictionary ({role, content}).
        Includes standard message format overhead (3 tokens).
        """
        tokens = 3  # Standard message framing overhead
        role = message.get("role", "")
        if role:
            tokens += self.count_tokens_text(role)

        content = message.get("content", "")
        if isinstance(content, str):
            tokens += self.count_tokens_text(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        tokens += self.count_tokens_text(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        tokens += 85  # Standard token estimate for image reference
                elif isinstance(part, str):
                    tokens += self.count_tokens_text(part)

        # Count tool calls if present (function name + JSON arguments)
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                if isinstance(tc, dict):
                    tokens += 3  # tool call framing overhead
                    fn = tc.get("function")
                    if isinstance(fn, dict):
                        tokens += self.count_tokens_text(fn.get("name", ""))
                        tokens += self.count_tokens_text(str(fn.get("arguments", "")))
                    elif "name" in tc:
                        tokens += self.count_tokens_text(tc.get("name", ""))
                        tokens += self.count_tokens_text(str(tc.get("arguments", "")))

        # Count tool message metadata if present
        if message.get("name"):
            tokens += self.count_tokens_text(str(message["name"]))
        if message.get("tool_call_id"):
            tokens += self.count_tokens_text(str(message["tool_call_id"]))

        return tokens

    def count_tokens_messages(self, messages: List[Dict[str, Any]]) -> int:
        """
        Count total tokens across a list of message dictionaries.
        Includes 3 assistant reply priming tokens.
        """
        total = 3  # Reply priming tokens
        for msg in messages:
            total += self.count_tokens_message(msg)
        return total

    def set_limit(self, limit: Optional[int], from_user: bool = True) -> None:
        """
        Set or update the context limit.
        """
        if limit is not None and limit <= 0:
            self.context_limit = None
        else:
            self.context_limit = limit
        if from_user:
            self._user_set_limit = (self.context_limit is not None)

    def set_auto_truncate(self, enabled: bool, pct: Optional[float] = None) -> None:
        """
        Enable or disable auto-truncation and set the trigger percentage (10.0 - 100.0).
        """
        self.auto_truncate = enabled
        if pct is not None:
            self.truncate_pct = float(pct)

    def check_warnings(self, total_tokens: int, limit: Optional[int] = None) -> Optional[str]:
        """
        Check if total token usage approaches or exceeds warning thresholds (70%, 90%).
        Returns warning message string if threshold reached, else None.
        """
        effective_limit = limit or self.context_limit
        if not effective_limit or effective_limit <= 0:
            return None

        pct = (total_tokens / effective_limit) * 100.0
        if pct >= 90.0:
            return f"[Warning: Context usage at {pct:.1f}% of limit ({total_tokens:,}/{effective_limit:,} tokens). Approaching context window limit.]"
        elif pct >= 70.0:
            return f"[Warning: Context usage at {pct:.1f}% of limit ({total_tokens:,}/{effective_limit:,} tokens).]"
        return None

    @staticmethod
    def partition_anchors(messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Partition messages into anchors (system prompt + initial user prompt) and evictable turns.
        Returns: (anchors, evictable)
        """
        anchors: List[Dict[str, Any]] = []
        if len(messages) > 0 and messages[0].get("role") == "system":
            anchors.append(messages[0])
            remaining = messages[1:]
        else:
            remaining = messages

        if remaining and remaining[0].get("role") == "user":
            anchors.append(remaining[0])
            evictable = remaining[1:]
        else:
            evictable = remaining

        return anchors, evictable

    def truncate_messages(
        self,
        messages: List[Dict[str, Any]],
        limit: Optional[int] = None,
        target_pct: Optional[float] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Truncate oldest intermediate messages and/or oversized message content until total tokens fit within target limit.
        Preserves the system prompt (if index 0) and the initial user goal/prompt, dropping intermediate turns first.
        Returns: (truncated_messages, did_truncate)
        """
        effective_limit = limit or self.context_limit
        if not effective_limit or effective_limit <= 0:
            return messages, False

        pct = target_pct if target_pct is not None else self.truncate_pct
        target_limit = int(effective_limit * (pct / 100.0))

        current_tokens = self.count_tokens_messages(messages)
        if current_tokens <= target_limit:
            return messages, False

        # Make copy of messages list
        result = [dict(m) for m in messages]
        
        # Partition into anchors (system prompt + initial user prompt) and evictable intermediate turns
        anchors, evictable = self.partition_anchors(result)

        did_truncate = False

        # Step 1: Drop older intermediate turns (keeping the latest turn if possible)
        while len(evictable) > 1 and self.count_tokens_messages(anchors + evictable) > target_limit:
            evictable.pop(0)
            did_truncate = True

        # If evictable has 1 item and total still exceeds target_limit, drop it if anchors alone fit better
        if len(evictable) == 1 and self.count_tokens_messages(anchors + evictable) > target_limit:
            evictable.pop(0)
            did_truncate = True

        # Step 2: If total tokens still exceed target_limit (single large message or remaining large turns),
        # truncate individual message content down to fit the available token budget
        while self.count_tokens_messages(anchors + evictable) > target_limit:
            # Find the largest message among evictable (or all anchors if evictable is empty)
            candidate_list = evictable if evictable else anchors
            if not candidate_list:
                break

            largest_msg = max(
                candidate_list,
                key=lambda m: len(m.get("content", "")) if isinstance(m.get("content"), str) else 0
            )
            content = largest_msg.get("content", "")
            if not isinstance(content, str) or len(content) <= 60:
                break

            current_total = self.count_tokens_messages(anchors + evictable)
            excess_tokens = current_total - target_limit
            excess_chars = int(excess_tokens * 4) + 60
            new_length = max(40, len(content) - excess_chars)
            if new_length >= len(content):
                # Cannot shrink further
                break

            did_truncate = True
            head_len = max(20, int(new_length * 0.6))
            tail_len = max(0, new_length - head_len)
            head = content[:head_len]
            tail = content[-tail_len:] if tail_len > 0 else ""
            new_content = f"{head}\n\n[... content truncated to fit context limit ...]\n\n{tail}"
            # No-progress guard: if truncation didn't reduce content length, stop
            if len(new_content) >= len(content):
                break
            largest_msg["content"] = new_content

        if did_truncate:
            trunc_notice = "[Note: Earlier messages were truncated to fit the context limit.]"
            target_notice_list = evictable if evictable else anchors
            if target_notice_list and isinstance(target_notice_list[0].get("content"), str):
                if not target_notice_list[0]["content"].startswith(trunc_notice) and not target_notice_list[0]["content"].startswith("[Note:"):
                    target_notice_list[0] = dict(target_notice_list[0])
                    target_notice_list[0]["content"] = f"{trunc_notice}\n\n{target_notice_list[0]['content']}"

            # Ensure prepending the truncation notice did not push total tokens over target_limit
            while self.count_tokens_messages(anchors + evictable) > target_limit:
                candidate_list = evictable if evictable else anchors
                if not candidate_list:
                    break

                largest_msg = max(
                    candidate_list,
                    key=lambda m: len(m.get("content", "")) if isinstance(m.get("content"), str) else 0
                )
                content = largest_msg.get("content", "")
                if not isinstance(content, str) or len(content) <= 60:
                    break

                current_total = self.count_tokens_messages(anchors + evictable)
                excess_tokens = current_total - target_limit
                excess_chars = int(excess_tokens * 4) + 60
                new_length = max(40, len(content) - excess_chars)
                if new_length >= len(content):
                    break

                head_len = max(20, int(new_length * 0.6))
                tail_len = max(0, new_length - head_len)
                head = content[:head_len]
                tail = content[-tail_len:] if tail_len > 0 else ""
                new_content = f"{head}\n\n[... content truncated to fit context limit ...]\n\n{tail}"
                if len(new_content) >= len(content):
                    break
                largest_msg["content"] = new_content

        result = anchors + evictable
        return result, did_truncate

    def truncate_messages_verbose(
        self,
        messages: List[Dict[str, Any]],
        limit: Optional[int] = None,
        target_pct: Optional[float] = None,
    ) -> "TruncationDiagnostic":
        """Run truncate_messages and return a comprehensive diagnostic struct.

        Non-breaking diagnostic wrapper around truncate_messages with monotonic
        index tracking (_orig_idx) so callers can see exactly which original
        messages were evicted. The _orig_idx tags survive because
        truncate_messages performs shallow dict copies (dict(m)) that preserve
        extra keys; if truncate_messages is ever refactored to reconstruct
        dicts with only role/content, this tracking silently breaks — add a
        regression test.
        """
        if not messages:
            return TruncationDiagnostic(
                original_messages=[], truncated_messages=[], did_truncate=False,
                original_tokens=0, truncated_tokens=0, effective_limit=0,
                target_limit=0, anchor_count=0, evicted_count=0,
                evicted_indices=[], content_truncated=False,
                anchors_alone_exceed_limit=False,
            )

        # Attach monotonic tracking tags to avoid content collision
        tagged_messages: List[Dict[str, Any]] = [
            {"_orig_idx": i, **m} for i, m in enumerate(messages)
        ]
        orig_tokens = self.count_tokens_messages(messages)

        # Variable names aligned with truncate_messages (context_limit.py:113-118):
        #   effective_limit = the raw limit (before pct adjustment)
        #   target_limit    = the pct-adjusted limit actually enforced
        effective_limit = limit or self.context_limit or 0
        pct = (target_pct if target_pct is not None else self.truncate_pct) / 100.0
        target_limit = int(effective_limit * pct) if effective_limit else 0

        # Anchor partition overflow detection (mirrors truncate_messages anchoring)
        anchors, _ = self.partition_anchors(tagged_messages)
        anchor_tokens = self.count_tokens_messages(anchors)
        anchors_alone_overflow = bool(target_limit and anchor_tokens > target_limit)

        # Run core truncation on a copy. _orig_idx tags survive the shallow
        # dict copy performed inside truncate_messages.
        clean_copy = [dict(m) for m in tagged_messages]
        truncated_tagged, did_truncate_ret = self.truncate_messages(
            clean_copy, limit=limit, target_pct=target_pct
        )

        surviving_indices = {m["_orig_idx"] for m in truncated_tagged if "_orig_idx" in m}
        evicted_indices = [i for i in range(len(messages)) if i not in surviving_indices]
        content_truncated = any(
            "[... content truncated" in str(m.get("content", "")) for m in truncated_tagged
        )

        # Clean tags from the final output
        final_truncated = [
            {k: v for k, v in m.items() if k != "_orig_idx"} for m in truncated_tagged
        ]
        trunc_tokens = self.count_tokens_messages(final_truncated)

        return TruncationDiagnostic(
            original_messages=messages,
            truncated_messages=final_truncated,
            did_truncate=did_truncate_ret or content_truncated,
            original_tokens=orig_tokens,
            truncated_tokens=trunc_tokens,
            effective_limit=effective_limit,
            target_limit=target_limit,
            anchor_count=len(anchors),
            evicted_count=len(evicted_indices),
            evicted_indices=evicted_indices,
            content_truncated=content_truncated,
            anchors_alone_exceed_limit=anchors_alone_overflow,
        )
