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
    """Verify hard denial on catastrophic shell commands and Chatybot execution while avoiding filename false positives."""
    engine = BuiltinPolicyEngine()

    dec = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": "rm -rf /"}))
    assert dec.verdict == Verdict.DENY
    assert "Dangerous command pattern" in dec.reason

    # 1. Chatybot executable invocations are strictly denied
    dec_chatybot = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": "chatybot --script attack.chatdsl -y"}))
    assert dec_chatybot.verdict == Verdict.DENY

    dec_rel = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": "./chatybot --run 'safe'"}))
    assert dec_rel.verdict == Verdict.DENY

    dec_py_chatybot = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": "python3 -m chatybot --run 'echo safe'"}))
    assert dec_py_chatybot.verdict == Verdict.DENY

    # 2. Benign commands referencing chatybot in filenames/arguments are NOT blocked by execution guard
    for benign_cmd in ["cat chatybot_notes.txt", "grep chatybot logfile.txt", "ls chatybot_dir/"]:
        dec_benign = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": benign_cmd}))
        assert dec_benign.verdict != Verdict.DENY, f"Expected non-DENY for '{benign_cmd}', got {dec_benign.verdict}"


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


def test_all_rules_are_case_insensitive():
    """Verify that all rules, tools, parameters, and patterns evaluate case-insensitively."""
    rules = [
        'deny read file with zaragoza in it',
        'allow read file ending with .md',
        'ask before run command with sudo',
    ]
    engine = BuiltinPolicyEngine(dsl_rules=rules)

    # 1. Mixed case tool and mixed case path value
    dec1 = engine.evaluate(PolicyRequest(tool="READ_FILE", parameters={"Path": "ZARAGOZA.MD"}))
    assert dec1.verdict == Verdict.DENY

    # 2. Mixed case target path for allow rule
    dec2 = engine.evaluate(PolicyRequest(tool="Read_File", parameters={"path": "DOCUMENTATION.MD"}))
    assert dec2.verdict == Verdict.ALLOW

    # 3. Mixed case command parameter and value
    dec3 = engine.evaluate(PolicyRequest(tool="RUN_COMMAND", parameters={"COMMAND": "SUDO systemctl restart"}))
    assert dec3.verdict == Verdict.ASK

    # 4. Tier 0 Protected path with uppercase
    dec_path = engine.evaluate(PolicyRequest(tool="READ_FILE", parameters={"path": "/ETC/PASSWD"}))
    assert dec_path.verdict == Verdict.DENY

    # 5. Tier 0 Dangerous command with uppercase
    dec_cmd = engine.evaluate(PolicyRequest(tool="RUN_COMMAND", parameters={"command": "RM -RF /"}))
    assert dec_cmd.verdict == Verdict.DENY


def test_mcp_tool_matching_and_arbitrary_field_targeting():
    """Verify that MCP tool naming, wildcard patterns, and arbitrary payload fields are supported."""
    rules = [
        'deny mcp__postgres__query where query contains "DROP TABLE"',
        'deny mcp__slack__* where channel equals "#confidential"',
        'deny create_issue where repo contains "internal"',
        'deny any tool where any field contains "PRIVATE KEY"',
        'deny write file where content contains "super_secret"',
        'deny write file with "token123" in content',
    ]
    engine = BuiltinPolicyEngine(dsl_rules=rules)

    # 1. Exact MCP tool name with arbitrary 'query' parameter
    dec1 = engine.evaluate(PolicyRequest(tool='mcp__postgres__query', parameters={'query': 'DROP TABLE users;', 'db': 'prod'}))
    assert dec1.verdict == Verdict.DENY

    # 2. MCP wildcard (mcp__slack__*) matching 'mcp__slack__post_message' and 'channel' field
    dec2 = engine.evaluate(PolicyRequest(tool='mcp__slack__post_message', parameters={'channel': '#confidential', 'msg': 'hello'}))
    assert dec2.verdict == Verdict.DENY

    # 3. Base tool name suffix ('create_issue') matching 'mcp__github__create_issue' and 'repo' field
    dec3 = engine.evaluate(PolicyRequest(tool='mcp__github__create_issue', parameters={'repo': 'my-org/internal-core', 'title': 'bug'}))
    assert dec3.verdict == Verdict.DENY

    # 4. Any tool / any field recursive scanning inside nested payload
    dec4 = engine.evaluate(PolicyRequest(tool='mcp__aws__s3_upload', parameters={'metadata': {'auth': 'BEGIN PRIVATE KEY ...'}}))
    assert dec4.verdict == Verdict.DENY

    # 5. write_file content inspection via 'where content contains'
    dec5 = engine.evaluate(PolicyRequest(tool='write_file', parameters={'path': 'out.txt', 'content': 'here is super_secret pass'}))
    assert dec5.verdict == Verdict.DENY

    # 6. write_file with 'with "token123" in content' phrasing
    dec6 = engine.evaluate(PolicyRequest(tool='write_file', parameters={'path': 'app.env', 'content': 'APP_KEY=token123'}))
    assert dec6.verdict == Verdict.DENY

    # 7. Safe query allowed through to baseline
    dec7 = engine.evaluate(PolicyRequest(tool='mcp__postgres__query', parameters={'query': 'SELECT * FROM users;', 'db': 'prod'}))
    assert dec7.verdict == Verdict.ASK


