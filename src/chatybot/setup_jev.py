"""Interactive setup wizard for Jev security engine and Chained Policy."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .env_utils import load_env_file

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

DEFAULT_CONFIG_PATH = Path("~/.config/chatybot/security.toml").expanduser()
DEFAULT_RUBRIC_PATH = Path("~/.config/chatybot/jev_security.toml").expanduser()
BUNDLED_SECURITY_TOML = Path(__file__).resolve().parent / "security" / "default_security.toml"
BUNDLED_RUBRIC_TOML = Path(__file__).resolve().parent / "security" / "default_jev_security.toml"
GLOBAL_ENV_FILE = Path("~/.config/chatybot/.env").expanduser()


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _check_and_prompt_api_key() -> str | None:
    """Check for OPENROUTER_API_KEY in env or ~/.config/chatybot/.env, prompt if missing."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key and GLOBAL_ENV_FILE.exists():
        loaded = load_env_file(GLOBAL_ENV_FILE, override=False)
        key = loaded.get("OPENROUTER_API_KEY", "")

    if key:
        masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "********"
        print(f"✓ Found OPENROUTER_API_KEY: {masked}")
        return key

    print("\n[!] OPENROUTER_API_KEY is not set.")
    print("    Jev uses the TypeSafe Jev model on OpenRouter to evaluate security rules.")
    print("    You can get an API key at: https://openrouter.ai/keys\n")

    try:
        entered = input("Enter your OPENROUTER_API_KEY (or press Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        entered = ""

    if entered:
        _ensure_dir(GLOBAL_ENV_FILE)
        sanitized_key = entered.replace('"', '\\"')
        with open(GLOBAL_ENV_FILE, "a", encoding="utf-8") as f:
            f.write(f'\n# Jev Security Policy Engine Key\nOPENROUTER_API_KEY="{sanitized_key}"\n')
        os.environ["OPENROUTER_API_KEY"] = entered
        print(f"✓ Saved OPENROUTER_API_KEY to {GLOBAL_ENV_FILE}")
        return entered

    print("⚠️  Continuing without setting OPENROUTER_API_KEY now.")
    print("   Make sure to export OPENROUTER_API_KEY before running Chatybot with Jev.")
    return None


def _seed_files() -> None:
    """Ensure ~/.config/chatybot/security.toml and jev_security.toml exist."""
    _ensure_dir(DEFAULT_CONFIG_PATH)

    if not DEFAULT_CONFIG_PATH.exists():
        if BUNDLED_SECURITY_TOML.exists():
            shutil.copy2(BUNDLED_SECURITY_TOML, DEFAULT_CONFIG_PATH)
            print(f"✓ Seeded {DEFAULT_CONFIG_PATH}")
    else:
        print(f"✓ Existing config found at {DEFAULT_CONFIG_PATH}")

    if not DEFAULT_RUBRIC_PATH.exists():
        if BUNDLED_RUBRIC_TOML.exists():
            shutil.copy2(BUNDLED_RUBRIC_TOML, DEFAULT_RUBRIC_PATH)
            print(f"✓ Seeded Jev rubric at {DEFAULT_RUBRIC_PATH}")
    else:
        print(f"✓ Existing Jev rubric found at {DEFAULT_RUBRIC_PATH}")

    log_dir = Path("~/.config/chatybot/logs").expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)


