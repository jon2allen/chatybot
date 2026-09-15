#!/bin/bash
# Run the chatybot function analyzer against the src/ directory.
# Writes a JSON report to code_analysis/report.json and prints the text report.
#
# Usage:
#   ./code_analysis/run_analysis.sh              # default: scan src/
#   ./code_analysis/run_analysis.sh --include-tests  # also report test functions
#   ./code_analysis/run_analysis.sh src test scripts  # scan custom paths

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ANALYZER="$SCRIPT_DIR/analyze_functions.py"
REPORT="$SCRIPT_DIR/report.json"

cd "$PROJECT_ROOT"

python3 "$ANALYZER" "$@" --json "$REPORT"
echo ""
echo "JSON report written to: $REPORT"
