# Technical Proposal: Line-by-Line Content Inspection for Chatybot Security (Builtin & RACF)

**Document Version:** 1.0  
**Date:** October 25, 2026  
**Status:** Implemented  
**Applies To:** Builtin Policy Engine (`BuiltinPolicyEngine`, `SecurityDSLParser`) & RACF Binary Guard (`racf-guard`)  

---

## 1. Problem Statement & Motivation

Both Chatybot's **Builtin Security Engine** (`src/chatybot/security/builtin.py`, `dsl.py`) and **RACF-Guard** (`tools/racf-guard/src/engine.rs`) currently support inspecting content payloads (such as file write arguments, patch diffs, and output egress text).

However, both engines currently suffer from a major design gap: **they evaluate patterns against the content payload as a single monolithic scalar string rather than on a line-by-line basis.**

### Current Limitations

1. **Inability to Anchor Line Prefixes (`startswith` / `#!` / command starts):**
   - In Builtin DSL: `deny write file starting with '#!'` evaluates `val_str.startswith("#!")` on the entire file payload. If the file has a leading blank line, a license comment on line 1, or the script directive appears on line 3, `startswith` evaluates to `False`.
   - Likewise, a rule like `deny write file starting with 'rm'` fails if `rm` is preceded by any other line in the script.
2. **Indentation and Formatting Fragility in RACF:**
   - In RACF's `CONTENT` class, `racf-guard` evaluates `glob_match(&pat_lower, line)`. A pattern like `RDEFINE CONTENT rm *` requires the **entire line** to match.
   - If a line is indented (e.g. `    rm -rf /tmp/cache`), the glob fails because leading spaces are not matched.
   - Using broad wildcards like `*rm *` turns the check into an uncontrolled substring search that matches harmless identifiers (e.g. `perform_action`).
3. **Write Input vs. Read Output Asymmetry:**
   - Builtin security currently lacks automated line-level scanning on pre-execution write payloads (`write_file`, `replace_file_content`), whereas output egress relies solely on regex pattern matching in `SecretScanner`.

---

## 2. Proposed Architecture & Scope

This proposal introduces **Line-by-Line Content Inspection** across both security engines:

```
                          Incoming Content Payload
               (write_file argument, patch chunk, or read output)
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │ Fast Substring Pre-Filter   │
                     │ (Does keyword appear in C?) │
                     └──────────────┬──────────────┘
                                    │ Yes
                                    ▼
                     ┌─────────────────────────────┐
                     │ Line Splitter & Normalizer  │
                     │ (splitlines + trim leading) │
                     └──────────────┬──────────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     ▼                             ▼
       ┌───────────────────────────┐ ┌───────────────────────────┐
       │   Builtin Security DSL    │ │      RACF-Guard Rust      │
       │  line starts with ...     │ │    CONTENT Profile Match  │
       │  first line starts with   │ │   (Trimmed per-line glob) │
       │  any line matching ...    │ │                           │
       └───────────────────────────┘ └───────────────────────────┘
```

---

## 3. Specification: Builtin Policy Engine & DSL

### 3.1 DSL Grammar Extensions

Extend `SecurityDSLParser` and `SecurityRuleAST` to support line-targeted qualifiers and operators:

```bnf
Condition       ::= ("WHERE" | "WITH" | "MATCHING") Predicate
Predicate       ::= LineQualifier? Operator Value
LineQualifier   ::= "LINE" | "ANY LINE" | "FIRST LINE" | "HEADER"
Operator        ::= "STARTS" "WITH" | "STARTING" "WITH"
                  | "ENDS" "WITH" | "ENDING" "WITH"
                  | "CONTAINS" | "HAS"
                  | "EQUALS" | "IS"
                  | "MATCHES"
```

### 3.2 Human-Readable Rule Examples

```toml
# In ~/.config/chatybot/security.toml [builtin]
dsl_rules = [
    # Shebang / executable script prevention in documents
    "deny write file where first line starts with '#!' because 'executable scripts not allowed in workspace'",
    
    # Destructive command prevention in generated scripts/configs
    "deny write file where line starts with 'rm ' because 'unbounded rm command detected'",
    "deny write file where line starts with 'rm -rf' because 'destructive removal command'",
    "deny write file where line starts with 'mkfs' because 'filesystem formatting command'",
    "deny write file where line starts with ':(){ :|:& };:' because 'fork bomb detected'",

    # Sensitive classification headers in read files (Output screening)
    "deny read file where any line contains 'CONFIDENTIAL // NOFORN'",
    "deny read file where first line contains 'RESTRICTED_DATA'",

    # Privilege escalation commands
    "ask before write file where line starts with 'sudo'",
    "ask before write file where line starts with 'chmod +x'",
]
```

### 3.3 Evaluation Algorithm (`SecurityRuleAST.matches`)

For any rule with a `line_scope` (`"any_line"`, `"first_line"`):

```python
def matches_content_lines(self, val_str: str) -> bool:
    if not val_str:
        return False

    # 1. First-line / Header inspection
    if self.line_scope == "first_line":
        # Find first non-empty line
        for raw_line in val_str.splitlines():
            line = raw_line.strip()
            if line:
                return self._eval_line(line)
        return False

    # 2. Fast-path substring check (Boyer-Moore-Horspool in C)
    # If the literal pattern cannot possibly exist in the text, skip splitting lines.
    if self.operator in ("contains", "startswith", "equals") and self.value_lower:
        if self.value_lower not in val_str.lower():
            return False

    # 3. Line-by-line inspection (Early-exit on first hit)
    for raw_line in val_str.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if self._eval_line(line):
            return True

    return False
```

---

## 4. Specification: RACF-Guard (`racf-guard`)