def _configure_security_toml(mode: str) -> None:
    """Update security.toml with the selected engine/chain mode."""
    with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Backup existing
    backup_path = DEFAULT_CONFIG_PATH.with_suffix(".toml.bak")
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 1. Update engine = "..."
    engine_val = "chain" if mode in ("shadow", "dual_enforce") else "jev"
    if re.search(r'^\s*engine\s*=', content, flags=re.MULTILINE):
        content = re.sub(r'^\s*engine\s*=\s*"[^"]*"', f'engine = "{engine_val}"', content, count=1, flags=re.MULTILINE)
    elif re.search(r'^\s*#\s*engine\s*=', content, flags=re.MULTILINE):
        content = re.sub(r'^\s*#\s*engine\s*=\s*"[^"]*"', f'engine = "{engine_val}"', content, count=1, flags=re.MULTILINE)
    else:
        content = f'engine = "{engine_val}"\n' + content

    # 2. Ensure [jev] section is active (replace or add)
    jev_block = f"""[jev]
rubric_path       = "{DEFAULT_RUBRIC_PATH}"
model             = "typesafe/jev-1.13"
timeout_seconds   = 2.5
on_error          = "auto"
mode              = "noul"
cache             = true
redact_secrets    = true
log_path          = "~/.config/chatybot/logs/jev_security.jsonl"
"""
    jev_section_active = re.search(r'^\s*\[jev\]', content, flags=re.MULTILINE)
    if jev_section_active:
        content = re.sub(r'\[jev\][\s\S]*?(?=\n\[|\Z)', jev_block.strip() + "\n", content, count=1)
    else:
        # Check if commented [jev] exists
        if "# [jev]" in content:
            pattern = re.compile(r'#\s*\[jev\][\s\S]*?(?=\n\s*\[|\n\s*#\s*\[|\Z)', re.MULTILINE)
            m = pattern.search(content)
            if m:
                content = content[:m.start()] + jev_block.strip() + "\n" + content[m.end():]
            else:
                content += "\n" + jev_block
        else:
            content += "\n" + jev_block

    # 3. Configure [chain] section if requested
    if mode in ("shadow", "dual_enforce"):
        jev_stage_mode = "shadow" if mode == "shadow" else "enforce"
        chain_block = f"""[chain]
stages = [
  {{ engine = "builtin", mode = "enforce" }},
  {{ engine = "jev",     mode = "{jev_stage_mode}"  }},
]
shadow_on_deny = true
log_path       = "~/.config/chatybot/logs/security_chain.jsonl"
redact_log     = true
"""
        chain_section_active = re.search(r'^\s*\[chain\]', content, flags=re.MULTILINE)
        if chain_section_active:
            content = re.sub(
                r'\[chain\][\s\S]*?(?=\n\[|\Z)',
                chain_block.strip() + "\n",
                content,
                count=1,
            )
        else:
            # Check for commented # [chain]
            if "# [chain]" in content:
                pattern = re.compile(r'#\s*\[chain\][\s\S]*?(?=\n\s*\[|\n\s*#\s*\[|\Z)', re.MULTILINE)
                m = pattern.search(content)
                if m:
                    content = content[:m.start()] + chain_block.strip() + "\n" + content[m.end():]
                else:
                    content += "\n" + chain_block
            else:
                content += "\n" + chain_block

    # Validate generated TOML
    tomllib.loads(content)

    with open(DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✓ Configured {DEFAULT_CONFIG_PATH} (engine = '{engine_val}')")


def _run_healthcheck() -> None:
    """Run a fast self-test using the configured engine."""
    print("\n[Running Jev Security Healthcheck]")
    try:
        from .security.manager import SecurityManager
        from .security.models import Verdict

        mgr = SecurityManager(config_path=str(DEFAULT_CONFIG_PATH), debug=False)
        banner = mgr.get_banner()
        print(f"  Active Policy Banner: {banner}")

        # Quick evaluation of benign command
        print("  Testing evaluation of 'git status'...")
        dec = mgr.evaluate("run_command", {"command": "git status"}, {"interactive": True})
        print(f"  Result: Verdict = {dec.verdict.value.upper()} ({dec.reason})")

        # Quick evaluation of denied command
        print("  Testing evaluation of 'cat /etc/shadow'...")
        dec_deny = mgr.evaluate("run_command", {"command": "cat /etc/shadow"}, {"interactive": True})
        print(f"  Result: Verdict = {dec_deny.verdict.value.upper()} ({dec_deny.reason})")

        if dec_deny.verdict == Verdict.DENY:
            print("\n✓ Healthcheck PASSED: Security policy engine is working properly.")
        else:
            print(f"\n⚠️  Healthcheck note: Protected path check returned {dec_deny.verdict.value.upper()}.")

    except Exception as exc:
        print(f"\n⚠️  Healthcheck warning: {exc}")
        print("   If network or API key issues occurred, check OPENROUTER_API_KEY.")


def main() -> int:
    """Run the interactive Jev setup assistant."""
    print("======================================================")
    print("          Chatybot Jev Security Setup Assistant       ")
    print("======================================================")
    print("This wizard configures the TypeSafe Jev AI policy engine")
    print("for autonomous tool inspection and safety guardrails.\n")

    # Step 1: Check / seed config and rubric
    print("[1/4] Preparing configuration and rubric files...")
    _seed_files()

    # Step 2: Check / prompt for API key
    print("\n[2/4] Checking OpenRouter API Key...")
    api_key = _check_and_prompt_api_key()

    # Step 3: Choose configuration mode
    print("\n[3/4] Select Deployment Mode:")
    print("  1) Recommended Trial (Chain: Builtin Enforce + Jev Shadow)")
    print("     Keeps Builtin rules in charge, logs Jev decisions in background.")
    print("     Zero risk of false-positive disruption; inspect with 'jev_eval.py --from-log'.")
    print("  2) Direct Jev Enforce (engine = 'jev')")
    print("     TypeSafe Jev model acts as the primary tool policy guardrail.")
    print("  3) Defense-in-Depth (Chain: Builtin Enforce + Jev Enforce)")
    print("     Both engines enforce policy; strictest verdict wins.")

    try:
        choice = input("\nSelect an option [1-3, default: 1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if choice == "2":
        mode = "direct_enforce"
    elif choice == "3":
        mode = "dual_enforce"
    else:
        mode = "shadow"

    print(f"\nConfiguring mode: {mode}...")
    _configure_security_toml(mode)

    # Step 4: Healthcheck
    print("\n[4/4] Verifying engine status...")
    _run_healthcheck()

    print("\n======================================================")
    print("Setup complete! Jev security configuration is active.")
    print("  - Configuration file: ~/.config/chatybot/security.toml")
    print("  - Security Rubric:    ~/.config/chatybot/jev_security.toml")
    print("  - Decision Logs:      ~/.config/chatybot/logs/")
    print("  - Trace payloads:     chatybot --security or /trace rawpayload on")
    print("  - Audit logs:         tools/jev-eval/jev_eval.py --from-log ~/.config/chatybot/logs/security_chain.jsonl")
    print("======================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
