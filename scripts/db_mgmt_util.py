#!/usr/bin/env python3
"""Database management utility for chatybot TinyDB files.

Subcommands:
  check    Validate schema and data integrity of a .json database file.

Future subcommands can be added by registering a handler in _SUBCOMMANDS.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------

# Top-level TinyDB table name used by CorpusManager.
TABLE_NAME = "items"

# Required top-level fields in every record.
REQUIRED_FIELDS = ("type", "name", "content", "metadata")

# Expected types for each top-level field.
FIELD_TYPES: dict[str, type] = {
    "type": str,
    "name": str,
    "content": str,
    "metadata": dict,
}

# Known metadata keys and their expected types.
# None in the tuple means the value may be None in addition to the listed types.
METADATA_SCHEMA: dict[str, tuple[type, ...]] = {
    "timestamp": (str,),
    "model_alias": (str,),
    "model_name": (str,),
    "prompt": (str,),
    "thinking_content": (str, type(None)),
    "thinking_tokens": (int, type(None)),
    "reasoning_effort": (str, type(None)),
}


# ---------------------------------------------------------------------------
# Check result types
# ---------------------------------------------------------------------------


@dataclass
class RecordError:
    doc_id: str
    field: str
    message: str


@dataclass
class CheckReport:
    path: str
    file_exists: bool = False
    file_size: int = 0
    parse_error: str | None = None
    table_present: bool = False
    table_type: str | None = None  # "dict", "list", or other
    total_records: int = 0
    valid_records: int = 0
    last_good_doc_id: str | None = None
    errors: list[RecordError] = field(default_factory=list)
    sequence_errors: list[str] = field(default_factory=list)

    @property
    def broken_records(self) -> int:
        return len({e.doc_id for e in self.errors})

    def print_summary(self) -> None:
        print("=" * 70)
        print("DATABASE INTEGRITY REPORT")
        print("=" * 70)
        print(f"File:            {self.path}")
        if not self.file_exists:
            print(f"Status:          FILE NOT FOUND")
            print("=" * 70)
            return
        print(f"Size:            {self.file_size:,} bytes")
        if self.parse_error:
            print(f"Status:          PARSE ERROR")
            print(f"Error:           {self.parse_error}")
            print("=" * 70)
            return
        print(f"Table:           {TABLE_NAME} ({'present' if self.table_present else 'MISSING'})")
        if self.table_present:
            print(f"Total records:   {self.total_records}")
            print(f"Valid records:   {self.valid_records}")
            print(f"Broken records:  {self.broken_records}")
            print(f"Last good ID:    {self.last_good_doc_id if self.last_good_doc_id is not None else 'none'}")
        print("-" * 70)

        if self.sequence_errors:
            print("SEQUENCE ERRORS:")
            for msg in self.sequence_errors:
                print(f"  - {msg}")
            print("-" * 70)

        if self.errors:
            print("RECORD ERRORS:")
            for err in self.errors:
                print(f"  doc_id={err.doc_id}  field='{err.field}'  {err.message}")
            print("-" * 70)

        is_pass = (
            not self.errors
            and not self.sequence_errors
            and not self.parse_error
            and self.file_exists
            and self.table_present
        )
        status = "PASS" if is_pass else "FAIL"
        print(f"Overall:         {status}")
        print("=" * 70)


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------


def _check_type(value: Any, expected_types: tuple[type, ...]) -> bool:
    return isinstance(value, expected_types)


def _validate_record(doc_id: str, record: Any) -> list[RecordError]:
    """Validate a single record against the schema. Returns a list of errors."""
    errors: list[RecordError] = []

    if not isinstance(record, dict):
        errors.append(RecordError(doc_id, "_root", f"record is {type(record).__name__}, expected dict"))
        return errors

    # Check required fields are present.
    for fname in REQUIRED_FIELDS:
        if fname not in record:
            errors.append(RecordError(doc_id, fname, "missing required field"))

    # Check field types for fields that are present.
    for fname, expected_type in FIELD_TYPES.items():
        if fname in record:
            if not isinstance(record[fname], expected_type):
                errors.append(
                    RecordError(
                        doc_id,
                        fname,
                        f"expected {expected_type.__name__}, got {type(record[fname]).__name__}",
                    )
                )

    # Validate metadata keys if metadata is a dict.
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        for key, expected_types in METADATA_SCHEMA.items():
            if key in metadata:
                val = metadata[key]
                if not _check_type(val, expected_types):
                    type_names = " | ".join(t.__name__ for t in expected_types)
                    errors.append(
                        RecordError(
                            doc_id,
                            f"metadata.{key}",
                            f"expected {type_names}, got {type(val).__name__}",
                        )
                    )

    return errors


def _check_sequence(doc_ids: list[str]) -> list[str]:
    """Check that doc_ids are sequential integers starting from 1 with no gaps."""
    errors: list[str] = []
    seen = set()
    for did in doc_ids:
        if did in seen:
            errors.append(f"duplicate doc_id: {did}")
        seen.add(did)

    try:
        int_ids = sorted(int(d) for d in doc_ids)
    except ValueError:
        errors.append("one or more doc_ids are not valid integers")
        return errors

    expected = list(range(1, len(int_ids) + 1))
    if int_ids != expected:
        missing = set(expected) - set(int_ids)
        extra = set(int_ids) - set(expected)
        if missing:
            errors.append(f"gap in sequence — missing IDs: {sorted(missing)}")
        if extra:
            errors.append(f"unexpected IDs beyond expected range: {sorted(extra)}")
    return errors


def check_database(path: str) -> CheckReport:
    """Run full integrity check on a database file. Returns a CheckReport."""
    report = CheckReport(path=path)

    if not os.path.exists(path):
        return report

    report.file_exists = True
    report.file_size = os.path.getsize(path)

    # Parse JSON.
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        report.parse_error = f"JSON decode error at line {e.lineno}, col {e.colno}: {e.msg}"
        return report
    except Exception as e:
        report.parse_error = f"{type(e).__name__}: {e}"
        return report

    if not isinstance(data, dict):
        report.parse_error = f"top-level structure is {type(data).__name__}, expected dict"
        return report

    # Check for the items table.
    if TABLE_NAME not in data:
        report.table_present = False
        return report

    report.table_present = True
    items = data[TABLE_NAME]

    if not isinstance(items, dict):
        report.table_type = type(items).__name__
        report.parse_error = f"'{TABLE_NAME}' table is {type(items).__name__}, expected dict"
        return report
    report.table_type = "dict"

    doc_ids = list(items.keys())
    report.total_records = len(doc_ids)

    # Validate each record in insertion order.
    for doc_id in doc_ids:
        record = items[doc_id]
        record_errors = _validate_record(doc_id, record)
        if record_errors:
            report.errors.extend(record_errors)
        else:
            report.valid_records += 1
            report.last_good_doc_id = doc_id

    # Check ID sequence integrity.
    report.sequence_errors = _check_sequence(doc_ids)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_check(args: argparse.Namespace) -> int:
    report = check_database(args.path)
    report.print_summary()
    if args.output:
        _write_json_report(report, args.output)
        print(f"Report written to {args.output}")
    if report.errors or report.sequence_errors or report.parse_error or not report.file_exists or not report.table_present:
        return 1
    return 0


def _write_json_report(report: CheckReport, out_path: str) -> None:
    payload = {
        "path": report.path,
        "file_exists": report.file_exists,
        "file_size": report.file_size,
        "parse_error": report.parse_error,
        "table_present": report.table_present,
        "table_type": report.table_type,
        "total_records": report.total_records,
        "valid_records": report.valid_records,
        "broken_records": report.broken_records,
        "last_good_doc_id": report.last_good_doc_id,
        "sequence_errors": report.sequence_errors,
        "errors": [
            {"doc_id": e.doc_id, "field": e.field, "message": e.message}
            for e in report.errors
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="db_mgmt_util",
        description="Database management utility for chatybot TinyDB files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check
    check_parser = subparsers.add_parser(
        "check",
        help="Validate schema and data integrity of a .json database file.",
    )
    check_parser.add_argument("path", help="Path to the .json database file")
    check_parser.add_argument(
        "-o", "--output",
        help="Write a machine-readable JSON report to this path",
        default=None,
    )
    check_parser.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