def test_tier0_filesystem_tools_and_parameter_aliases():
    """Verify that Tier 0 path protection covers all filesystem tools and parameter aliases."""
    engine = BuiltinPolicyEngine()

    # 1. remove_directory on ~/.ssh -> DENY
    dec1 = engine.evaluate(PolicyRequest(tool="remove_directory", parameters={"path": "~/.ssh"}))
    assert dec1.verdict == Verdict.DENY

    # 2. make_directory on /etc/new_dir -> DENY
    dec2 = engine.evaluate(PolicyRequest(tool="make_directory", parameters={"dir": "/etc/new_dir"}))
    assert dec2.verdict == Verdict.DENY

    # 3. replace_file_content on /etc/passwd -> DENY
    dec3 = engine.evaluate(PolicyRequest(tool="replace_file_content", parameters={"target_file": "/etc/passwd"}))
    assert dec3.verdict == Verdict.DENY

    # 4. patch_file on ~/.ssh/authorized_keys -> DENY
    dec4 = engine.evaluate(PolicyRequest(tool="patch_file", parameters={"file": "~/.ssh/authorized_keys"}))
    assert dec4.verdict == Verdict.DENY

    # 5. find_files in /etc -> DENY
    dec5 = engine.evaluate(PolicyRequest(tool="find_files", parameters={"directory": "/etc"}))
    assert dec5.verdict == Verdict.DENY

    # 6. write_file with 'filename' alias on /etc/passwd -> DENY
    dec6 = engine.evaluate(PolicyRequest(tool="write_file", parameters={"filename": "/etc/passwd", "content": "root:x:0:0"}))
    assert dec6.verdict == Verdict.DENY

    # 7. write_file with 'filepath' alias on /etc/passwd -> DENY
    dec7 = engine.evaluate(PolicyRequest(tool="write_file", parameters={"filepath": "/etc/passwd", "content": "root:x:0:0"}))
    assert dec7.verdict == Verdict.DENY

    # 8. Unprotected paths proceed normally to baseline / DSL evaluation
    dec_safe = engine.evaluate(PolicyRequest(tool="make_directory", parameters={"path": "./safe_tmp_dir"}))
    assert dec_safe.verdict == Verdict.ASK


def _write_guard(tmpdir, name, body):
    import os as _os
    import tempfile as _tempfile

    fd, path = _tempfile.mkstemp(suffix=".py", dir=tmpdir)
    with os.fdopen(fd, "w") as f:
        f.write("#!/usr/bin/env python3\n" + body)
    _os.chmod(path, 0o755)
    return path


def test_stdio_binary_invalid_json_fails_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys\nprint('this is not json')\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.DENY
        assert "invalid JSON" in decision.reason


def test_stdio_binary_unknown_status_fails_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys, json\nprint(json.dumps({'status': 'maybe'}))\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.DENY
        assert "unknown status" in decision.reason


def test_stdio_binary_non_string_status_fails_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys, json\nprint(json.dumps({'status': 42}))\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.DENY
        assert "non-string status" in decision.reason


def test_stdio_binary_non_object_response_fails_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys\nprint('[1, 2, 3]')\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.DENY
        assert "not a JSON object" in decision.reason


def test_stdio_binary_nonzero_exit_fails_safe_with_stderr():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys\nsys.stderr.write('boom' * 300)\nsys.exit(3)\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.DENY
        assert "exited with code 3" in decision.reason
        assert len(decision.reason) <= 600


