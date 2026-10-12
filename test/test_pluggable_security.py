"""
Unit and Integration Tests for Pluggable Security Architecture
"""

import os
import sys
import tempfile
import pytest

from chatybot.security import (
    BuiltinPolicyEngine,
    PolicyDecision,
    PolicyRequest,
    SecurityManager,
    Verdict,
)
from chatybot.security.adapters.stdio_binary import StdioBinaryPolicyEngine


def test_builtin_policy_default_verdicts():
    """Verify default tri-state assignments."""
    engine = BuiltinPolicyEngine()

    # read_file -> allow
    dec = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/tmp/test.txt"}))
    assert dec.verdict == Verdict.ALLOW

    # write_file -> ask
    dec = engine.evaluate(PolicyRequest(tool="write_file", parameters={"path": "/tmp/test.txt"}))
    assert dec.verdict == Verdict.ASK
    assert dec.prompt_details is not None

    # run_command -> ask with high risk
    dec = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": "ls -la"}))
    assert dec.verdict == Verdict.ASK
    assert dec.prompt_details.risk_level == "high"


def test_builtin_policy_protected_path_denial():
    """Verify denial when attempting to access protected system paths."""
    engine = BuiltinPolicyEngine()

    dec = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/etc/passwd"}))
    assert dec.verdict == Verdict.DENY
    assert "protected path" in dec.reason

    dec = engine.evaluate(PolicyRequest(tool="write_file", parameters={"path": "~/.ssh/id_rsa"}))
    assert dec.verdict == Verdict.DENY
    assert "protected path" in dec.reason


def test_builtin_policy_dangerous_commands():
    """Verify hard denial on catastrophic shell commands."""
    engine = BuiltinPolicyEngine()

    dec = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": "rm -rf /"}))
    assert dec.verdict == Verdict.DENY
    assert "Dangerous command pattern" in dec.reason


def test_security_manager_custom_config():
    """Verify SecurityManager loads dedicated TOML config outside tools_config."""
    toml_content = """
version = "1.0"
engine = "builtin"
fail_safe = "deny"

[builtin]
default_verdict = "deny"

[builtin.rules]
read_file = "allow"
special_tool = "allow"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        cfg_path = f.name

    try:
        mgr = SecurityManager(config_path=cfg_path)
        assert mgr.evaluate("read_file").verdict == Verdict.ALLOW
        assert mgr.evaluate("special_tool").verdict == Verdict.ALLOW
        assert mgr.evaluate("unknown_tool").verdict == Verdict.DENY
    finally:
        if os.path.exists(cfg_path):
            os.remove(cfg_path)


def test_stdio_binary_adapter_with_mock_executable():
    """Verify external binary adapter executes child process and parses PolicyResponse."""
    # Create a small python script acting as an external binary policy guard
    guard_script = """#!/usr/bin/env python3
import sys, json

data = json.loads(sys.stdin.read())
tool = data.get("tool")
if tool == "blocked_by_guard":
    print(json.dumps({"status": "deny", "reason": "Blocked by external test binary"}))
else:
    print(json.dumps({"status": "allow", "reason": "Approved by external test binary"}))
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(guard_script)
        script_path = f.name

    os.chmod(script_path, 0o755)

    try:
        engine = StdioBinaryPolicyEngine(binary_path=script_path)
        
        dec1 = engine.evaluate(PolicyRequest(tool="blocked_by_guard"))
        assert dec1.verdict == Verdict.DENY
        assert "Blocked by external" in dec1.reason

        dec2 = engine.evaluate(PolicyRequest(tool="allowed_tool"))
        assert dec2.verdict == Verdict.ALLOW
        assert "Approved by external" in dec2.reason
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)


def test_security_dsl_rules():
    """Verify Security DSL parser and matching engine."""
    dsl_rules = [
        "do not read file with api_key in it",
        "never write file ending with .env",
        "ask before run command with sudo",
        "deny delete file in /var",
        "allow read file ending with .md because 'documentation is safe'",
    ]

    engine = BuiltinPolicyEngine(dsl_rules=dsl_rules)

    # 1. "do not read file with api_key in it"
    dec = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/tmp/my_api_key.txt"}))
    assert dec.verdict == Verdict.DENY
    assert "do not read file with api_key in it" in dec.reason

    # Clean file read should still be allowed
    dec_ok = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/tmp/normal_file.txt"}))
    assert dec_ok.verdict == Verdict.ALLOW

    # 2. "never write file ending with .env"
    dec_env = engine.evaluate(PolicyRequest(tool="write_file", parameters={"path": "/project/.env"}))
    assert dec_env.verdict == Verdict.DENY

    # 3. "ask before run command with sudo"
    dec_sudo = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": "sudo apt update"}))
    assert dec_sudo.verdict == Verdict.ASK
    assert dec_sudo.prompt_details.risk_level == "high"

    # 4. Explicit reason clause: "allow read file ending with .md because 'documentation is safe'"
    dec_md = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/docs/readme.md"}))
    assert dec_md.verdict == Verdict.ALLOW
    assert dec_md.reason == "documentation is safe"


def test_malformed_rule_emits_warning(caplog):
    """Verify malformed rules emit a runtime warning and valid rules continue functioning."""
    import logging

    dsl_rules = [
        "this is not a valid security rule whatsoever",
        "do not read file with secret in it",
    ]

    with caplog.at_level(logging.WARNING):
        engine = BuiltinPolicyEngine(dsl_rules=dsl_rules)

    # Check warning was emitted for the invalid rule
    assert any("Failed to parse rule #1 in security policy" in record.message for record in caplog.records)

    # Check valid rule still loaded and works
    dec_deny = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/tmp/my_secret.txt"}))
    assert dec_deny.verdict == Verdict.DENY


