#!/usr/bin/env bash
# Test harness for db_mgmt_util.py
#
# Generates broken fixtures from a known-good source database, then runs
# db_mgmt_util.py check against each fixture and the good source, verifying
# that exit codes match expectations.
#
# Usage:
#   ./run_db_mgmt_tests.sh [source_db] [fixtures_dir]
#
# Defaults:
#   source_db     ~/Downloads/3Kingdoms.json
#   fixtures_dir  scripts/test_fixtures
#
# Exit codes:
#   0  all tests passed
#   1  one or more tests failed
#   2  setup error (missing source, missing util, etc.)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE_DB="${1:-$SCRIPT_DIR/test_fixtures/large_json_test.json}"
FIXTURES_DIR="${2:-$SCRIPT_DIR/test_fixtures}"
UTIL="$SCRIPT_DIR/db_mgmt_util.py"
GEN="$SCRIPT_DIR/generate_db_fixtures.py"

# --- preflight checks -------------------------------------------------------

if [[ ! -f "$SOURCE_DB" ]]; then
    echo "ERROR: source database not found: $SOURCE_DB" >&2
    exit 2
fi

if [[ ! -f "$UTIL" ]]; then
    echo "ERROR: db_mgmt_util.py not found at $UTIL" >&2
    exit 2
fi

if [[ ! -f "$GEN" ]]; then
    echo "ERROR: generate_db_fixtures.py not found at $GEN" >&2
    exit 2
fi

PYTHON="${PYTHON:-python3}"

# --- generate fixtures ------------------------------------------------------

echo "=== Generating fixtures from $SOURCE_DB ==="
"$PYTHON" "$GEN" "$SOURCE_DB" "$FIXTURES_DIR"
echo ""

# --- run tests --------------------------------------------------------------

PASS_COUNT=0
FAIL_COUNT=0
FAILED_TESTS=()

run_test() {
    local label="$1"
    local db_path="$2"
    local expected_exit="$3"

    local actual_exit
    "$PYTHON" "$UTIL" check "$db_path" > /tmp/db_mgmt_test_out.txt 2>&1 || actual_exit=$? || true
    actual_exit=${actual_exit:-0}

    if [[ "$actual_exit" -eq "$expected_exit" ]]; then
        echo "  PASS  $label (exit=$actual_exit)"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "  FAIL  $label (expected exit=$expected_exit, got exit=$actual_exit)"
        echo "        --- output ---"
        sed 's/^/        /' /tmp/db_mgmt_test_out.txt
        echo "        --- end ---"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILED_TESTS+=("$label")
    fi
}

echo "=== Running tests ==="

# Good source — should pass.
run_test "good source (large_json_test.json)" "$SOURCE_DB" 0

# Read manifest and run each fixture.
# Use process substitution (not a pipe) so run_test executes in the current
# shell and counters persist.
MANIFEST="$FIXTURES_DIR/manifest.json"
if [[ ! -f "$MANIFEST" ]]; then
    echo "ERROR: manifest not found at $MANIFEST" >&2
    exit 2
fi

while IFS=$'\t' read -r filename description expected_exit; do
    run_test "$description" "$FIXTURES_DIR/$filename" "$expected_exit"
done < <("$PYTHON" -c "
import json
with open('$MANIFEST') as f:
    for entry in json.load(f):
        print(f\"{entry['file']}\t{entry['description']}\t{entry['expected_exit']}\")
")

# File not found — should fail.
run_test "file not found" "$FIXTURES_DIR/does_not_exist.json" 1

# --- summary ----------------------------------------------------------------

echo ""
echo "=== Summary ==="
echo "  Passed: $PASS_COUNT"
echo "  Failed: $FAIL_COUNT"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
    echo "  Failed tests:"
    for t in "${FAILED_TESTS[@]}"; do
        echo "    - $t"
    done
    exit 1
fi

echo "  All tests passed."
exit 0
