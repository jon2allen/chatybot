#! /usr/bin/env python3
"""
Context Limit Module
Manages user-configurable context limits, token counting, warning triggers,
and automatic conversation history truncation.
"""

import math
from typing import Dict, Any, List, Optional, Tuple, Union


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
        anchors: List[Dict[str, Any]] = []
        if len(result) > 0 and result[0].get("role") == "system":
            anchors.append(result[0])
            remaining = result[1:]
        else:
            remaining = result

        # Anchor initial user prompt if present
        if remaining and remaining[0].get("role") == "user":
            anchors.append(remaining[0])
            evictable = remaining[1:]
        else:
            evictable = remaining

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
            # Find the largest message among evictable (or non-system anchors if evictable is empty)
            candidate_list = evictable if evictable else [m for m in anchors if m.get("role") != "system"]
            if not candidate_list:
                candidate_list = anchors

            largest_msg = max(
                candidate_list,
                key=lambda m: len(m.get("content", "")) if isinstance(m.get("content"), str) else 0
            )
            content = largest_msg.get("content", "")
            if isinstance(content, str) and len(content) > 60:
                current_total = self.count_tokens_messages(anchors + evictable)
                excess_tokens = current_total - target_limit
                excess_chars = int(excess_tokens * 4) + 60
                new_length = max(40, len(content) - excess_chars)
                if new_length < len(content):
                    did_truncate = True
                    head_len = max(20, int(new_length * 0.6))
                    tail_len = max(0, new_length - head_len)
                    head = content[:head_len]
                    tail = content[-tail_len:] if tail_len > 0 else ""
                    largest_msg["content"] = f"{head}\n\n[... content truncated to fit context limit ...]\n\n{tail}"
                else:
                    # Cannot shrink further
                    break
            else:
                # Content too small or cannot shrink further
                break

        if did_truncate:
            trunc_notice = "[Note: Earlier messages were truncated to fit the context limit.]"
            target_notice_list = evictable if evictable else anchors
            if target_notice_list and isinstance(target_notice_list[0].get("content"), str):
                if not target_notice_list[0]["content"].startswith(trunc_notice) and not target_notice_list[0]["content"].startswith("[Note:"):
                    target_notice_list[0] = dict(target_notice_list[0])
                    target_notice_list[0]["content"] = f"{trunc_notice}\n\n{target_notice_list[0]['content']}"

        result = anchors + evictable
        return result, did_truncate
