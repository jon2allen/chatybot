#!/usr/bin/env python3
"""
chatybot function analyzer.

For a given tree of Python source it reports, per function/method:
  - qualified name (module.qualname)
  - source file and line range
  - size in lines of code (body only, excluding decorator/def line noise)
  - number of call sites that reference it (static, best-effort)
  - whether it appears to be dead (defined but never called)

Usage:
  python analyze_functions.py [PATH ...] [--exclude GLOB ...] [--no-tests]
                              [--json OUT] [--top N]

Defaults: scans ./src, excludes venv/site-packages/__pycache__/.git.

Limitations (inherent to static AST analysis):
  - Dynamic dispatch (getattr, __getattr__, plugin registries, callbacks
    wired by string name) is invisible, so "dead" is a *candidate* list,
    not a verdict. Entry points, dunders, decorated, and test functions are
    excluded from the dead list to reduce false positives.
  - Call counting matches by simple name. `self.foo()` and `obj.foo()` both
    count toward a method named `foo`; a bare `foo()` counts toward a
    top-level function named `foo`. Cross-module calls of the form
    `module.foo()` count toward `foo`.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from fnmatch import fnmatch
from pathlib import Path


# Names that are invoked by Python itself or by frameworks, so a lack of
# explicit call sites does not mean they are dead.
DUNDER_WHITELIST = {
    "__init__", "__new__", "__del__", "__call__", "__str__", "__repr__",
    "__len__", "__iter__", "__next__", "__getitem__", "__setitem__",
    "__delitem__", "__contains__", "__eq__", "__ne__", "__lt__", "__le__",
    "__gt__", "__ge__", "__hash__", "__bool__", "__enter__", "__exit__",
    "__aenter__", "__aexit__", "__aiter__", "__anext__", "__getattr__",
    "__setattr__", "__delattr__", "__getattribute__", "__get__", "__set__",
    "__delete__", "__class_getitem__", "__instancecheck__", "__subclasscheck__",
    "__missing__", "__post_init__", "__getstate__", "__setstate__",
    "__reduce__", "__reduce_ex__", "__copy__", "__deepcopy__",
    "__format__", "__dir__", "__sizeof__", "__index__", "__int__", "__float__",
    "__complex__", "__round__", "__trunc__", "__floor__", "__ceil__", "__abs__",
    "__pos__", "__neg__", "__invert__", "__add__", "__radd__", "__sub__",
    "__rsub__", "__mul__", "__rmul__", "__truediv__", "__rtruediv__",
    "__floordiv__", "__rfloordiv__", "__mod__", "__rmod__", "__pow__",
    "__rpow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__",
    "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__",
    "__iadd__", "__isub__", "__imul__", "__itruediv__", "__ifloordiv__",
    "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__",
    "__ior__", "__ixor__", "__matmul__", "__rmatmul__", "__imatmul__",
    "__divmod__", "__rdivmod__", "__radd__", "__cmp__", "__rcmp__",
    "__div__", "__rdiv__", "__nonzero__", "__divmod__",
}

# Heuristic entry-point names that are called from outside the codebase
# (CLI, scripts, framework hooks) and so should never be flagged dead.
ENTRY_POINT_NAMES = {
    "main", "run", "app", "create_app", "cli", "setup", "register",
    "load_ipython_extension", "pytest_collection_modifyitems",
}


@dataclass
class FuncInfo:
    qualname: str          # module.Class.method or module.func
    name: str              # simple name
    file: str              # relative path
    lineno: int            # def line (1-based)
    end_lineno: int        # last line of function
    loc: int               # lines of code (body, blank/comment stripped)
    is_method: bool
    is_async: bool
    is_decorated: bool
    is_test: bool          # lives in a test file or named test_*
    is_override: bool = False  # method on a class with non-builtin bases
    enclosing_func: str = ""  # name of the function this is nested in, if any
    call_count: int = 0
    callers: list[str] = field(default_factory=list)


def is_test_path(path: Path) -> bool:
    parts = path.parts
    return "test" in parts or "tests" in parts or path.name.startswith("test_")


def loc_from_source(source_lines: list[str], start: int, end: int) -> int:
    count = 0
    for i in range(start - 1, end):
        if i >= len(source_lines):
            break
        line = source_lines[i].strip()
        if not line or line.startswith("#"):
            continue
        count += 1
    return count


def parse_toml_tool_names(paths: list[str]) -> set[str]:
    """Find *.toml files under the scan roots and extract `function = "x"`
    values. These are dynamically-loaded tool entry points that static
    call analysis cannot see."""
    names: set[str] = set()
    for root in paths:
        root_path = Path(root)
        if root_path.is_file():
            toml_files = [root_path] if root_path.suffix == ".toml" else []
        else:
            toml_files = list(root_path.rglob("*.toml"))
        for tf in toml_files:
            sp = tf.as_posix()
            if any(seg in sp for seg in (
                "site-packages", "__pycache__", "/.git/", "/venv/",
                "/.venv/", "/node_modules/",
            )):
                continue
            try:
                text = tf.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # lightweight scan: `function = "name"` lines. Avoids a toml
            # dependency; good enough for the common config shape.
            import re
            for m in re.finditer(r'^\s*function\s*=\s*["\']([^"\']+)["\']', text, re.M):
                names.add(m.group(1))
    return names


class Collector(ast.NodeVisitor):
    """Walks one module: records function defs, call targets, and references.

    A "reference" is a name used anywhere other than as the callable in a
    Call — e.g. passed as a callback argument, assigned to an attribute
    (monkeypatch), or used as a default. References count as "alive" just
    like calls, because they mean the function is reachable at runtime.
    """

    def __init__(self, rel_path: str, source_lines: list[str], is_test_file: bool):
        self.rel_path = rel_path
        self.source_lines = source_lines
        self.is_test_file = is_test_file
        self.functions: list[FuncInfo] = []
        self.call_targets: list[str] = []  # simple names that were called
        self.references: set[str] = set()  # names referenced but not called
        # stack of enclosing class names for qualname building
        self._class_stack: list[str] = []
        self._func_stack: list[str] = []  # enclosing function names
        # class names that have non-builtin bases (protocol/override candidates)
        self.override_classes: set[str] = set()

    def _qualname(self, name: str, module: str) -> str:
        if self._class_stack:
            return f"{module}." + ".".join(self._class_stack) + f".{name}"
        return f"{module}.{name}"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        # detect non-builtin inheritance -> methods are likely overrides
        if self._has_nonbuiltin_base(node.bases):
            self.override_classes.add(node.name)
        # visit decorators (e.g. @dataclass, @register) — they may call
        # factory functions that would otherwise look dead
        for dec in node.decorator_list:
            self.visit(dec)
        for item in node.body:
            self.visit(item)
        self._class_stack.pop()

    @staticmethod
    def _has_nonbuiltin_base(bases: list[ast.expr]) -> bool:
        BUILTINS = {"object", "ABC", "ABCMeta", "Enum", "IntEnum", "Flag",
                    "IntFlag", "Exception", "BaseException", "ValueError",
                    "TypeError", "RuntimeError", "dict", "list", "set",
                    "tuple", "str", "int", "float", "bytes"}
        for b in bases:
            name = None
            if isinstance(b, ast.Name):
                name = b.id
            elif isinstance(b, ast.Attribute):
                name = b.attr
            if name and name not in BUILTINS:
                return True
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_func(node, is_async=True)

    def _handle_func(self, node, is_async: bool) -> None:
        module = Path(self.rel_path).with_suffix("").as_posix().replace("/", ".")
        # collapse leading dots / __init__
        module_parts = [p for p in module.split(".") if p and p != "__init__"]
        module = ".".join(module_parts) or Path(self.rel_path).stem
        qualname = self._qualname(node.name, module)
        loc = loc_from_source(self.source_lines, node.lineno, node.end_lineno or node.lineno)
        is_method = bool(self._class_stack)
        is_decorated = bool(node.decorator_list)
        is_test = self.is_test_file or node.name.startswith("test_")
        is_override = is_method and any(
            c in self.override_classes for c in self._class_stack
        )
        enclosing = self._func_stack[-1] if self._func_stack else ""
        info = FuncInfo(
            qualname=qualname,
            name=node.name,
            file=self.rel_path,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            loc=loc,
            is_method=is_method,
            is_async=is_async,
            is_decorated=is_decorated,
            is_test=is_test,
            is_override=is_override,
            enclosing_func=enclosing,
        )
        self.functions.append(info)
        # visit decorators — @register_engine("grep") is a Call that must be
        # collected, otherwise the factory looks dead
        for dec in node.decorator_list:
            self.visit(dec)
        # recurse into nested functions
        self._func_stack.append(node.name)
        for item in node.body:
            self.visit(item)
        self._func_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        target = None
        func = node.func
        if isinstance(func, ast.Name):
            target = func.id
        elif isinstance(func, ast.Attribute):
            target = func.attr
        if target is not None:
            self.call_targets.append(target)
        # collect names passed as arguments / keyword values — these are
        # references (callbacks, registrations, serializers), not calls.
        for arg in node.args:
            self._collect_reference(arg)
        for kw in node.keywords:
            self._collect_reference(kw.value)
        self.generic_visit(node)

    def _collect_reference(self, expr: ast.expr) -> None:
        if isinstance(expr, ast.Name):
            self.references.add(expr.id)
        elif isinstance(expr, ast.Attribute):
            self.references.add(expr.attr)

    def visit_Assign(self, node: ast.Assign) -> None:
        # detect monkeypatch: `module.attr = func_name` (Attribute target,
        # Name value) — the RHS function is referenced/alive.
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute):
            for val in [node.value] if not isinstance(node.value, ast.Tuple) else (
                node.value.elts if isinstance(node.value, (ast.Tuple, ast.List)) else [node.value]
            ):
                self._collect_reference(val)
        self.generic_visit(node)


def iter_py_files(paths: list[str], excludes: list[str], include_tests: bool,
                   test_ref_only: bool = False):
    """Yield (path, is_test) pairs. When test_ref_only is True, test files
    are yielded (so their references/calls are collected) but flagged so the
    caller can skip reporting their functions."""
    seen = set()
    for root in paths:
        root_path = Path(root)
        if root_path.is_file() and root_path.suffix == ".py":
            files = [root_path]
        else:
            files = list(root_path.rglob("*.py"))
        for f in files:
            try:
                f = f.resolve()
            except OSError:
                continue
            if f in seen:
                continue
            seen.add(f)
            sp = f.as_posix()
            if any(
                seg in sp for seg in (
                    "site-packages", "__pycache__", "/.git/", "/venv/",
                    "/.venv/", "/node_modules/",
                )
            ):
                continue
            if any(fnmatch(sp, ex) or fnmatch(f.name, ex) for ex in excludes):
                continue
            is_test = is_test_path(f)
            if is_test and not include_tests and not test_ref_only:
                continue
            yield f, is_test


def _sibling_test_dirs(paths: list[str]) -> list[str]:
    """Find test/ or tests/ directories that sit next to the scanned roots,
    so their calls/references are collected even when the user only passes
    `src`."""
    extra = []
    for root in paths:
        root_path = Path(root)
        if root_path.is_file():
            continue
        for parent in [root_path.parent, root_path]:
            for cand in [parent / "test", parent / "tests"]:
                if cand.is_dir() and str(cand) not in paths and str(cand) not in extra:
                    extra.append(str(cand))
    return extra


def analyze(paths, excludes, include_tests, scan_test_refs=True) -> tuple[list[FuncInfo], dict[str, int], set[str]]:
    all_funcs: list[FuncInfo] = []
    call_counts: dict[str, int] = defaultdict(int)
    ref_names: set[str] = set()
    # auto-include sibling test dirs for reference scanning
    ref_paths = list(paths)
    if scan_test_refs and not include_tests:
        ref_paths = paths + _sibling_test_dirs(paths)
    for py, is_test in iter_py_files(ref_paths, excludes, include_tests,
                                     test_ref_only=not include_tests):
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"skip {py}: {e}", file=sys.stderr)
            continue
        try:
            tree = ast.parse(text, filename=str(py))
        except SyntaxError as e:
            print(f"parse error {py}: {e}", file=sys.stderr)
            continue
        rel = py.as_posix()
        try:
            rel = str(py.relative_to(Path.cwd()))
        except ValueError:
            pass
        lines = text.splitlines()
        collector = Collector(rel, lines, is_test)
        collector.visit(tree)
        # only collect functions from the user's paths (not auto-added test dirs)
        in_user_paths = any(py.is_relative_to(Path(p).resolve()) for p in paths)
        if in_user_paths and (not is_test or include_tests):
            all_funcs.extend(collector.functions)
        for t in collector.call_targets:
            call_counts[t] += 1
        ref_names.update(collector.references)
    # TOML-configured tool functions are alive
    toml_names = parse_toml_tool_names(paths)
    ref_names.update(toml_names)
    return all_funcs, call_counts, ref_names


def is_likely_entry_point(info: FuncInfo) -> bool:
    if info.name in ENTRY_POINT_NAMES:
        return True
    if info.name == "__main__":  # not a function but guard
        return True
    return False


def is_dead_candidate(info: FuncInfo, call_counts: dict[str, int],
                      ref_names: set[str] | None = None) -> bool:
    if call_counts.get(info.name, 0) > 0:
        return False
    if ref_names and info.name in ref_names:
        return False
    # nested function whose enclosing function is called/referenced is alive:
    # it is invoked by the enclosing function (e.g. a decorator inner wrapper)
    if info.enclosing_func and ref_names is not None:
        if call_counts.get(info.enclosing_func, 0) > 0 or info.enclosing_func in ref_names:
            return False
    if info.name in DUNDER_WHITELIST:
        return False
    if info.is_decorated:
        return False
    if info.is_test:
        return False
    if info.is_override:
        return False
    if is_likely_entry_point(info):
        return False
    return True


def print_report(funcs: list[FuncInfo], call_counts: dict[str, int],
                  ref_names: set[str], top: int):
    # attach call counts
    for f in funcs:
        f.call_count = call_counts.get(f.name, 0)

    total = len(funcs)
    dead = [f for f in funcs if is_dead_candidate(f, call_counts, ref_names)]
    called = [f for f in funcs if f.call_count > 0 or f.name in ref_names]
    uncalled = [f for f in funcs if f.call_count == 0 and f.name not in ref_names]

    print(f"=== chatybot function analysis ===")
    print(f"files scanned produced {total} functions/methods")
    print(f"called or referenced : {len(called)}")
    print(f"never called (raw)   : {len(uncalled)}")
    print(f"dead candidates      : {len(dead)}  (after excluding dunders, "
          f"decorators, tests, entry points, overrides, refs, toml tools)")
    print()

    print(f"--- top {top} largest functions (by LOC) ---")
    by_size = sorted(funcs, key=lambda f: f.loc, reverse=True)
    print(f"{'LOC':>5}  {'calls':>5}  {'kind':<7}  {'name'}")
    for f in by_size[:top]:
        kind = "async" if f.is_async else ("method" if f.is_method else "func")
        print(f"{f.loc:>5}  {f.call_count:>5}  {kind:<7}  {f.qualname}  ({f.file}:{f.lineno})")
    print()

    print(f"--- top {top} most-called functions ---")
    by_calls = sorted(funcs, key=lambda f: f.call_count, reverse=True)
    print(f"{'calls':>5}  {'LOC':>5}  {'kind':<7}  {'name'}")
    for f in by_calls[:top]:
        kind = "async" if f.is_async else ("method" if f.is_method else "func")
        print(f"{f.call_count:>5}  {f.loc:>5}  {kind:<7}  {f.qualname}  ({f.file}:{f.lineno})")
    print()

    print(f"--- dead function candidates ({len(dead)}) ---")
    if not dead:
        print("(none)")
    else:
        dead_sorted = sorted(dead, key=lambda f: f.loc, reverse=True)
        print(f"{'LOC':>5}  {'kind':<7}  {'name'}")
        for f in dead_sorted:
            kind = "async" if f.is_async else ("method" if f.is_method else "func")
            print(f"{f.loc:>5}  {kind:<7}  {f.qualname}  ({f.file}:{f.lineno})")
    print()

    # distribution
    print("--- call-count distribution ---")
    buckets = [0, 1, 2, 5, 10, 25, 50, 100]
    for lo, hi in zip(buckets, buckets[1:] + [10**9]):
        n = sum(1 for f in funcs if lo <= f.call_count < hi if hi != 10**9)
        label = f"{lo}-{hi-1}" if hi != 10**9 else f"{lo}+"
        if hi == 10**9:
            n = sum(1 for f in funcs if f.call_count >= lo)
        print(f"  {label:>8}: {n}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="chatybot function analyzer")
    ap.add_argument("paths", nargs="*", default=["src"],
                    help="dirs/files to scan (default: src)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="glob patterns to exclude (repeatable)")
    ap.add_argument("--include-tests", action="store_true",
                    help="also scan test files (excluded by default)")
    ap.add_argument("--no-test-refs", action="store_true",
                    help="do not auto-scan sibling test/ dirs for references")
    ap.add_argument("--json", metavar="OUT",
                    help="write full results as JSON to OUT")
    ap.add_argument("--top", type=int, default=20,
                    help="rows in the top-N sections (default 20)")
    args = ap.parse_args(argv)

    funcs, call_counts, ref_names = analyze(
        args.paths, args.exclude, args.include_tests,
        scan_test_refs=not args.no_test_refs,
    )
    print_report(funcs, call_counts, ref_names, args.top)

    if args.json:
        for f in funcs:
            f.call_count = call_counts.get(f.name, 0)
        data = {
            "summary": {
                "total_functions": len(funcs),
                "dead_candidates": len([f for f in funcs if is_dead_candidate(f, call_counts, ref_names)]),
            },
            "functions": [asdict(f) for f in funcs],
        }
        Path(args.json).write_text(json.dumps(data, indent=2))
        print(f"\nwrote JSON -> {args.json}")


if __name__ == "__main__":
    main()
