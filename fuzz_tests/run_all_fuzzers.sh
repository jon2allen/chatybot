#!/bin/bash
# Run all Atheris fuzzers serially with CPU cooldown between runs
# Usage: ./run_all_fuzzers.sh [max_len] [runs]
#   max_len: Maximum input length (default: 300)
#   runs:    Number of fuzzing iterations per fuzzer (default: 10000)
# Example: ./run_all_fuzzers.sh 500 5000

set -e

# Defaults
MAX_LEN=300
RUNS=10000

# Parse optional arguments
if [ $# -ge 1 ]; then
    MAX_LEN=$1
fi
if [ $# -ge 2 ]; then
    RUNS=$2
fi

echo "=========================================="
echo "  Atheris Fuzzing for chatybot BufferManager"
echo "  Running all fuzzers serially with max_len=$MAX_LEN runs=$RUNS"
echo "  Press Ctrl+C to stop"
echo "=========================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

export PYTHONPATH=.":$PYTHONPATH"

# Use the python that has atheris installed
#PYTHON=/opt/homebrew/opt/python@3.11/bin/python3.11
PYTHON=python3
# Create crashes directory
mkdir -p crashes

FUZZERS=(
    "fuzz_placeholders.py"
    "fuzz_crash_test.py"
    "fuzz_file_loading.py"
    "fuzz_format_detection.py"
    "fuzz_bank_operations.py"
)

for fuzzer in "${FUZZERS[@]}"; do
    echo "=========================================="
    echo "[+] Starting $fuzzer at $(date)"
    echo "=========================================="
    
    $PYTHON "$SCRIPT_DIR/$fuzzer" "$SCRIPT_DIR/corpus" -max_len=$MAX_LEN -atheris_runs=$RUNS -ignore_crashes=1 -artifact_prefix="$SCRIPT_DIR/../crashes/$fuzzer"
    
    echo ""
    echo "[+] Completed $fuzzer at $(date)"
    echo "[+] Waiting 5 seconds for CPU cooldown..."
    sleep 5
    echo ""
done

echo "=========================================="
echo "All fuzzers completed at $(date)"
echo "=========================================="
