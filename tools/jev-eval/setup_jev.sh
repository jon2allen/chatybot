#!/usr/bin/env bash
#
# setup_jev.sh -- One-shot setup helper for TypeSafe Jev security policy engine
#
# Seeds ~/.config/chatybot/security.toml and jev_security.toml,
# checks or prompts for OPENROUTER_API_KEY, configures the selected engine mode,
# and runs a healthcheck.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}"

python3 -m chatybot.setup_jev "$@"