def test_stdio_binary_timeout_fails_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import time\ntime.sleep(5)\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script, timeout_seconds=0.5)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.DENY
        assert "timed out" in decision.reason


def test_stdio_binary_missing_binary_fails_safe():
    engine = StdioBinaryPolicyEngine(binary_path="/nonexistent/policy-binary")
    decision = engine.evaluate(PolicyRequest(tool="read_file"))
    assert decision.verdict == Verdict.DENY
    assert "failed" in decision.reason


def test_stdio_binary_ask_verdict_gets_default_prompt_details():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys, json\nprint(json.dumps({'status': 'ask'}))\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.ASK
        assert decision.prompt_details is not None
        assert decision.prompt_details.message == "Authorize action?"


def test_stdio_binary_non_dict_modified_parameters_fails_safe():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys, json\nprint(json.dumps({'status': 'allow', 'modified_parameters': ['a', 'b']}))\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.DENY
        assert "modified_parameters" in decision.reason


def test_stdio_binary_valid_modified_parameters_passed_through():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys, json\nprint(json.dumps({'status': 'allow', 'modified_parameters': {'path': '/safe.txt'}}))\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        request = PolicyRequest(tool="write_file", parameters={"path": "/tmp/x", "content": "hi"})
        decision = engine.evaluate(request)
        assert decision.verdict == Verdict.ALLOW
        assert decision.modified_parameters == {"path": "/safe.txt"}


def test_stdio_binary_null_reason_is_coerced_to_string():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = _write_guard(
            tmpdir,
            "guard",
            "import sys, json\nprint(json.dumps({'status': 'allow', 'reason': None}))\n",
        )
        engine = StdioBinaryPolicyEngine(binary_path=script)
        decision = engine.evaluate(PolicyRequest(tool="read_file"))
        assert decision.verdict == Verdict.ALLOW
        assert isinstance(decision.reason, str)

def test_config_resilience_and_case_insensitive_verdicts(tmp_path, caplog):
    """Verify uppercase verdicts, baseline tool rule case normalization, and config error logging."""
    import logging

    # 1. Uppercase fail_safe and engine options in security.toml
    cfg_file = tmp_path / "security_uppercase.toml"
    cfg_file.write_text('fail_safe = "DENY"\nengine = "builtin"\n[builtin]\ndefault_verdict = "ASK"\n')

    mgr = SecurityManager(config_path=str(cfg_file))
    assert mgr.fail_safe == Verdict.DENY
    assert isinstance(mgr.engine, BuiltinPolicyEngine)
    assert mgr.engine.default_verdict == Verdict.ASK

    # 2. Case-insensitive baseline tool rules in BuiltinPolicyEngine
    engine = BuiltinPolicyEngine(
        rules={"Read_File": "DENY", "CUSTOM_TOOL": "ALLOW"},
        default_verdict="ASK",
    )
    dec_read = engine.evaluate(PolicyRequest(tool="read_file", parameters={"path": "safe.txt"}))
    assert dec_read.verdict == Verdict.DENY
    dec_custom = engine.evaluate(PolicyRequest(tool="custom_tool", parameters={}))
    assert dec_custom.verdict == Verdict.ALLOW

    # 3. Malformed security.toml triggers warning and falls back to default engine
    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("this is completely invalid [[ TOML {")
    with caplog.at_level(logging.WARNING):
        mgr_bad = SecurityManager(config_path=str(bad_toml))
    assert mgr_bad.engine is not None
    assert any("[Security Config] Failed to parse security policy file" in record.message for record in caplog.records)

    # 4. enabled=False does not construct unnecessary engine and returns ALLOW
    mgr_disabled = SecurityManager(enabled=False)
    assert mgr_disabled.engine is None
    dec_disabled = mgr_disabled.evaluate(tool="run_command", parameters={"command": "rm -rf /"})
    assert dec_disabled.verdict == Verdict.ALLOW


