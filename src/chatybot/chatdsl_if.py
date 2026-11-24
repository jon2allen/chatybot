"""Shared ChatDSL line classifier - single source of truth for construct-vs-prompt.

Used by both the runtime (chatybot_app) and the standalone parser
(chatdsl_parse) so the two can never disagree on how a line is read.

Rules
-----
- A line starting with a script keyword is a construct ONLY if it also
  matches that keyword's shape heuristic; otherwise it is an LLM prompt.
  This is what keeps prose like ``if you find a bug then fix`` from being
  executed as a conditional.
- An ``if``/``elseif`` condition must reference a variable (``$var`` or
  ``${var}``); variable-free conditions are prose, not conditionals.
- The FIRST ``then`` outside quotes terminates the condition (never the
  last), so ``if $X then /echo then`` is a single-line if whose body is
  ``/echo then`` - not a phantom block opener.
- After ``then`` an optional ``:`` is allowed; if nothing else remains on
  the line, the construct opens a block (``if_block`` / ``elseif``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Keywords that may start a script construct. Shared by the runtime
# dispatch, the interactive command-verb matcher, and the parser.
SCRIPT_KEYWORDS = frozenset({
    "if", "elseif", "elif", "else", "endif",
    "set", "local", "wait", "def", "defproc", "endproc",
    "foreach", "endfor", "break",
})

_WORD_RE = re.compile(r"[A-Za-z_]\w*")
_OP_RE = re.compile(r"(==|!=|>=|<=|>|<)")
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_BARE_OPERAND_RE = re.compile(r"[A-Za-z_]\w*(?::[A-Za-z0-9_\-]*)*")  # bare name, optional :modifiers (incl. open-ended slices)
_SET_RE = re.compile(r"\s+([A-Za-z_]\w*)\s*(\[\])?\s*=")
_WAIT_RE = re.compile(r"\s+(\d+(?:\.\d+)?)\s*$")
_LOCAL_RE = re.compile(r"\s+([A-Za-z_]\w*)")
_DEF_RE = re.compile(r"\s+([A-Za-z_]\w*)\s*\(")
_FOREACH_RE = re.compile(r"\s+([A-Za-z_]\w*)\s+in\s+(.+?)\s*$")
_FOREACH_ITERABLE_RE = re.compile(r"[A-Za-z_]\w*|\$\{?\w+\}?|range\(.*\)|lines\(.*\)")
_MACRO_RE = re.compile(r"%([A-Za-z_]\w*)\s*\(")


@dataclass
class LineClassification:
    """Result of classifying one script line.

    kind is one of: empty, comment, command, prompt, set, local, wait,
    macro_def, macro, defproc, endproc, foreach, endfor, break,
    if_block, if_single, elseif, else, endif, invalid_construct.
    """
    kind: str
    keyword: str | None = None
    condition: str | None = None      # if / elseif
    then_body: str | None = None      # if_single
    else_body: str | None = None      # if_single
    is_block: bool = False            # if_block / elseif
    name: str | None = None           # set / local / def / defproc / macro
    item_var: str | None = None       # foreach
    iterable: str | None = None       # foreach
    reason: str | None = None         # invalid_construct
    lhs: str | None = None            # if/elseif: left operand when needs_var_check
    needs_var_check: bool = False     # True when construct-vs-prompt depends on a runtime variable


def _quoted_mask(text: str) -> list[bool]:
    """mask[i] is True when text[i] is inside a '...' or "..." region."""
    mask = [False] * len(text)
    in_dq = in_sq = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            mask[i] = in_dq or in_sq
            mask[i + 1] = in_dq or in_sq
            i += 2
            continue
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        mask[i] = in_dq or in_sq
        i += 1
    return mask


def find_outside_quotes(text: str, pattern: str) -> re.Match | None:
    """First regex match of `pattern` in `text` that starts outside quotes."""
    mask = _quoted_mask(text)
    for m in re.finditer(pattern, text):
        if not mask[m.start()]:
            return m
    return None


def _classify_if(rest: str, kw: str) -> LineClassification:
    """Classify the text after an `if`/`elseif`/`elif` keyword."""
    then_m = find_outside_quotes(rest, r"\s+then\b")
    if then_m is None:
        # Keyword matched; if the would-be condition references a variable,
        # this is a malformed construct (error), not prose.
        if "$" in rest:
            return LineClassification("invalid_construct", keyword=kw,
                                      reason="missing 'then'")
        return LineClassification("prompt", keyword=kw)

    condition = rest[:then_m.start()].strip()
    if not condition:
        return LineClassification("invalid_construct", keyword=kw,
                                  reason="empty condition")

    # Decide construct-vs-prose. A variable reference ($var / ${var}) is always a
    # construct. Otherwise the condition must have a comparison/truthy *shape*:
    # numeric or quoted left operand -> construct; bare-identifier left operand ->
    # needs_var_check (the runtime resolves it against actual script variables, so
    # undefined names in prose like "if x > 3 then answer" still read as prompts).
    needs_var_check = False
    lhs = None
    if "$" not in condition:
        cond_no_not = re.sub(r"^not\s+", "", condition, flags=re.IGNORECASE).strip()
        op_m = find_outside_quotes(cond_no_not, _OP_RE.pattern)
        if op_m is not None:
            lhs = cond_no_not[:op_m.start()].strip()
            rhs = cond_no_not[op_m.end():].strip()
            if not lhs or not rhs:
                return LineClassification("prompt", keyword=kw, condition=condition)
            if _NUM_RE.fullmatch(lhs) or (lhs[:1] in ("\"", "'")):
                pass  # literal comparison -> construct
            elif _BARE_OPERAND_RE.fullmatch(lhs):
                needs_var_check = True
            else:
                return LineClassification("prompt", keyword=kw, condition=condition)
        elif _BARE_OPERAND_RE.fullmatch(cond_no_not):
            # truthy check on a bare name (or bare name with modifiers): maybe a variable, maybe prose
            needs_var_check = True
            lhs = cond_no_not
        else:
            return LineClassification("prompt", keyword=kw, condition=condition)

    body = rest[then_m.end():].strip()
    if body.startswith(":"):
        body = body[1:].strip()

    if not body:
        return LineClassification(
            "if_block" if kw == "if" else "elseif",
            keyword=kw, condition=condition, is_block=True,
            lhs=lhs, needs_var_check=needs_var_check)

    if kw != "if":
        return LineClassification(
            "invalid_construct", keyword=kw, condition=condition,
            reason="elseif/elif must open a block (nothing may follow 'then' on the same line)")

    else_m = find_outside_quotes(body, r"\s+else\b")
    if else_m is not None:
        then_body = body[:else_m.start()].strip()
        else_body = body[else_m.end():].strip()
    else:
        then_body, else_body = body, None
    return LineClassification(
        "if_single", keyword=kw, condition=condition,
        then_body=then_body, else_body=else_body, is_block=False,
        lhs=lhs, needs_var_check=needs_var_check)


def resolve_var_check(cls: LineClassification, script_vars) -> LineClassification:
    """Resolve a needs_var_check classification against actual script variables.

    Rule (single source): a bare-name condition counts as a construct only if
    that variable is set; otherwise the line is a prompt. `script_vars` is any
    mapping, e.g. BufferManager.script_vars.
    """
    if cls.needs_var_check and cls.lhs:
        base = cls.lhs.split(":")[0].lstrip("$")
        if base not in script_vars:
            return LineClassification("prompt", keyword=cls.keyword)
    return cls


def classify_script_line(line: str) -> LineClassification:
    """Classify one raw script line. See module docstring for the rules."""
    stripped = line.strip()
    if not stripped:
        return LineClassification("empty")
    if stripped.startswith("#"):
        return LineClassification("comment")
    if stripped.startswith("/"):
        return LineClassification("command")
    if stripped.startswith("%"):
        m = _MACRO_RE.match(stripped)
        if m:
            return LineClassification("macro", keyword="%", name=m.group(1))
        return LineClassification("prompt", keyword="%")

    m = _WORD_RE.match(stripped)
    if not m:
        return LineClassification("prompt")
    word = m.group(0)
    kw = word.lower()
    if kw not in SCRIPT_KEYWORDS:
        return LineClassification("prompt")
    rest = stripped[m.end():]

    if kw in ("if", "elseif", "elif"):
        return _classify_if(rest, kw)
    if kw == "else":
        if rest.strip() in ("", ":"):
            return LineClassification("else", keyword=kw)
        return LineClassification("prompt", keyword=kw)
    if kw in ("endif", "endfor"):
        if rest.strip() in ("", ":"):
            return LineClassification(kw, keyword=kw)
        return LineClassification("prompt", keyword=kw)
    if kw in ("endproc", "break"):
        if rest.strip() == "":
            return LineClassification(kw, keyword=kw)
        return LineClassification("prompt", keyword=kw)
    if kw == "set":
        m2 = _SET_RE.match(rest)
        if m2:
            return LineClassification("set", keyword=kw, name=m2.group(1))
        return LineClassification("prompt", keyword=kw)
    if kw == "wait":
        if _WAIT_RE.match(rest):
            return LineClassification("wait", keyword=kw)
        return LineClassification("prompt", keyword=kw)
    if kw == "local":
        m2 = _LOCAL_RE.match(rest)
        if m2:
            return LineClassification("local", keyword=kw, name=m2.group(1))
        return LineClassification("prompt", keyword=kw)
    if kw in ("def", "defproc"):
        m2 = _DEF_RE.match(rest)
        if m2:
            return LineClassification("macro_def" if kw == "def" else "defproc",
                                      keyword=kw, name=m2.group(1))
        return LineClassification("prompt", keyword=kw)
    if kw == "foreach":
        m2 = _FOREACH_RE.match(rest)
        if m2 and _FOREACH_ITERABLE_RE.fullmatch(m2.group(2)):
            return LineClassification("foreach", keyword=kw,
                                      item_var=m2.group(1), iterable=m2.group(2))
        return LineClassification("prompt", keyword=kw)

    return LineClassification("prompt", keyword=kw)
