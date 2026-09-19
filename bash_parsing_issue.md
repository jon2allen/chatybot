# Bash Parsing Issue: Variable Substitution Strips `$VAR` from `/decide` State Content

## Status

Open — needs review

## Date

2026-09-17

## Summary

When `/decide` is used with a script variable containing bash code (e.g. a
generated shell script with `$REPO_PATH`, `$0`, `$1`), the variable
substitution pipeline (`replace_placeholders_legacy`) strips all unresolved
`$VAR` patterns from the content before it reaches the decide handler. This
corrupts the state text sent to the decision model.

## Reproduction

```
/setvar bash1 ${LAST_COMPLETION}
/decide "${bash1}" noul "Does this contain dangerous commands?" threshold=0.8 var=bash_decision
```

Where `bash1` contains a script like:

```bash
#!/usr/bin/env bash
REPO_PATH="$1"
rm -rf "$REPO_PATH/.git"
echo "Deleted $REPO_PATH/.git"
```

After `replace_placeholders_legacy` runs, the state sent to the API becomes:

```bash
#!/usr/bin/env bash
REPO_PATH=""
rm -rf "/.git"
echo "Deleted /.git"
```

All `$REPO_PATH`, `$0`, `$1` references are stripped or emptied.

## Root Cause

`buffer_manager.replace_placeholders_legacy` (line 606) calls
`replace_placeholders` with `clear_unresolved=True` (line 608). The
`clear_unresolved` logic (lines 586–594) removes all unresolved `$VAR` and
`${VAR}` patterns from the text:

```python
# 3. Braced base: ${var} or {var}
text_prompt = re.sub(r'\$?\{[a-zA-Z_]\w*\}', "", text_prompt)
# 4. Unbraced base: $var
text_prompt = re.sub(r'\$[a-zA-Z_]\w*\b', "", text_prompt)
```

This is applied to the full command string at line 2565 of
`chatybot_app.py` before `handle_escape_command` is called:

```python
processed_command = self.buffer_manager.replace_placeholders_legacy(command)
```

The skip list at line 2562 exempts `/setvar`, `/calc`, and `/str_search`
from this substitution because they handle it internally. `/decide` is not
on this list.

## Impact

- Bash scripts passed as `/decide` state via `${VAR}` have their own
  `$` variables stripped, corrupting the content sent to the decision model.
- Any state content containing `$` followed by a word character is
  affected, not just bash scripts.
- The decision model evaluates corrupted content, potentially producing
  incorrect safety assessments.

## Possible Approaches

1. **Add `/decide` to the skip list** at line 2562 and handle variable
   substitution internally in `cmd_decide`, substituting only the state
   argument's `${VAR}` references while leaving the content intact.

2. **Use a placeholder-aware substitution** that only replaces known
   script variables and leaves unknown `$VAR` patterns in place (i.e.
   `clear_unresolved=False` for `/decide`).

3. **Escape `$` in state content** before substitution and unescape after,
   though this is fragile.

## Related Files

- `src/chatybot/buffer_manager.py:490` — `replace_placeholders`
- `src/chatybot/buffer_manager.py:606` — `replace_placeholders_legacy`
- `src/chatybot/chatybot_app.py:2562` — skip list for substitution
- `src/chatybot/commands/decide.py:46` — combined regex parser