### 4.1 Enhanced `CONTENT` Class Semantics

In `tools/racf-guard/src/engine.rs`, update the `ResourceClass::Content` profile evaluator so that:

1. **Indentation Normalization:** Lines are trimmed (`line.trim()`) before evaluating patterns.
2. **Line-Anchored Glob Matching:**
   - A pattern like `#!*` or `rm *` matches against `line.trim()` for each line.
   - If a line starts with `rm `, even if indented with 4 spaces or a tab (`    rm -rf /cache`), it matches.
3. **Header-Specific Profile Namespace (Optional/Clean Extension):**
   - Allow profiles like `CONTENT:HEADER.#!*` or `CONTENT:FIRSTLINE.#!*` for first-line matching.

### 4.2 RACF Rule Examples

```racf
# Block shebang lines in written files
RDEFINE CONTENT #!*          UACC(DENY)

# Block destructive commands on any line (regardless of indentation)
RDEFINE CONTENT rm *         UACC(DENY)
RDEFINE CONTENT sudo *       UACC(ASK)
RDEFINE CONTENT mkfs*        UACC(DENY)

# Existing payload secret signatures continue to match across lines
RDEFINE CONTENT *BEGIN*PRIVATE*KEY* UACC(DENY)
RDEFINE CONTENT *api_key*           UACC(DENY)
```

### 4.3 Evaluation Implementation (`engine.rs`)

```rust
ResourceClass::Content => {
    let pat_lower = self.pattern.to_lowercase();
    let res_lower = resource.to_lowercase();

    // 1. Whole-block match (for multi-line patterns like certificates/private keys)
    let normalized_pattern = if pat_lower.contains('*') && !pat_lower.contains("**") {
        pat_lower.replace('*', "**")
    } else {
        pat_lower.clone()
    };
    if glob_match(&normalized_pattern, &res_lower) {
        return true;
    }

    // 2. Line-by-line match with indentation trimming
    for raw_line in res_lower.lines() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }
        if glob_match(&pat_lower, line) {
            return true;
        }
    }
    false
}
```

---

## 5. Performance & Overhead Analysis

Because LLM generation limits constrain tool invocation payloads:

| Payload Metric | Typical LLM Interaction | Maximum Limit (Stress Case) |
|---|---|---|
| **Token Count** | 500 – 4,000 tokens | 16,384 tokens |
| **Payload Size** | 2 KB – 16 KB | ~64 KB |
| **Line Count** | 50 – 400 lines | ~1,500 lines |

### Benchmark Projections

- **Python (`BuiltinPolicyEngine`)**:
  - Substring fast-path bypass (`if keyword not in text`): **`< 0.002 ms`**.
  - Full `splitlines()` + `line.strip().startswith(...)` over 500 lines: **`~0.03 ms`**.
- **Rust (`racf-guard`)**:
  - Native Rust line iterator + glob match: **`< 0.01 ms`**.
- **Total Request Latency Impact**: **`< 0.1%`** of local tool dispatch time; completely imperceptible to users.

---

## 6. Pre-Write Inspection in `SecurityManager`

To ensure full coverage, file write tools (`write_file`, `replace_file_content`, `multi_replace_file_content`, `patch_file`) must have their content inspected **before** the filesystem is touched:

1. **Candidate Content Extraction**:
   Extract all text from `content`, `text`, `code_content`, and `ReplacementChunks[*].replacement_content`.
2. **Floor Scanner Check**:
   Run `SecretScanner.scan(content)` on write payloads (prevents writing leaked API keys into workspace files).
3. **DSL / RACF Evaluation**:
   Run the content rules against each extracted content block.

---

## 7. Migration & Backward Compatibility

- **100% Backward Compatible**: Existing DSL rules without the `line` or `first line` qualifiers (e.g. `deny read file with 'secret' in it`) continue to operate as broad substring/pattern matches.
- **RACF Compatibility**: Existing `RDEFINE CONTENT *api_key*` profiles continue to match via the whole-string pass; only line-oriented profiles (`rm *`, `#!*`) gain the new ability to match trimmed lines.

---

## 8. Implementation & Production Hardenings

The implementation completed with the following features and hardenings:

1. **Security DSL Grammar & Line Evaluation (`dsl.py`)**:
   - `SecurityRuleAST` supports `line_scope: "first_line" | "any_line" | None`.
   - Recognizes `line starts with`, `first line starts with`, `header contains`, and `any line contains`.
   - Fast-path Boyer-Moore substring filter avoids line iteration for large files when the keyword is absent.
   - Trims and normalizes whitespace per line, correctly catching indented commands (`    rm -rf /`).
   - Supports shebang header identification on the first non-empty line.

2. **Full MCP Support (Write, Read & Command)**:
   - Evaluates write payloads pre-execution and read outputs post-execution.
   - Extracts nested parameters across arbitrary levels (e.g., `arguments.content`, `params.query`, `arguments.stdin`).
   - Hardened `workdir` and `working_dir` parameter extraction to guard against path traversal in MCP terminal tools.
   - Hardened array of paths handling (`paths: ["..."]`).

3. **RACF-Guard Rust Engine (`engine.rs`)**:
   - Depth-limited recursive extraction (`depth <= 15`) prevents stack exhaustion DoS from maliciously nested JSON.
   - Trimmed per-line glob evaluation matches indented commands and shebang patterns (`'#!*'`).
   - Fast-path literal needle pre-filter avoids line iteration across multi-megabyte payloads.
   - Inspects `request.output` for post-execution egress screening.

4. **Test Suite Verification**:
   - Complete unit and integration test coverage across Builtin DSL, SecurityManager lifecycle, MCP payloads, and RACF Guard.