@pytest.mark.anyio
async def test_dispatch_tool_async_security_confirmation_and_audit(monkeypatch):
    """Verify non-blocking async confirmation in dispatch_tool and persistent audit logging."""
    import json
    from chatybot.chatybot_app import ChatybotApp

    app = ChatybotApp()
    app.initialize()
    app.logging_manager.logging_active = True
    logged_messages = []
    monkeypatch.setattr(app.logging_manager, "log_message", lambda msg: logged_messages.append(msg))

    # 1. User denies ASK tool in interactive session
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    async def mock_input(fn, *args, **kwargs):
        return "n"

    monkeypatch.setattr("asyncio.to_thread", mock_input)
    res_deny = await app.dispatch_tool(json.dumps({"tool": "write_file", "arguments": {"path": "test.txt", "content": "hi"}}))
    assert "Error: Security Authorization Denied" in res_deny
    assert any("[Security Audit] USER DECLINED tool 'write_file'" in m for m in logged_messages)

    # 2. Blocked Tier 0 tool creates BLOCKED audit log
    logged_messages.clear()
    res_tier0 = await app.dispatch_tool(json.dumps({"tool": "read_file", "arguments": {"path": "/etc/passwd"}}))
    assert "Error: Security Policy Blocked" in res_tier0
    assert any("[Security Audit] BLOCKED tool 'read_file'" in m for m in logged_messages)


def test_regex_validation_default_tools_and_cleanups(caplog):
    """Verify regex compile validation at parse time and newly registered DEFAULT_TOOL_RULES."""
    import logging
    from chatybot.security.dsl import SecurityDSLParser

    # 1. Invalid regex in DSL rule is caught and logged as warning at parse time
    with caplog.at_level(logging.WARNING):
        bad_rule = SecurityDSLParser.parse_rule('deny read file matching "[a-z"')
    assert bad_rule is None
    assert any("Invalid regex pattern '[a-z'" in r.message for r in caplog.records)

    # 2. DEFAULT_TOOL_RULES includes find_files (allow), session_get (allow), replace_file_content (ask), patch_file (ask)
    engine = BuiltinPolicyEngine()
    assert engine.evaluate(PolicyRequest(tool="find_files", parameters={"path": "./safe"})).verdict == Verdict.ALLOW
    assert engine.evaluate(PolicyRequest(tool="session_get", parameters={"key": "k"})).verdict == Verdict.ALLOW
    assert engine.evaluate(PolicyRequest(tool="replace_file_content", parameters={"target_file": "./safe.py"})).verdict == Verdict.ASK
    assert engine.evaluate(PolicyRequest(tool="patch_file", parameters={"file": "./safe.py"})).verdict == Verdict.ASK


@pytest.mark.anyio
async def test_auto_approve_yes_flag(monkeypatch):
    """Verify that auto_approve=True (-y / --yes) approves ASK tools without prompting, but DENY still blocks."""
    import json
    from chatybot.chatybot_app import ChatybotApp

    app = ChatybotApp(auto_approve=True)
    app.initialize()
    app.logging_manager.logging_active = True
    logged_messages = []
    monkeypatch.setattr(app.logging_manager, "log_message", lambda msg: logged_messages.append(msg))

    def fail_input(*args, **kwargs):
        raise AssertionError("input() should not be called when auto_approve is True")
    monkeypatch.setattr("asyncio.to_thread", fail_input)

    # 1. ASK tool (write_file) auto-approved
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "out.txt")
        res = await app.dispatch_tool(json.dumps({"tool": "write_file", "arguments": {"path": target, "content": "auto"}}))
        assert "Successfully wrote" in res or os.path.exists(target)
        assert any("[Security Audit] AUTO-APPROVED tool 'write_file' via --yes flag" in m for m in logged_messages)

    # 2. Tier 0 DENY tool (read_file /etc/passwd) is STILL BLOCKED even with auto_approve=True!
    logged_messages.clear()
    res_deny = await app.dispatch_tool(json.dumps({"tool": "read_file", "arguments": {"path": "/etc/passwd"}}))
    assert "Error: Security Policy Blocked" in res_deny
    assert any("[Security Audit] BLOCKED tool 'read_file'" in m for m in logged_messages)

    # 3. Spawning chatybot sub-process via run_command is strictly DENIED even with auto_approve=True!
    logged_messages.clear()
    res_cmd = await app.dispatch_tool(json.dumps({"tool": "run_command", "arguments": {"command": "chatybot --script escape.chatdsl -y"}}))
    assert "Error: Security Policy Blocked" in res_cmd
    assert any("[Security Audit] BLOCKED tool 'run_command'" in m for m in logged_messages)


