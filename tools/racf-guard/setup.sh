#!/usr/bin/env bash
#
# setup.sh -- One-shot setup helper for racf-guard security engine
#
# Builds the Rust binary, copies the seed policy to ~/.config/chatybot/,
# connects the current OS user to the DEVELOPER group, and patches
# security.toml to use engine = "binary".
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHATYBOT_CONFIG_DIR="${HOME}/.config/chatybot"
SECURITY_TOML="${CHATYBOT_CONFIG_DIR}/security.toml"
SECURITY_RACF="${CHATYBOT_CONFIG_DIR}/security.racf"
BINARY_PATH="${SCRIPT_DIR}/target/release/racf-guard"
SEED_POLICY="${SCRIPT_DIR}/examples/security.racf"

CURRENT_USER="${USER:-${LOGNAME:-${USERNAME:-$(whoami 2>/dev/null || echo 'unknown')}}}"

echo "=== racf-guard Setup ==="
echo "  Repo root:       ${REPO_ROOT}"
echo "  Config dir:      ${CHATYBOT_CONFIG_DIR}"
echo "  Current user:    ${CURRENT_USER}"
echo ""

# --- Step 1: Build the binary ---
echo "[1/4] Building racf-guard binary..."
if ! command -v cargo >/dev/null 2>&1; then
    echo "ERROR: Rust toolchain (cargo) not found. Install from https://rustup.rs"
    exit 1
fi
cd "$SCRIPT_DIR"
cargo build --release
echo "  Binary: ${BINARY_PATH}"
echo ""

# --- Step 2: Copy seed policy ---
echo "[2/4] Copying seed policy..."
mkdir -p "$CHATYBOT_CONFIG_DIR"
if [ -f "$SECURITY_RACF" ]; then
    echo "  Existing policy found at ${SECURITY_RACF} -- backing up"
    cp "$SECURITY_RACF" "${SECURITY_RACF}.bak.$(date +%s)"
fi
cp "$SEED_POLICY" "$SECURITY_RACF"
echo "  Policy: ${SECURITY_RACF}"
echo ""

# --- Step 3: Connect current user to DEVELOPER group ---
echo "[3/4] Connecting user '${CURRENT_USER}' to DEVELOPER group..."
if grep -q "CONNECT ${CURRENT_USER} GROUP(DEVELOPER)" "$SECURITY_RACF" 2>/dev/null; then
    echo "  User '${CURRENT_USER}' already connected to DEVELOPER -- skipping"
else
    echo "CONNECT ${CURRENT_USER} GROUP(DEVELOPER)" >> "$SECURITY_RACF"
    echo "  Added: CONNECT ${CURRENT_USER} GROUP(DEVELOPER)"
fi
echo ""

# --- Step 4: Patch security.toml to use binary engine ---
echo "[4/4] Configuring security.toml for engine = binary..."

# Seed default security.toml if it does not exist
if [ ! -f "$SECURITY_TOML" ]; then
    echo "  No security.toml found -- seeding from bundled default"
    cp "${REPO_ROOT}/src/chatybot/security/default_security.toml" "$SECURITY_TOML"
fi

# Use Python to patch the TOML reliably (handles quoting, comments, etc.)
python3 - "$SECURITY_TOML" "$BINARY_PATH" "$SECURITY_RACF" <<'PYEOF'
import sys, re

toml_path = sys.argv[1]
binary_path = sys.argv[2]
policy_path = sys.argv[3]

with open(toml_path, "r") as f:
    content = f.read()

# Set engine = "binary"
content = re.sub(r'^engine\s*=\s*"[^"]*"', 'engine = "binary"', content, count=1, flags=re.MULTILINE)

# Replace [binary] path and args
content = re.sub(
    r'path\s*=\s*"[^"]*"\s*\n\s*timeout_seconds\s*=\s*[\d.]+\s*\n\s*args\s*=\s*\[[^\]]*\]',
    f'path = "{binary_path}"\ntimeout_seconds = 2.0\nargs = ["--policy", "{policy_path}"]',
    content,
    count=1,
)

with open(toml_path, "w") as f:
    f.write(content)
PYEOF

echo "  Config: ${SECURITY_TOML}"
echo "  Engine: binary"
echo "  Binary: ${BINARY_PATH}"
echo "  Policy: ${SECURITY_RACF}"
echo ""

# --- Verify ---
echo "=== Verification ==="
echo "$BINARY_PATH" --policy "$SECURITY_RACF" --banner
echo ""
echo "Test a tool evaluation:"
echo '{"tool":"git.status","context":{"user":"'"$CURRENT_USER"'"}}' | "$BINARY_PATH" --policy "$SECURITY_RACF"
echo ""
echo "=== Setup complete ==="
echo "Chatybot will now use racf-guard as its security policy engine."
echo "Run 'chatybot --security' to see verbose security debug traces."
