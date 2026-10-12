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


def test_security_manager_seeds_default_config(capsys):
    """Verify that SecurityManager copies default_security.toml and notifies the user."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_cfg = os.path.join(tmp_dir, "nonexistent", "security.toml")
        assert not os.path.exists(target_cfg)

        mgr = SecurityManager(config_path=target_cfg)

        # File should now have been seeded
        assert os.path.exists(target_cfg)
        with open(target_cfg, "r") as f:
            content = f.read()
            assert "dsl_rules" in content
            assert "do not read file with api_key in it" in content

        # Verify user was notified via console print
        captured = capsys.readouterr()
        assert "[Security Sync] Initialized local 'security.toml'" in captured.out


def test_security_debug_mode_shows_parsed_definitions_and_actions(capsys):
    """Verify debug mode prints each parsed definition with tier labels and special deny/accept actions."""
    rules = [
        "do not read file with api_key in it",
        "allow read file ending with .md because 'docs are safe'",
    ]
    engine = BuiltinPolicyEngine(dsl_rules=rules, debug=True)

    # Verify loading and definition output
    init_out = capsys.readouterr().out
    assert "[Security Debug] Parsing and compiling 2 Security DSL rule definitions..." in init_out
    assert "[Definition #1] [SPECIAL DENY (Tier 1)] Raw: 'do not read file with api_key in it'" in init_out
    assert "Parsed: action=DENY, tool=read_file, match=(path contains 'api_key')" in init_out
    assert "[Definition #2] [SPECIAL ACCEPT (Tier 3)] Raw: 'allow read file ending with .md because 'docs are safe''" in init_out
    assert "reason='docs are safe'" in init_out
    assert "[Definition: Path] [SPECIAL DENY]" in init_out
    assert "[Definition: Command Pattern] [SPECIAL DENY]" in init_out
    assert "[Definition: Baseline Tool] [ACCEPT] 'read_file'" in init_out

    # 1. Trigger Special Deny
    dec_deny = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/tmp/secret_api_key.txt"}))
    assert dec_deny.verdict == Verdict.DENY
    eval_deny_out = capsys.readouterr().out
    assert "[Security Debug] [SPECIAL DENY] Tier 1 Rule:" in eval_deny_out

    # 2. Trigger Special Accept
    dec_accept = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/docs/index.md"}))
    assert dec_accept.verdict == Verdict.ALLOW
    eval_accept_out = capsys.readouterr().out
    assert "[Security Debug] [SPECIAL ACCEPT] Tier 3 Rule:" in eval_accept_out

    # 3. Trigger Special Deny via protected path
    dec_path = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/etc/shadow"}))
    assert dec_path.verdict == Verdict.DENY
    eval_path_out = capsys.readouterr().out
    assert "[Security Debug] [SPECIAL DENY] Tier 0 Protected Path:" in eval_path_out


def test_deny_overrides_tiering_system():
    """Verify that Tier 1 Deny rules override Tier 3 Allow rules regardless of definition order."""
    rules = [
        # Broad allow rule defined BEFORE specific deny rule
        "allow read file ending with .md because 'documentation files are always safe'",
        "deny read file with zaragoza in it",
    ]
    engine = BuiltinPolicyEngine(dsl_rules=rules)

    # File matches both 'ending with .md' AND 'with zaragoza in it'
    # Tier 1 Deny MUST override Tier 3 Allow
    dec_zaragoza = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "zaragoza.md"}))
    assert dec_zaragoza.verdict == Verdict.DENY
    assert "deny read file with zaragoza in it" in dec_zaragoza.reason

    # Normal markdown file should still be allowed by Tier 3
    dec_normal = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "readme.md"}))
    assert dec_normal.verdict == Verdict.ALLOW
    assert dec_normal.reason == "documentation files are always safe"


def test_contains_synonyms_parsing():
    """Verify 'contains <val>' synonym works interchangeably with 'with <val> in it'."""
    rules = [
        'deny read file contains "zaragoza"',
        'deny read file that contains "secret"',
        'deny run command contains "sudo"',
        'block read file containing "token"',
    ]
    engine = BuiltinPolicyEngine(dsl_rules=rules)

    # 1. contains "zaragoza"
    dec1 = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "zaragoza.md"}))
    assert dec1.verdict == Verdict.DENY

    # 2. that contains "secret"
    dec2 = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "/tmp/my_secret_file.txt"}))
    assert dec2.verdict == Verdict.DENY

    # 3. run command contains "sudo"
    dec3 = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": "sudo apt update"}))
    assert dec3.verdict == Verdict.DENY

    # 4. containing "token"
    dec4 = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "app_token_config.json"}))
    assert dec4.verdict == Verdict.DENY

    # 5. Clean request passes
    dec_clean = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "normal.md"}))
    assert dec_clean.verdict == Verdict.ALLOW