@pytest.mark.anyio
async def test_non_interactive_ask_resolution(monkeypatch, tmp_path):
    """Verify non_interactive_ask policy (deny vs allow) when running non-interactively."""
    import json
    from chatybot.chatybot_app import ChatybotApp

    # 1. non_interactive_ask = "deny" (default)
    app_deny = ChatybotApp(auto_approve=False)
    app_deny.initialize()
    app_deny.script_context = True  # Marks non-interactive
    app_deny.logging_manager.logging_active = True
    logged_deny = []
    monkeypatch.setattr(app_deny.logging_manager, "log_message", lambda msg: logged_deny.append(msg))

    def fail_input(*args, **kwargs):
        raise AssertionError("input() should not be called in non-interactive mode")
    monkeypatch.setattr("asyncio.to_thread", fail_input)

    res_blocked = await app_deny.dispatch_tool(json.dumps({"tool": "write_file", "arguments": {"path": "test.txt", "content": "data"}}))
    assert "rejected by non_interactive_ask policy" in res_blocked
    assert any("BLOCKED non-interactive tool 'write_file'" in m for m in logged_deny)

    # 2. non_interactive_ask = "allow"
    cfg = tmp_path / "allow_sec.toml"
    cfg.write_text('non_interactive_ask = "allow"\n')
    app_allow = ChatybotApp(auto_approve=False)
    app_allow.initialize()
    app_allow.security_manager.non_interactive_ask = "allow"
    app_allow.script_context = True
    app_allow.logging_manager.logging_active = True
    logged_allow = []
    monkeypatch.setattr(app_allow.logging_manager, "log_message", lambda msg: logged_allow.append(msg))

    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "allowed.txt")
        res_allowed = await app_allow.dispatch_tool(json.dumps({"tool": "write_file", "arguments": {"path": target, "content": "data"}}))
        assert "Successfully wrote" in res_allowed or os.path.exists(target)
        assert any("AUTO-APPROVED tool 'write_file' via non_interactive_ask policy" in m for m in logged_allow)


@pytest.mark.anyio
async def test_no_security_cli_mode(monkeypatch):
    """Verify that no_security=True (--no-security) completely disables security evaluation."""
    import json
    from chatybot.chatybot_app import ChatybotApp

    app = ChatybotApp(no_security=True)
    app.initialize()
    assert app.security_manager.enabled is False

    # Fail immediately if any input() prompt is attempted
    def fail_input(*args, **kwargs):
        raise AssertionError("input() should not be called when security is disabled")
    monkeypatch.setattr("asyncio.to_thread", fail_input)

    # 1. Normal ASK tool runs without prompting or security checks
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "out.txt")
        res = await app.dispatch_tool(json.dumps({"tool": "write_file", "arguments": {"path": target, "content": "hello"}}))
        assert "Successfully wrote" in res or os.path.exists(target)

    # 2. Protected paths are NOT blocked by security policy
    res_path = await app.dispatch_tool(json.dumps({"tool": "read_file", "arguments": {"path": "/etc/nonexistent_system_cfg.conf"}}))
    assert "Error: Security Policy Blocked" not in res_path

    # 3. Dangerous commands (chatybot / rm -rf) are NOT blocked by security policy
    res_cmd = await app.dispatch_tool(json.dumps({"tool": "run_command", "arguments": {"command": "echo test_cmd"}}))
    assert "Error: Security Policy Blocked" not in res_cmd


def test_git_command_safeguards_and_chaining_defense(tmp_path):
    """Verify git read-only allowances, shell chaining guards, and destructive git command denials with config isolation."""
    import shutil
    from chatybot.security.manager import SecurityManager

    # Isolate test from user's ~/.config by using a copy of the default template
    bundled_default = os.path.join(os.path.dirname(__file__), "..", "src", "chatybot", "security", "default_security.toml")
    cfg_file = tmp_path / "isolated_security.toml"
    shutil.copy2(bundled_default, cfg_file)
    mgr = SecurityManager(config_path=str(cfg_file))

    # 1. Read-only standalone inspection commands are ALLOWED
    for cmd in ["git status", "git diff", "git log -n 5", "git show HEAD", "git branch -a", "git rev-parse HEAD", "git remote -v", "git ls-files"]:
        dec = mgr.evaluate(tool="run_command", parameters={"command": cmd})
        assert dec.verdict == Verdict.ALLOW, f"Expected ALLOW for '{cmd}', got {dec.verdict}"

    # 2. Compound/chained commands trigger ASK via Tier 2 chaining guards even if starting with git status
    for chained in [
        "git status && ls",
        "git status ; cat foo",
        "git status | grep bar",
        "git status $(echo hi)",
        "git status `whoami`",
        "git diff\nls -la /etc",
        "git status\r\nwhoami",
    ]:
        dec = mgr.evaluate(tool="run_command", parameters={"command": chained})
        assert dec.verdict == Verdict.ASK, f"Expected ASK for chained '{chained}', got {dec.verdict}"

    # 3. Destructive git commands are strictly DENIED via Tier 1
    for destructive in ["git reset --hard HEAD~1", "git clean -fdx", "git push --force origin main"]:
        dec = mgr.evaluate(tool="run_command", parameters={"command": destructive})
        assert dec.verdict == Verdict.DENY, f"Expected DENY for destructive '{destructive}', got {dec.verdict}"

    # 4. Mutating commands without explicit allow fall to Tier 4 baseline ASK
    dec_commit = mgr.evaluate(tool="run_command", parameters={"command": "git commit -m 'feat: update'"})
    assert dec_commit.verdict == Verdict.ASK


