#!/usr/bin/env python3
"""Generate broken database fixtures from a known-good TinyDB file.

Each fixture introduces a single class of corruption so the integrity
checker can be tested in isolation.  Run with:

    python3 generate_db_fixtures.py <source.json> <output_dir>

If <output_dir> already contains fixtures they are overwritten.
"""

import json
import os
import sys


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _save_raw(text: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# Fixture generators
# ---------------------------------------------------------------------------

# Each entry: (filename, description, generator function)
# Generator functions receive (data, src_path) and return either a dict to
# json.dump or a string to write raw.


def gen_truncated(data, src_path) -> str:
    """Truncated JSON — file cut mid-content."""
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()[:5000]


def gen_no_table(data, src_path) -> dict:
    """Missing 'items' table — data stored under wrong key."""
    return {"_default": data["items"]}


def gen_missing_field(data, src_path) -> dict:
    """Record 5 is missing the 'content' field."""
    d = json.loads(json.dumps(data))  # deep copy
    del d["items"]["5"]["content"]
    return d


def gen_wrong_type(data, src_path) -> dict:
    """Record 10 has metadata as a string instead of a dict."""
    d = json.loads(json.dumps(data))
    d["items"]["10"]["metadata"] = "not a dict"
    return d


def gen_gap(data, src_path) -> dict:
    """Gap in doc_id sequence — record 20 deleted."""
    d = json.loads(json.dumps(data))
    del d["items"]["20"]
    return d


def gen_bad_meta_type(data, src_path) -> dict:
    """Record 3 has thinking_tokens as a string instead of int."""
    d = json.loads(json.dumps(data))
    d["items"]["3"]["metadata"]["thinking_tokens"] = "five"
    return d


def gen_duplicate_id(data, src_path) -> dict:
    """Duplicate doc_id — copy record 1 to a new key '1' won't work in JSON,
    so instead copy record 1's content into record 2, making id 2 a dup of 1
    conceptually.  For a true duplicate-key test we corrupt by inserting a
    second key that parses to the same int (e.g. "01")."""
    d = json.loads(json.dumps(data))
    d["items"]["01"] = d["items"]["1"]
    return d


def gen_non_dict_record(data, src_path) -> dict:
    """Record 15 is a string instead of a dict."""
    d = json.loads(json.dumps(data))
    d["items"]["15"] = "this should be a dict"
    return d


def gen_missing_metadata_key(data, src_path) -> dict:
    """Record 7 is missing the 'metadata' field entirely."""
    d = json.loads(json.dumps(data))
    del d["items"]["7"]["metadata"]
    return d


# (filename, description, generator, expected_exit_code)
FIXTURES = [
    ("truncated.json", "Truncated JSON (cut mid-file)", gen_truncated, 1),
    ("no_table.json", "Missing 'items' table", gen_no_table, 1),
    ("missing_field.json", "Record missing required field 'content'", gen_missing_field, 1),
    ("wrong_type.json", "metadata is str instead of dict", gen_wrong_type, 1),
    ("gap.json", "Gap in doc_id sequence (id 20 deleted)", gen_gap, 1),
    ("bad_meta_type.json", "thinking_tokens is str instead of int", gen_bad_meta_type, 1),
    ("duplicate_id.json", "Duplicate doc_id (key '01' shadows '1')", gen_duplicate_id, 1),
    ("non_dict_record.json", "Record 15 is a string not a dict", gen_non_dict_record, 1),
    ("missing_metadata.json", "Record 7 missing 'metadata' field", gen_missing_metadata_key, 1),
]


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(f"Usage: {sys.argv[0]} <source.json> <output_dir>", file=sys.stderr)
        return 2

    src_path, out_dir = argv
    if not os.path.isfile(src_path):
        print(f"Source file not found: {src_path}", file=sys.stderr)
        return 2

    os.makedirs(out_dir, exist_ok=True)
    data = _load(src_path)

    manifest = []
    for filename, desc, gen, expected_exit in FIXTURES:
        out_path = os.path.join(out_dir, filename)
        result = gen(data, src_path)
        if isinstance(result, str):
            _save_raw(result, out_path)
        else:
            _save(result, out_path)
        manifest.append((filename, desc, expected_exit))
        print(f"  created {filename:30s} — {desc}")

    # Write manifest for the test harness to consume.
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            [{"file": fn, "description": desc, "expected_exit": code}
             for fn, desc, code in manifest],
            f,
            indent=2,
        )
    print(f"\nManifest written to {manifest_path}")
    print(f"Generated {len(manifest)} fixtures in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
