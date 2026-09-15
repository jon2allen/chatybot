# Code Analysis Tools

Static analysis utilities for the chatybot codebase.

## analyze_functions.py

A zero-dependency Python AST analyzer that reports, per function/method:

- **Qualified name** (`module.Class.method` or `module.func`)
- **Source file and line range**
- **Lines of code** (body only, excluding blank lines and comments)
- **Call count** (static, best-effort — how often the function is called or referenced)
- **Dead code candidates** (functions defined but never called or referenced)

### What it detects as "alive"

To reduce false positives, the analyzer treats a function as alive if any of these are true:

- It is called anywhere in the scanned source (by simple name)
- It is passed as a reference (callbacks, registrations, serializer defaults)
- It is assigned to an attribute (monkeypatches like `mp.to_number = _patched_to_number`)
- It is listed in a `tools_config.toml` `function = "..."` entry (dynamically loaded tools)
- It is a method on a class with non-builtin bases (protocol/framework overrides)
- It is a nested function whose enclosing function is called (decorator inner wrappers)
- It is called from test files (auto-scans sibling `test/` directories)
- It is a dunder method, decorated function, test function, or known entry point

### What it cannot see

These remain inherent limitations of static AST analysis:

- **String-based dispatch** — `getattr(obj, "method_name")` or `registry["name"]` lookups
- **`__all__` exports** — functions exported in `__all__` for external consumers are not whitelisted
- **Cross-project callers** — if chatybot is imported as a library by external code

The dead list is a **candidate list for human review**, not a verdict.

### Usage

```bash
# Basic scan of src/ (default), excludes test files from function listing
# but still scans them for call references
python3 analyze_functions.py src

# Include test functions in the report
python3 analyze_functions.py src --include-tests

# Scan multiple paths
python3 analyze_functions.py src test scripts

# Exclude additional globs
python3 analyze_functions.py src --exclude "*_old.py" --exclude "test_*"

# Export full results as JSON
python3 analyze_functions.py src --json report.json

# Show top N in the largest/most-called sections
python3 analyze_functions.py src --top 50

# Disable sibling test directory scanning
python3 analyze_functions.py src --no-test-refs
```

### Output sections

1. **Summary** — total functions, called/referenced count, dead candidate count
2. **Top N largest functions** — by lines of code
3. **Top N most-called functions** — by call/reference count
4. **Dead function candidates** — sorted by LOC, with file and line number
5. **Call-count distribution** — histogram of call frequencies

### JSON output

With `--json OUT`, writes a JSON file with:

```json
{
  "summary": {
    "total_functions": 717,
    "dead_candidates": 19
  },
  "functions": [
    {
      "qualname": "src.chatybot.dispatcher.load_configs",
      "name": "load_configs",
      "file": "src/chatybot/dispatcher.py",
      "lineno": 24,
      "end_lineno": 40,
      "loc": 14,
      "is_method": false,
      "is_async": false,
      "is_decorated": false,
      "is_test": false,
      "is_override": false,
      "enclosing_func": "",
      "call_count": 1
    },
    ...
  ]
}
```

### Run script

Use `run_analysis.sh` to run the analyzer against the chatybot codebase with sensible defaults:

```bash
./code_analysis/run_analysis.sh
```

This scans `src/`, writes a JSON report to `code_analysis/report.json`, and prints the text report to stdout.