@pytest.mark.anyio
async def test_security_manager_init_failure_fails_closed(monkeypatch):
    """Verify that if SecurityManager.__init__ fails, ChatybotApp fails closed and blocks tools."""
    import json
    from chatybot.chatybot_app import ChatybotApp

    def fail_init(*args, **kwargs):
        raise RuntimeError("Simulated corrupt configuration file or dependency failure")

    monkeypatch.setattr("chatybot.security.manager.SecurityManager.__init__", fail_init)

    app = ChatybotApp(no_security=False)
    app.initialize()

    # The emergency security manager must be active and fail closed
    assert app.security_manager is not None
    assert app.security_manager.enabled is True

    # Any tool call must be strictly BLOCKED
    res = await app.dispatch_tool(json.dumps({"tool": "read_file", "arguments": {"path": "test.txt"}}))
    assert "Error: Security Policy Blocked" in res
    assert "fail-closed" in res


def test_racf_guard_binary_integration():
    """Verify end-to-end integration with racf-guard reference Rust binary if built."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    racf_bin = os.path.join(repo_root, "tools", "racf-guard", "target", "release", "racf-guard")
    if not os.path.isfile(racf_bin):
        pytest.skip("racf-guard release binary not built")

    policy_file = os.path.join(repo_root, "tools", "racf-guard", "examples", "security.racf")
    engine = StdioBinaryPolicyEngine(
        binary_path=racf_bin,
        args=["--policy", policy_file],
        timeout_seconds=2.0,
    )

    # 1. Developer member allowed on git.status
    dec = engine.evaluate(PolicyRequest(
        tool="git.status",
        context={"user": "jon2allen"},
    ))
    assert dec.verdict == Verdict.ALLOW
    assert "DEVELOPER" in dec.reason

    # 2. Dangerous rm command denied
    dec_rm = engine.evaluate(PolicyRequest(
        tool="run_command",
        parameters={"command": "rm -rf /"},
        context={"user": "jon2allen"},
    ))
    assert dec_rm.verdict == Verdict.DENY

    # 3. Sensitive /etc directory denied
    dec_dir = engine.evaluate(PolicyRequest(
        tool="view_file",
        parameters={"path": "/etc/shadow"},
        context={"user": "jon2allen"},
    ))
    assert dec_dir.verdict == Verdict.DENY

    # 4. Git commit prompts ASK
    dec_ask = engine.evaluate(PolicyRequest(
        tool="git.commit",
        context={"user": "jon2allen"},
    ))
    assert dec_ask.verdict == Verdict.ASK
    assert dec_ask.prompt_details is not None


def test_racf_guard_list_rules_and_debug_trace(capsys):
    """Verify racf-guard --list-rules audit output and debug trace forwarding."""
    import subprocess

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    racf_bin = os.path.join(repo_root, "tools", "racf-guard", "target", "release", "racf-guard")
    if not os.path.isfile(racf_bin):
        pytest.skip("racf-guard release binary not built")

    policy_file = os.path.join(repo_root, "tools", "racf-guard", "examples", "security.racf")

    # 1. Test CLI --list-rules
    proc = subprocess.run(
        [racf_bin, "--policy", policy_file, "--list-rules"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "RACF SECURITY DATABASE AUDIT REPORT" in proc.stdout
    assert "RESOURCE CLASS: FACILITY" in proc.stdout
    assert "RESOURCE CLASS: DIR" in proc.stdout
    assert "RESOURCE CLASS: COMMAND" in proc.stdout
    assert "DEVELOPER" in proc.stdout

    # 2. Test debug trace forwarding via StdioBinaryPolicyEngine
    engine_debug = StdioBinaryPolicyEngine(
        binary_path=racf_bin,
        args=["--policy", policy_file],
        debug=True,
    )
    dec = engine_debug.evaluate(PolicyRequest(
        tool="git.status",
        context={"user": "jon2allen"},
    ))
    assert dec.verdict == Verdict.ALLOW

    # Verify stderr was captured and printed with debug tag
    captured = capsys.readouterr()
    assert "[Security Debug] [External Binary] [RACF Debug]" in captured.out
    assert "Matched" in captured.out
    assert "Effective group access" in captured.out


def test_racf_guard_cli_persistence_with_backup():
    """Verify that CLI administrative updates create a backup copy and persist rules."""
    import shutil
    import subprocess

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    racf_bin = os.path.join(repo_root, "tools", "racf-guard", "target", "release", "racf-guard")
    if not os.path.isfile(racf_bin):
        pytest.skip("racf-guard release binary not built")

    seed_file = os.path.join(repo_root, "tools", "racf-guard", "examples", "security.racf")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_policy = os.path.join(tmpdir, "policy.racf")
        backup_file = os.path.join(tmpdir, "policy.racf.bak")
        shutil.copy(seed_file, test_policy)

        # 1. Run CLI command to connect user 'tester' to DEVELOPER
        proc = subprocess.run(
            [racf_bin, "--policy", test_policy, "connect", "tester", "--group", "DEVELOPER"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "[RACF Admin] Created backup" in proc.stdout
        assert "CONNECT tester GROUP(DEVELOPER)" in proc.stdout
        assert os.path.isfile(backup_file), "Backup file was not created"

        # Verify backup does NOT contain 'tester'
        with open(backup_file, "r", encoding="utf-8") as bf:
            assert "tester" not in bf.read()

        # 2. Run CLI command to permit git.push for DEVELOPER
        proc_permit = subprocess.run(
            [racf_bin, "--policy", test_policy, "permit", "git.push", "--class", "FACILITY", "--id", "DEVELOPER", "--access", "ALLOW"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "[RACF Admin] Created backup" in proc_permit.stdout
        assert "PERMIT git.push CLASS(FACILITY) ID(DEVELOPER) ACCESS(ALLOW)" in proc_permit.stdout

        # 3. Verify evaluate on next invocation loads and respects persisted updates
        engine = StdioBinaryPolicyEngine(
            binary_path=racf_bin,
            args=["--policy", test_policy],
        )
        dec = engine.evaluate(PolicyRequest(
            tool="git.push",
            context={"user": "tester"},
        ))
        assert dec.verdict == Verdict.ALLOW
        assert "tester" in dec.reason


def test_chatybot_execution_hardening_against_wrappers():
    """Verify CHATYBOT_EXEC_PATTERN blocks execution wrappers (env, nohup, sh -c, python -c/module)."""
    engine = BuiltinPolicyEngine()

    evasion_commands = [
        "env chatybot --run",
        "nohup ./chatybot &",
        "sudo /usr/local/bin/chatybot -y",
        'sh -c "chatybot status"',
        "bash -c 'chatybot --script foo.dsl'",
        "xargs chatybot",
        'python -c "import chatybot; chatybot.run()"',
        "python3.11 /opt/chatybot/chatybot.py --help",
        "python3 -m chatybot",
    ]

    for cmd in evasion_commands:
        dec = engine.evaluate(PolicyRequest(tool="run_command", parameters={"command": cmd}))
        assert dec.verdict == Verdict.DENY, f"Expected DENY for wrapper command '{cmd}', got {dec.verdict}"
        assert "Chatybot" in dec.reason


def test_racf_guard_path_traversal_and_explicit_policy_flag():
    """Verify racf-guard rejects path traversal bypasses and errors on nonexistent explicit policy file."""
    import subprocess

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    racf_bin = os.path.join(repo_root, "tools", "racf-guard", "target", "release", "racf-guard")
    if not os.path.isfile(racf_bin):
        pytest.skip("racf-guard release binary not built")

    policy_file = os.path.join(repo_root, "tools", "racf-guard", "examples", "security.racf")

    # 1. Path traversal attempt in view_file: /etc/../etc/passwd should match /etc/** and be DENIED
    engine = StdioBinaryPolicyEngine(
        binary_path=racf_bin,
        args=["--policy", policy_file],
    )
    dec_traversal = engine.evaluate(PolicyRequest(
        tool="view_file",
        parameters={"path": "/etc/../etc/passwd"},
    ))
    assert dec_traversal.verdict == Verdict.DENY
    assert "RACF security violation" in dec_traversal.reason

    # 2. Nonexistent explicit --policy file must cause nonzero exit code and explicit error
    proc = subprocess.run(
        [racf_bin, "--policy", "nonexistent_policy_file.racf", "--check", "--tool", "git.status"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "Explicit policy file not found" in (proc.stderr + proc.stdout)


def test_security_manager_missing_binary_warning(tmp_path, capsys):
    """Verify SecurityManager logs and prints a prominent warning if configured binary does not exist."""
    cfg = tmp_path / "missing_bin_sec.toml"
    cfg.write_text("""
engine = "binary"
[binary]
path = "/nonexistent/path/to/guard_binary"
""")
    mgr = SecurityManager(config_path=str(cfg))
    out = capsys.readouterr().out
    assert "[Security Warning] Configured binary path not found" in out
    assert isinstance(mgr.engine, BuiltinPolicyEngine)


def test_security_engine_banner_reporting(tmp_path):
    """Verify get_banner() on Builtin, StdioBinary, and SecurityManager."""
    import subprocess

    # 1. Builtin engine banner
    builtin = BuiltinPolicyEngine(dsl_rules=["deny read file with secret in it"])
    b_banner = builtin.get_banner()
    assert "Builtin Python Engine" in b_banner
    assert "1 DSL rules" in b_banner

    # 2. Disabled manager banner
    mgr_dis = SecurityManager(enabled=False)
    assert mgr_dis.get_banner() == "Disabled"

    # 3. racf-guard binary banner
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    racf_bin = os.path.join(repo_root, "tools", "racf-guard", "target", "release", "racf-guard")
    if os.path.isfile(racf_bin):
        policy_file = os.path.join(repo_root, "tools", "racf-guard", "examples", "security.racf")
        bin_engine = StdioBinaryPolicyEngine(
            binary_path=racf_bin,
            args=["--policy", policy_file],
        )
        banner = bin_engine.get_banner()
        assert "RACF-Guard" in banner
        assert "groups" in banner
        assert "profiles loaded" in banner

        # Verify CLI --banner directly
        proc = subprocess.run([racf_bin, "--policy", policy_file, "--banner"], capture_output=True, text=True)
        assert proc.returncode == 0
        assert "RACF-Guard" in proc.stdout


def test_racf_guard_content_class_payload_blocking():
    """Verify racf-guard CONTENT resource class blocks write_file when payload contains sensitive tokens."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    racf_bin = os.path.join(repo_root, "tools", "racf-guard", "target", "release", "racf-guard")
    if not os.path.isfile(racf_bin):
        pytest.skip("racf-guard release binary not built")

    policy_file = os.path.join(repo_root, "tools", "racf-guard", "examples", "security.racf")
    engine = StdioBinaryPolicyEngine(
        binary_path=racf_bin,
        args=["--policy", policy_file],
    )

    # 1. Clean payload write passes to FACILITY verdict (ASK)
    dec_clean = engine.evaluate(PolicyRequest(
        tool="write_file",
        parameters={"path": "safe.txt", "content": "hello world"},
        context={"user": "jon2allen"},
    ))
    assert dec_clean.verdict in (Verdict.ALLOW, Verdict.ASK)
    assert "RACF security violation" not in dec_clean.reason

    # 2. Payload with api_key triggers hard DENY on CONTENT class
    dec_leak = engine.evaluate(PolicyRequest(
        tool="write_file",
        parameters={"path": "app.env", "content": "my_api_key = 'sk-123456'"},
        context={"user": "jon2allen"},
    ))
    assert dec_leak.verdict == Verdict.DENY
    assert "RACF security violation on CONTENT" in dec_leak.reason

    # 3. Payload with private key triggers hard DENY on CONTENT class
    dec_key = engine.evaluate(PolicyRequest(
        tool="write_file",
        parameters={"path": "cert.pem", "content": "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."},
        context={"user": "jon2allen"},
    ))
    assert dec_key.verdict == Verdict.DENY
    assert "RACF security violation on CONTENT" in dec_key.reason


