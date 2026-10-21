"""
Tests for the allow, jev and chain policy engines (jev_security branch).
The Jev HTTP call is stubbed; no network access is needed.
"""

import json

import pytest

from chatybot.security import (
    AllowAllPolicyEngine,
    ChainedPolicyEngine,
    ChainStage,
    PolicyDecision,
    PolicyRequest,
    SecurityManager,
    Verdict,
)
from chatybot.security.base import BasePolicyEngine
from chatybot.security.jev import BUNDLED_RUBRIC, JevPolicyEngine
from chatybot.security.jev_rubric import CHOICE_KEY, Rubric

RULE_IDS = [r.id for r in Rubric.load(BUNDLED_RUBRIC).rules]



@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Engines now log by default under ~/.config/chatybot/logs; keep tests out of the real home."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Jev's redaction scanner caches known secrets from the environment; rebuild per test.
    monkeypatch.setattr("chatybot.security.jev._SCANNER", None)
    return home


def req(tool, interactive=True, **params):
    return PolicyRequest(tool=tool, parameters=params, context={"interactive": interactive})


def cmd(command, interactive=True):
    return req("run_command", interactive=interactive, command=command)


# --------------------------------------------------------------------------- stubs

class Fixed(BasePolicyEngine):
    def __init__(self, verdict, reason="fixed", boom=False):
        self.verdict, self.reason, self.boom, self.calls = verdict, reason, boom, 0

    def evaluate(self, request):
        self.calls += 1
        if self.boom:
            raise RuntimeError("stage exploded")
        return PolicyDecision(verdict=self.verdict, reason=self.reason)

    def supports_output_evaluation(self):
        return True

    def evaluate_output(self, request):
        return self.evaluate(request)




class FakeJev:
    """Records requests and returns noul answers from a scores dict."""

    def __init__(self, scores=None, choice=None, error=None):
        self.scores = scores or {}
        self.choice = choice
        self.error = error
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append({"url": url, "body": body, "headers": headers, "timeout": timeout})
        if self.error:
            raise self.error
        answers = {rid: {"type": "noul", "noul": self.scores.get(rid, 0.02)} for rid in RULE_IDS}
        if self.choice:
            answers[CHOICE_KEY] = {"type": "choice", **self.choice}
        return {"model": "typesafe/jev-1.13", "answers": answers, "usage": {"input_tokens": 900, "cost": 4e-05}}


@pytest.fixture
def rubric_path(tmp_path):
    p = tmp_path / "jev_security.toml"
    p.write_bytes(open(BUNDLED_RUBRIC, "rb").read())
    return str(p)


@pytest.fixture
def jev_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key-123456789")


def make_jev(rubric_path, fake, **kw):
    return JevPolicyEngine(rubric_path=rubric_path, http_post=fake, **kw)


# --------------------------------------------------------------------------- allow engine

def test_allow_engine_allows_everything_but_security_config():
    eng = AllowAllPolicyEngine()
    assert eng.evaluate(cmd("rm -rf build && git push origin main")).verdict == Verdict.ALLOW
    assert eng.evaluate(req("write_file", path="/tmp/x.txt", content="hi")).verdict == Verdict.ALLOW
    assert eng.evaluate(req("read_file", path="~/.ssh/id_rsa")).verdict == Verdict.ALLOW  # no path policy

    for blocked in (
        req("read_file", path="~/.config/chatybot/security.toml"),
        req("write_file", path="/anywhere/security.toml", content="engine='allow'"),
        req("write_file", path="~/.config/chatybot/jev_security.toml", content="x"),
        req("read_file", path="~/.config/chatybot/.env"),
        req("delete_file", path="policy.racf"),
        req("grep_search", path="~/.config/chatybot", search_term="API_KEY"),
        req("change_dir", path="~/.config/chatybot"),
        req("delete_file", path="~/.config/chatybot"),
        cmd("sed -i 's/deny/allow/' ~/.config/chatybot/security.toml"),
        cmd("cat ~/.config/chatybot/.env"),
    ):
        dec = eng.evaluate(blocked)
        assert dec.verdict == Verdict.DENY, blocked
        assert "self-protection" in dec.reason


def test_allow_engine_without_self_protection():
    eng = AllowAllPolicyEngine(protect_security_config=False)
    assert eng.evaluate(req("write_file", path="~/.config/chatybot/security.toml", content="x")).verdict == Verdict.ALLOW
    assert "NO self-protection" in eng.get_banner()


def test_manager_allow_engine(tmp_path, capsys):
    cfg = tmp_path / "security.toml"
    cfg.write_text('engine = "allow"\n')
    mgr = SecurityManager(config_path=str(cfg))
    assert isinstance(mgr.engine, AllowAllPolicyEngine)
    assert "without policy checks" in capsys.readouterr().out.lower()
    assert mgr.evaluate("run_command", {"command": "rm -rf node_modules"}).verdict == Verdict.ALLOW
    assert mgr.get_banner().startswith("Allow-All")

    cfg.write_text('engine = "allow"\n[allow]\nprotect_security_config = false\n')
    mgr = SecurityManager(config_path=str(cfg))
    assert mgr.engine.protect_security_config is False


# --------------------------------------------------------------------------- chain engine

def test_chain_strictest_enforcing_verdict_wins():
    chain = ChainedPolicyEngine([
        ChainStage("a", Fixed(Verdict.ALLOW, "a ok")),
        ChainStage("b", Fixed(Verdict.ASK, "b wants a human")),
    ])
    dec = chain.evaluate(cmd("ls"))
    assert dec.verdict == Verdict.ASK
    assert dec.reason == "[b] b wants a human"


def test_chain_shadow_never_changes_verdict_and_is_logged(tmp_path):
    log = tmp_path / "chain.jsonl"
    shadow = Fixed(Verdict.DENY, "shadow says no")
    chain = ChainedPolicyEngine(
        [ChainStage("builtin", Fixed(Verdict.ALLOW, "fine")), ChainStage("jev", shadow, mode="shadow")],
        log_path=str(log),
    )
    dec = chain.evaluate(cmd("git status"))
    assert dec.verdict == Verdict.ALLOW
    assert shadow.calls == 1
    entry = json.loads(log.read_text().strip())
    assert entry["final"] == "allow" and entry["decided_by"] == "builtin"
    assert entry["disagreement"] is True
    assert [s["verdict"] for s in entry["stages"]] == ["allow", "deny"]
    assert entry["stages"][1]["mode"] == "shadow"


def test_chain_deny_short_circuits_enforcers_but_shadow_still_runs():
    later = Fixed(Verdict.ALLOW)
    shadow = Fixed(Verdict.ALLOW)
    chain = ChainedPolicyEngine([
        ChainStage("first", Fixed(Verdict.DENY, "blocked")),
        ChainStage("second", later),
        ChainStage("trial", shadow, mode="shadow"),
    ])
    assert chain.evaluate(cmd("rm -rf /")).verdict == Verdict.DENY
    assert later.calls == 0
    assert shadow.calls == 1

    shadow2 = Fixed(Verdict.ALLOW)
    chain2 = ChainedPolicyEngine(
        [ChainStage("first", Fixed(Verdict.DENY)), ChainStage("trial", shadow2, mode="shadow")],
        shadow_on_deny=False,
    )
    chain2.evaluate(cmd("rm -rf /"))
    assert shadow2.calls == 0


def test_chain_stage_failures(tmp_path):
    log = tmp_path / "chain.jsonl"
    chain = ChainedPolicyEngine(
        [ChainStage("ok", Fixed(Verdict.ALLOW)), ChainStage("broken", Fixed(Verdict.ALLOW, boom=True))],
        fail_safe=Verdict.DENY, log_path=str(log),
    )
    dec = chain.evaluate(cmd("ls"))
    assert dec.verdict == Verdict.DENY
    assert "failed" in dec.reason

    chain = ChainedPolicyEngine(
        [ChainStage("ok", Fixed(Verdict.ALLOW)), ChainStage("broken", Fixed(Verdict.ALLOW, boom=True), mode="shadow")],
        log_path=str(log),
    )
    assert chain.evaluate(cmd("ls")).verdict == Verdict.ALLOW
    last = json.loads(log.read_text().strip().splitlines()[-1])
    assert "stage exploded" in last["stages"][1]["error"]


def test_chain_validation():
    with pytest.raises(ValueError):
        ChainedPolicyEngine([])
    with pytest.raises(ValueError):
        ChainedPolicyEngine([ChainStage("x", Fixed(Verdict.ALLOW), mode="shadow")])
    with pytest.raises(ValueError):
        ChainedPolicyEngine([ChainStage("x", Fixed(Verdict.ALLOW), mode="observe")])


def test_chain_log_redacts_secrets(tmp_path):
    log = tmp_path / "chain.jsonl"
    chain = ChainedPolicyEngine([ChainStage("a", Fixed(Verdict.ALLOW))], log_path=str(log))
    chain.evaluate(cmd("OPENROUTER_API_KEY=sk-or-v1-supersecretvalue123 python app.py"))
    text = log.read_text()
    assert "supersecretvalue" not in text
    assert "<redacted>" in text


def test_manager_chain_config(tmp_path):
    cfg = tmp_path / "security.toml"
    log = tmp_path / "logs" / "chain.jsonl"
    cfg.write_text(f'''
engine = "chain"
[chain]
stages = [ {{ engine = "builtin", mode = "enforce" }}, {{ engine = "allow", mode = "shadow" }} ]
log_path = "{log}"
''')
    mgr = SecurityManager(config_path=str(cfg))
    assert isinstance(mgr.engine, ChainedPolicyEngine)
    assert [(s.name, s.mode) for s in mgr.engine.stages] == [("builtin", "enforce"), ("allow", "shadow")]
    # builtin asks for run_command; the permissive shadow stage must not loosen that
    dec = mgr.evaluate("run_command", {"command": "ls -la"})
    assert dec.verdict == Verdict.ASK
    entry = json.loads(log.read_text().strip())
    assert entry["disagreement"] is True
    assert "Chain: builtin[enforce]" in mgr.get_banner()

    cfg.write_text('engine = "chain"\n[chain]\nstages = ["allow", "builtin"]\n')
    mgr = SecurityManager(config_path=str(cfg))
    assert [s.mode for s in mgr.engine.stages] == ["enforce", "enforce"]
    assert mgr.evaluate("read_file", {"path": "/etc/passwd"}).verdict == Verdict.DENY


@pytest.mark.parametrize("stages", ['["chain"]', '["nonsense"]', "[]"])
def test_manager_chain_bad_stages_raise(tmp_path, stages):
    cfg = tmp_path / "security.toml"
    cfg.write_text(f'engine = "chain"\n[chain]\nstages = {stages}\n')
    with pytest.raises(ValueError):
        SecurityManager(config_path=str(cfg))


# --------------------------------------------------------------------------- jev engine

def test_jev_deny_rule_and_request_shape(rubric_path, jev_key):
    fake = FakeJev(scores={"git_push": 0.94})
    eng = make_jev(rubric_path, fake)
    dec = eng.evaluate(cmd("git push origin main"))
    assert dec.verdict == Verdict.DENY
    assert "git_push=0.94->deny" in dec.reason
    call = fake.calls[0]
    assert call["url"] == "https://openrouter.ai/api/alpha/decisions"
    assert call["headers"]["Authorization"] == "Bearer sk-or-test-key-123456789"
    assert set(call["body"]["questions"]) == set(RULE_IDS)
    assert all(q["type"] == "noul" for q in call["body"]["questions"].values())
    assert '"command": "git push origin main"' in call["body"]["state"]
    assert call["timeout"] == 2.5


def test_jev_allow_and_uncertain_band(rubric_path, jev_key):
    eng = make_jev(rubric_path, FakeJev())
    dec = eng.evaluate(cmd("git status"))
    assert dec.verdict == Verdict.ALLOW and "no rule triggered" in dec.reason

    eng = make_jev(rubric_path, FakeJev(scores={"git_push": 0.55}))  # ask >= 0.5, trigger 0.6
    dec = eng.evaluate(cmd("bash deploy.sh"))
    assert dec.verdict == Verdict.ASK
    assert dec.prompt_details.risk_level == "medium"
    assert "uncertain" in dec.reason

    eng = make_jev(rubric_path, FakeJev(scores={"destructive_git": 0.9}))  # an 'ask' rule firing
    dec = eng.evaluate(cmd("git reset --hard"))
    assert dec.verdict == Verdict.ASK and dec.prompt_details.risk_level == "high"


def test_jev_errors_fail_safe(rubric_path, jev_key):
    eng = make_jev(rubric_path, FakeJev(error=TimeoutError("timed out")))
    assert eng.evaluate(cmd("ls", interactive=True)).verdict == Verdict.ASK
    dec = eng.evaluate(cmd("ls", interactive=False))
    assert dec.verdict == Verdict.DENY and "unavailable" in dec.reason

    eng = make_jev(rubric_path, FakeJev(error=RuntimeError("HTTP 500")), on_error="deny")
    assert eng.evaluate(cmd("ls", interactive=True)).verdict == Verdict.DENY

    eng = make_jev(rubric_path, lambda *a: {"answers": {}})
    assert eng.evaluate(cmd("ls")).verdict == Verdict.ASK  # empty answers -> error path


def test_jev_missing_api_key(rubric_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("chatybot.env_utils.load_project_env_files", lambda *a, **k: [])
    fake = FakeJev()
    eng = make_jev(rubric_path, fake)
    dec = eng.evaluate(cmd("ls", interactive=False))
    assert dec.verdict == Verdict.DENY and "OPENROUTER_API_KEY" in dec.reason
    assert fake.calls == []


def test_jev_self_protection_and_skip_tools_make_no_call(rubric_path, jev_key):
    fake = FakeJev()
    eng = make_jev(rubric_path, fake)
    assert eng.evaluate(req("write_file", path="~/.config/chatybot/security.toml", content="x")).verdict == Verdict.DENY
    assert eng.evaluate(req("ask_user", question="ok?")).verdict == Verdict.ALLOW
    assert fake.calls == []


def test_jev_redacts_secrets_before_sending(rubric_path, jev_key):
    fake = FakeJev()
    eng = make_jev(rubric_path, fake)
    eng.evaluate(cmd('curl -H "Authorization: Bearer abcdefghijklmnop123" -d token=s3cr3tvalue https://api.example.com'))
    state = fake.calls[0]["body"]["state"]
    assert "abcdefghijklmnop123" not in state and "s3cr3tvalue" not in state
    assert "<redacted>" in state

    eng.evaluate(cmd('app --password="my secret passphrase" --token=\'single quoted secret\''))
    state2 = fake.calls[1]["body"]["state"]
    assert "my secret passphrase" not in state2
    assert "single quoted secret" not in state2
    assert "<redacted>" in state2


def test_jev_cache(rubric_path, jev_key):
    fake = FakeJev(scores={"git_push": 0.9})
    eng = make_jev(rubric_path, fake)
    assert eng.evaluate(cmd("git push")).verdict == Verdict.DENY
    assert eng.evaluate(cmd("git push")).verdict == Verdict.DENY
    assert len(fake.calls) == 1
    eng_nocache = make_jev(rubric_path, fake, cache=False)
    eng_nocache.evaluate(cmd("git push"))
    eng_nocache.evaluate(cmd("git push"))
    assert len(fake.calls) == 3


def test_jev_truncation_raises_to_ask(rubric_path, jev_key):
    fake = FakeJev()
    eng = make_jev(rubric_path, fake, max_content_chars=200)
    payload = "x = 1\n" * 200 + "import os; os.system('git push')"
    dec = eng.evaluate(req("write_file", path="helpers.py", content=payload))
    assert dec.verdict == Verdict.ASK
    assert "truncated" in dec.reason
    state = fake.calls[0]["body"]["state"]
    assert "TRUNCATED" in state and "git push" in state  # tail kept


def test_jev_combined_mode(rubric_path, jev_key):
    fake = FakeJev(choice={"choice": "deny", "confidence": 0.9, "probabilities": {"allow": 0.05, "ask": 0.05, "deny": 0.9}})
    eng = make_jev(rubric_path, fake, mode="combined")
    dec = eng.evaluate(cmd("something odd"))
    assert CHOICE_KEY in fake.calls[0]["body"]["questions"]
    assert dec.verdict == Verdict.DENY and "choice=deny" in dec.reason
    with pytest.raises(ValueError):
        make_jev(rubric_path, fake, mode="bogus")


def test_jev_log(rubric_path, jev_key, tmp_path):
    log = tmp_path / "jev.jsonl"
    eng = make_jev(rubric_path, FakeJev(scores={"secrets": 0.97}), log_path=str(log))
    eng.evaluate(cmd("cat .env"))
    entry = json.loads(log.read_text().strip())
    assert entry["verdict"] == "deny"
    assert entry["scores"]["secrets"] == 0.97
    assert entry["usage"]["input_tokens"] == 900


def test_jev_seeds_rubric(tmp_path, jev_key):
    target = tmp_path / "cfg" / "jev_security.toml"
    eng = JevPolicyEngine(rubric_path=str(target), http_post=FakeJev())
    assert target.exists()
    assert len(eng.rubric.rules) == len(RULE_IDS)


def test_manager_chain_builtin_enforce_jev_shadow(tmp_path, jev_key, monkeypatch):
    fake = FakeJev(scores={"git_push": 0.95})
    monkeypatch.setattr("chatybot.security.jev._urllib_post", fake)
    rubric = tmp_path / "jev_security.toml"
    log = tmp_path / "chain.jsonl"
    cfg = tmp_path / "security.toml"
    cfg.write_text(f'''
engine = "chain"
[jev]
rubric_path = "{rubric}"
[chain]
stages = [ {{ engine = "builtin", mode = "enforce" }}, {{ engine = "jev", mode = "shadow" }} ]
log_path = "{log}"
''')
    mgr = SecurityManager(config_path=str(cfg))
    assert rubric.exists()  # seeded
    dec = mgr.evaluate("run_command", {"command": "git push origin main"}, {"interactive": True})
    assert dec.verdict == Verdict.ASK  # builtin decides; jev's DENY is only logged
    entry = json.loads(log.read_text().strip())
    assert entry["stages"][1]["stage"] == "jev" and entry["stages"][1]["verdict"] == "deny"
    assert entry["disagreement"] is True
    assert len(fake.calls) == 1

    # Promote Jev to enforce: now its DENY wins
    cfg.write_text(cfg.read_text().replace('engine = "jev", mode = "shadow"', 'engine = "jev", mode = "enforce"'))
    mgr = SecurityManager(config_path=str(cfg))
    assert mgr.evaluate("run_command", {"command": "git push origin main"}).verdict == Verdict.DENY


def test_jev_cache_differentiation_by_context(rubric_path, jev_key, monkeypatch, tmp_path):
    fake = FakeJev(scores={"git_push": 0.9})
    eng = make_jev(rubric_path, fake)
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    monkeypatch.chdir(dir_a)
    eng.evaluate(cmd("git push", interactive=True))
    assert len(fake.calls) == 1

    # Same command in different directory does not falsely hit cache
    monkeypatch.chdir(dir_b)
    eng.evaluate(cmd("git push", interactive=True))
    assert len(fake.calls) == 2

    # Same command in same directory hits cache
    eng.evaluate(cmd("git push", interactive=True))
    assert len(fake.calls) == 2

    # Different interactivity does not falsely hit cache
    eng.evaluate(cmd("git push", interactive=False))
    assert len(fake.calls) == 3


def test_jev_rubric_nan_scores_treated_as_uncertain():
    rubric = Rubric.load(BUNDLED_RUBRIC)
    verdict, reasons = rubric.noul_verdict({"git_push": float("nan")})
    assert verdict == "ask"
    assert "git_push=missing->ask" in reasons



# --------------------------------------------------------------------------- malformed scores

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -0.3, 1.7, True, "0.9", None])
def test_malformed_noul_scores_become_ask(bad):
    rubric = Rubric.load(BUNDLED_RUBRIC)
    scores = {r.id: 0.02 for r in rubric.rules}
    scores["git_push"] = bad
    verdict, reasons = rubric.noul_verdict(scores)
    assert verdict == "ask", (bad, verdict)
    assert "git_push=missing->ask" in reasons


@pytest.mark.parametrize("raw", [
    '{"noul": NaN}', '{"noul": Infinity}', '{"noul": -Infinity}', '{"noul": -0.2}', '{"noul": 1.5}',
    '{"answer": true, "confidence": NaN}',
])
def test_parse_noul_rejects_malformed(raw):
    from chatybot.security.jev_rubric import parse_noul

    assert parse_noul(json.loads(raw)) is None


@pytest.mark.parametrize("probs", [
    '{"allow": 0.1, "ask": NaN, "deny": NaN}',
    '{"allow": 0.9, "ask": 0.9, "deny": 0.9}',      # does not sum to 1
    '{"allow": 1.2, "ask": -0.1, "deny": -0.1}',    # out of range
    '{"allow": "lots", "ask": 0.0, "deny": 0.0}',   # not a number
])
def test_malformed_choice_probabilities_become_ask(probs):
    from chatybot.security.jev_rubric import parse_choice

    rubric = Rubric.load(BUNDLED_RUBRIC)
    raw = json.loads('{"choice": "allow", "confidence": 0.9, "probabilities": ' + probs + "}")
    parsed = parse_choice(raw)
    assert parsed is None
    assert rubric.choice_verdict(parsed)[0] == "ask"
    # Also guarded when an already-parsed (e.g. saved) record carries bad numbers
    assert rubric.choice_verdict({"choice": "allow", "probabilities": {"allow": 0.1, "ask": float("nan"), "deny": float("nan")}})[0] == "ask"


def test_valid_choice_still_allows():
    from chatybot.security.jev_rubric import parse_choice

    rubric = Rubric.load(BUNDLED_RUBRIC)
    parsed = parse_choice({"choice": "allow", "confidence": 0.97, "probabilities": {"allow": 0.97, "ask": 0.02, "deny": 0.01}})
    assert rubric.choice_verdict(parsed)[0] == "allow"


# --------------------------------------------------------------------------- logging & outcomes

def _lines(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def test_jev_and_chain_log_by_default(tmp_path, jev_key, monkeypatch, isolated_home):
    monkeypatch.setattr("chatybot.security.jev._urllib_post", FakeJev(scores={"git_push": 0.95}))
    cfg = tmp_path / "security.toml"
    cfg.write_text(
        'engine = "chain"\n[chain]\nstages = [ { engine = "builtin", mode = "enforce" }, { engine = "jev", mode = "shadow" } ]\n'
    )
    mgr = SecurityManager(config_path=str(cfg))
    mgr.evaluate("run_command", {"command": "git push"}, {"interactive": True})
    logs = isolated_home / ".config" / "chatybot" / "logs"
    assert (logs / "security_chain.jsonl").exists()
    assert (logs / "jev_security.jsonl").exists()

    cfg.write_text(cfg.read_text() + 'log_path = ""\n[jev]\nlog_path = ""\n')
    for f in logs.iterdir():
        f.unlink()
    mgr = SecurityManager(config_path=str(cfg))
    mgr.evaluate("run_command", {"command": "git push --tags"}, {"interactive": True})
    assert list(logs.iterdir()) == []


def test_jev_logs_every_path_with_source(rubric_path, jev_key, tmp_path, monkeypatch):
    log = tmp_path / "jev.jsonl"
    eng = make_jev(rubric_path, FakeJev(scores={"git_push": 0.9}), log_path=str(log))
    eng.evaluate(cmd("git push"))                                           # api
    eng.evaluate(cmd("git push"))                                           # cache
    eng.evaluate(req("read_file", path="~/.config/chatybot/security.toml"))  # self_protect
    eng.evaluate(req("ask_user", question="ok?"))                           # skip_tools
    sources = [e["source"] for e in _lines(log)]
    assert sources == ["api", "cache", "self_protect", "skip_tools"]
    cache_line = _lines(log)[1]
    assert cache_line["scores"]["git_push"] == 0.9  # scores kept with cached decisions
    assert all(e["event"] == "decision" for e in _lines(log))

    err_log = tmp_path / "err.jsonl"
    make_jev(rubric_path, FakeJev(error=TimeoutError("slow")), log_path=str(err_log)).evaluate(cmd("ls"))
    monkeypatch.delenv("OPENROUTER_API_KEY")
    monkeypatch.setattr("chatybot.env_utils.load_project_env_files", lambda *a, **k: [])
    make_jev(rubric_path, FakeJev(), log_path=str(err_log)).evaluate(cmd("ls"))
    assert [e["source"] for e in _lines(err_log)] == ["error", "error"]


def test_cached_decisions_are_copies(rubric_path, jev_key):
    eng = make_jev(rubric_path, FakeJev(scores={"git_push": 0.9}))
    first = eng.evaluate(cmd("git push"))
    first.reason = "tampered"
    assert eng.evaluate(cmd("git push")).reason != "tampered"


def test_manager_stamps_request_id_and_records_outcomes(tmp_path, jev_key, monkeypatch):
    fake = FakeJev(scores={"destructive_git": 0.9})
    monkeypatch.setattr("chatybot.security.jev._urllib_post", fake)
    chain_log, jev_log = tmp_path / "chain.jsonl", tmp_path / "jev.jsonl"
    cfg = tmp_path / "security.toml"
    cfg.write_text(f'''
engine = "chain"
[jev]
rubric_path = "{tmp_path / 'r.toml'}"
log_path = "{jev_log}"
[chain]
stages = [ {{ engine = "builtin", mode = "enforce" }}, {{ engine = "jev", mode = "shadow" }} ]
log_path = "{chain_log}"
''')
    mgr = SecurityManager(config_path=str(cfg))
    d1 = mgr.evaluate("run_command", {"command": "git reset --hard HEAD~1"}, {"interactive": True})
    d2 = mgr.evaluate("run_command", {"command": "git stash clear"}, {"interactive": True})
    assert d1.request_id and d2.request_id and d1.request_id != d2.request_id
    mgr.record_outcome(d1, "declined", tool="run_command")
    mgr.record_outcome(d2, "approved", tool="run_command")

    chain = _lines(chain_log)
    assert [e["event"] for e in chain] == ["decision", "decision", "outcome", "outcome"]
    assert chain[2]["request_id"] == chain[0]["request_id"] == d1.request_id
    assert chain[2]["outcome"] == "declined" and chain[3]["outcome"] == "approved"
    jev = _lines(jev_log)
    outcomes = {e["request_id"]: e["outcome"] for e in jev if e["event"] == "outcome"}
    assert outcomes == {d1.request_id: "declined", d2.request_id: "approved"}
    decisions = {e["request_id"] for e in jev if e["event"] == "decision"}
    assert decisions == {d1.request_id, d2.request_id}


def test_record_outcome_is_safe_without_logging_engines(tmp_path):
    cfg = tmp_path / "security.toml"
    cfg.write_text('engine = "builtin"\n')
    mgr = SecurityManager(config_path=str(cfg))
    dec = mgr.evaluate("run_command", {"command": "ls"})
    mgr.record_outcome(dec, "approved", tool="run_command")  # builtin has no log: no-op
    mgr.record_outcome(PolicyDecision(verdict=Verdict.ASK), "approved")  # no request_id: no-op
    disabled = SecurityManager(config_path=str(cfg), enabled=False)
    disabled.record_outcome(disabled.evaluate("run_command", {"command": "ls"}), "approved")


@pytest.mark.anyio
async def test_dispatch_records_ask_outcomes_in_chain_log(monkeypatch, tmp_path):
    """End to end through ChatybotApp.dispatch_tool: each ASK path writes an outcome line."""
    from chatybot.chatybot_app import ChatybotApp

    chain_log = tmp_path / "chain.jsonl"
    sec_cfg = tmp_path / "sec.toml"
    sec_cfg.write_text(
        'engine = "chain"\nfail_safe = "deny"\nnon_interactive_ask = "deny"\n'
        '[builtin]\ndefault_verdict = "ask"\n'
        f'[chain]\nstages = [ {{ engine = "builtin", mode = "enforce" }}, {{ engine = "allow", mode = "shadow" }} ]\n'
        f'log_path = "{chain_log}"\n'
    )
    app = ChatybotApp(security_config_path=str(sec_cfg))
    app.initialize()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    answers = iter(["n", "y"])

    async def fake_input(fn, *args, **kwargs):
        return next(answers)

    monkeypatch.setattr("asyncio.to_thread", fake_input)
    target = tmp_path / "out.txt"
    call = json.dumps({"tool": "write_file", "arguments": {"path": str(target), "content": "hi"}})
    assert "Security Authorization Denied" in await app.dispatch_tool(call)   # declined
    await app.dispatch_tool(call)                                               # approved
    app.script_context = True                                                  # now non-interactive
    assert "non_interactive_ask" in await app.dispatch_tool(call)              # blocked

    events = [json.loads(l) for l in open(chain_log)]
    decisions = [e for e in events if e["event"] == "decision"]
    outcomes = [e for e in events if e["event"] == "outcome"]
    assert [o["outcome"] for o in outcomes] == ["declined", "approved", "blocked_non_interactive"]
    assert [o["request_id"] for o in outcomes] == [d["request_id"] for d in decisions]
    assert all(o["tool"] == "write_file" for o in outcomes)


def test_engine_rubric_matches_harness_rubric():
    """The engine's bundled rubric must equal tools/jev-eval/rubric.toml, or the harness
    stops testing what chatybot runs. Comments may differ; content may not."""
    import tomllib
    from pathlib import Path

    harness = Path(__file__).resolve().parent.parent / "tools" / "jev-eval" / "rubric.toml"
    if not harness.exists():
        pytest.skip("tools/jev-eval not present (installed package)")
    with open(BUNDLED_RUBRIC, "rb") as f:
        engine_cfg = tomllib.load(f)
    with open(harness, "rb") as f:
        harness_cfg = tomllib.load(f)
    assert engine_cfg == harness_cfg, (
        "src/chatybot/security/default_jev_security.toml and tools/jev-eval/rubric.toml differ; "
        "copy one over the other (keeping the header comment)"
    )


def test_jev_eval_from_log(tmp_path, jev_key, monkeypatch, capsys):
    """tools/jev-eval/jev_eval.py --from-log: joins logs, re-grades, exports cases to label."""
    import argparse
    import importlib.util
    from pathlib import Path

    harness_path = Path(__file__).resolve().parent.parent / "tools" / "jev-eval" / "jev_eval.py"
    if not harness_path.exists():
        pytest.skip("tools/jev-eval not present")
    spec = importlib.util.spec_from_file_location("jev_eval", harness_path)
    jev_eval = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jev_eval)

    scores = {"git push origin main": {"git_push": 0.94}, "git reset --hard": {"destructive_git": 0.9}}

    def fake(url, body, headers, timeout):
        s = next((v for k, v in scores.items() if f'"command": "{k}"' in body["state"]), {})
        return {"answers": {r: {"type": "noul", "noul": s.get(r, 0.03)} for r in RULE_IDS}}

    monkeypatch.setattr("chatybot.security.jev._urllib_post", fake)
    cfg = tmp_path / "security.toml"
    cfg.write_text(f'''
engine = "chain"
[jev]
rubric_path = "{tmp_path / 'r.toml'}"
log_path = "{tmp_path / 'jev.jsonl'}"
[chain]
stages = [ {{ engine = "builtin", mode = "enforce" }}, {{ engine = "jev", mode = "shadow" }} ]
log_path = "{tmp_path / 'chain.jsonl'}"
''')
    mgr = SecurityManager(config_path=str(cfg))
    push = mgr.evaluate("run_command", {"command": "git push origin main"}, {"interactive": True})
    reset = mgr.evaluate("run_command", {"command": "git reset --hard"}, {"interactive": True})
    mgr.record_outcome(push, "approved", tool="run_command")
    mgr.record_outcome(reset, "declined", tool="run_command")

    def run(**kw):
        ns = argparse.Namespace(from_log=[str(tmp_path / "jev.jsonl"), str(tmp_path / "chain.jsonl")],
                                export=kw.get("export"), mode_given=None)
        rubric = Rubric.load(tmp_path / "r.toml")
        if "trigger" in kw:
            rubric.trigger = kw["trigger"]
        return jev_eval.from_log(ns, rubric)

    out = tmp_path / "cands.jsonl"
    assert run(export=str(out)) == 0
    text = capsys.readouterr().out
    assert "2 Jev decisions, 2 chain decisions, 2 ASK outcomes" in text
    rows = [json.loads(l) for l in open(out)]
    by_cmd = {r["parameters"]["command"]: r for r in rows}
    assert "engines disagreed" in by_cmd["git push origin main"]["_why"]
    assert "user approved what Jev would deny" in by_cmd["git push origin main"]["_why"]
    assert "user declined the ASK" in by_cmd["git reset --hard"]["_why"]
    assert all(r["expected"] is None and r["category"] == "live" for r in rows)

    # Unlabelled exports are refused by the corpus loader
    with pytest.raises(SystemExit):
        jev_eval.load_cases(out, None, None)

    # Re-grading with a stricter trigger flips Jev's DENY on the push to ASK
    run(trigger=0.95)
    assert "deny -> ask" in capsys.readouterr().out


def test_jev_context_target_exists(rubric_path, jev_key, tmp_path):
    fake = FakeJev()
    eng = make_jev(rubric_path, fake)

    existing_file = tmp_path / "exists.txt"
    existing_file.write_text("hello")
    non_existing = tmp_path / "not_exists.txt"

    # 1. Existing file -> target_exists: True
    eng.evaluate(req("write_file", path=str(existing_file), content="new content"))
    state1 = fake.calls[0]["body"]["state"]
    action1 = json.loads(state1.split("ACTION:\n")[1])
    assert action1["context"]["target_exists"] is True

    # 2. Non-existent file -> target_exists: False
    eng.evaluate(req("write_file", path=str(non_existing), content="brand new"))
    state2 = fake.calls[1]["body"]["state"]
    action2 = json.loads(state2.split("ACTION:\n")[1])
    assert action2["context"]["target_exists"] is False

    # 3. Non-file tool -> target_exists not in context
    eng.evaluate(cmd("ls -l"))
    state3 = fake.calls[2]["body"]["state"]
    action3 = json.loads(state3.split("ACTION:\n")[1])
    assert "target_exists" not in action3["context"]


def test_jev_from_log_approved_ask_candidate(tmp_path, jev_key, monkeypatch):
    import argparse
    import importlib.util
    from pathlib import Path

    harness_path = Path(__file__).resolve().parents[1] / "tools" / "jev-eval" / "jev_eval.py"
    spec = importlib.util.spec_from_file_location("jev_eval", harness_path)
    jev_eval = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jev_eval)

    fake = FakeJev(scores={"data_loss": 0.55})
    rubric = tmp_path / "r.toml"
    rubric.write_bytes(open(BUNDLED_RUBRIC, "rb").read())
    log = tmp_path / "jev.jsonl"
    cfg = tmp_path / "security.toml"
    cfg.write_text(f'''
engine = "jev"
[jev]
rubric_path = "{rubric}"
log_path = "{log}"
''')
    mgr = SecurityManager(config_path=str(cfg))
    mgr.engine.http_post = fake

    dec = mgr.evaluate("write_file", {"path": "src/main.rs", "content": "fn main() {}"}, {"interactive": True})
    assert dec.verdict == Verdict.ASK
    mgr.record_outcome(dec, "approved", tool="write_file")

    # Auto-approved outcomes (via --yes flag or non-interactive policy) are NOT human-approved candidate false positives
    dec_auto = mgr.evaluate("write_file", {"path": "src/lib.rs", "content": "pub fn lib() {}"}, {"interactive": False})
    mgr.record_outcome(dec_auto, "auto_approved_yes_flag", tool="write_file")

    ns = argparse.Namespace(from_log=[str(log)], export=str(tmp_path / "cands.jsonl"), mode_given=None)
    rub = Rubric.load(rubric)
    assert jev_eval.from_log(ns, rub) == 0
    rows = [json.loads(l) for l in open(tmp_path / "cands.jsonl")]
    assert len(rows) == 1
    assert any("candidate false positive" in w for w in rows[0]["_why"])
    assert rows[0]["parameters"]["path"] == "src/main.rs"


def test_allow_engine_evaluate_output():
    eng = AllowAllPolicyEngine(protect_security_config=True)
    # Allows benign output
    req_benign = PolicyRequest(tool="read_file", output="hello world", phase="output")
    assert eng.evaluate_output(req_benign).verdict == Verdict.ALLOW

    # Allows all output
    req_out = PolicyRequest(tool="read_file", parameters={"path": "any_file.txt"}, output="any output", phase="output")
    assert eng.evaluate_output(req_out).verdict == Verdict.ALLOW


def test_jev_evaluate_output(rubric_path, jev_key):
    fake = FakeJev(scores={"secrets": 0.95})
    # Default: output_scan is False, supports_output_evaluation() is False
    default_eng = make_jev(rubric_path, fake)
    assert default_eng.supports_output_evaluation() is False
    req_out = PolicyRequest(tool="read_file", parameters={"path": "notes.txt"}, output="some output content", phase="output")
    assert default_eng.evaluate_output(req_out).verdict == Verdict.ALLOW
    assert len(fake.calls) == 0

    # Opted-in: output_scan=True enables LLM output evaluation
    eng = make_jev(rubric_path, fake, output_scan=True)
    assert eng.supports_output_evaluation() is True

    # 1. Output evaluation sends phase="output_inspection" in state and scores rubric
    dec = eng.evaluate_output(req_out)
    assert dec.verdict == Verdict.DENY
    assert len(fake.calls) == 1

    state_str = fake.calls[0]["body"]["state"]
    assert "output_inspection" in state_str

    # 2. Empty output is allowed without making an LLM API call
    req_empty = PolicyRequest(tool="read_file", output="   ", phase="output")
    dec_empty = eng.evaluate_output(req_empty)
    assert dec_empty.verdict == Verdict.ALLOW
    assert len(fake.calls) == 1  # No additional API call made

    # 3. skip_tools bypasses LLM API call during output evaluation
    req_skip = PolicyRequest(tool="ask_user", output="some user prompt response", phase="output")
    dec_skip = eng.evaluate_output(req_skip)
    assert dec_skip.verdict == Verdict.ALLOW
    assert "skip_tools" in dec_skip.reason
    assert len(fake.calls) == 1  # Still 1, no call made for skip_tools



def test_chain_evaluate_output():
    enforcer = Fixed(Verdict.ASK, reason="Sensitive output detected")
    shadow = Fixed(Verdict.ALLOW)
    chain = ChainedPolicyEngine(
        stages=[ChainStage("enforce_stg", enforcer, "enforce"), ChainStage("shadow_stg", shadow, "shadow")],
        log_path="",
    )
    req_secret = PolicyRequest(tool="read_file", output="some secret output", phase="output")
    dec = chain.evaluate_output(req_secret)
    assert dec.verdict == Verdict.ASK
    assert enforcer.calls == 1
    assert shadow.calls == 1


def test_chain_output_evaluation_skips_unsupported_stage():
    """Verify that a chain stage without output evaluation support does not invoke evaluate()."""
    class LegacyEngine(BasePolicyEngine):
        def __init__(self):
            self.calls = 0

        def evaluate(self, request):
            self.calls += 1
            return PolicyDecision(verdict=Verdict.DENY, reason="Legacy engine blocks everything")

    legacy = LegacyEngine()
    chain = ChainedPolicyEngine(
        stages=[ChainStage("legacy", legacy, "enforce")],
        log_path="",
    )
    req = PolicyRequest(tool="read_file", output="hello", phase="output")
    dec = chain.evaluate_output(req)
    assert dec.verdict == Verdict.ALLOW
    assert legacy.calls == 0  # evaluate was NOT called!


def test_jev_trace_raw_payload_prints_request_and_response(rubric_path, jev_key, capsys):
    """trace_raw_payload=True prints the outgoing body and incoming response to the screen."""
    fake = FakeJev(scores={"git_push": 0.94})
    eng = make_jev(rubric_path, fake, trace_raw_payload=True)
    eng.evaluate(cmd("git push origin main"))

    out = capsys.readouterr().out
    assert "JEV Security Request Payload" in out
    assert "POST https://openrouter.ai/api/alpha/decisions" in out
    # The body sent to the model is visible (state + questions + model).
    assert '"model": "typesafe/jev-1.13"' in out
    assert "JEV Security Response Payload" in out
    assert "---- end of payload ---" in out
    # API key is masked, never printed in full.
    assert "sk-or-test-key-123456789" not in out


def test_jev_trace_raw_payload_env_var(rubric_path, jev_key, monkeypatch, capsys):
    """CHATYBOT_TRACE_RAW_PAYLOAD=1 enables tracing even without the constructor flag."""
    monkeypatch.setenv("CHATYBOT_TRACE_RAW_PAYLOAD", "1")
    eng = make_jev(rubric_path, FakeJev())  # trace_raw_payload defaults to False
    eng.evaluate(cmd("git status"))
    out = capsys.readouterr().out
    assert "JEV Security Request Payload" in out
    assert "JEV Security Response Payload" in out


def test_jev_trace_raw_payload_off_by_default(rubric_path, jev_key, capsys):
    """No payload is printed when tracing is disabled."""
    eng = make_jev(rubric_path, FakeJev())
    eng.evaluate(cmd("git status"))
    out = capsys.readouterr().out
    assert "JEV Security Request Payload" not in out


def test_jev_trace_raw_payload_output_path(rubric_path, jev_key, capsys):
    """Output evaluation also traces its payload when enabled."""
    fake = FakeJev(scores={"secrets": 0.95})
    eng = make_jev(rubric_path, fake, output_scan=True, trace_raw_payload=True)
    req_out = PolicyRequest(tool="read_file", parameters={"path": "notes.txt"}, output="some output content", phase="output")
    eng.evaluate_output(req_out)
    out = capsys.readouterr().out
    assert "JEV Security Output Request Payload" in out
    assert "JEV Security Output Response Payload" in out








def test_jev_request_redacts_provider_keys_and_known_secrets(rubric_path, jev_key, monkeypatch):
    """Secrets in a command never reach the Jev API: provider formats via SecretScanner
    patterns, and the user's own keys (from the environment) via known-secret matching."""
    groq = "gsk_" + "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789ABCDEFGHIJKLMN"
    mine = "Xk9mQ2vR7tY4pL8w" + "N3zB6cJ1hF5dG0sA"
    monkeypatch.setenv("MISTRAL_API_KEY", mine)
    fake = FakeJev()
    eng = make_jev(rubric_path, fake)
    eng.evaluate(cmd(f"groq-cli --key {groq} && mistral chat --api-key {mine}"))
    state = fake.calls[0]["body"]["state"]
    assert groq not in state and mine not in state
    assert "<redacted:MISTRAL_API_KEY>" in state
    assert "groq-cli --key" in state  # the rest of the command is still visible to Jev


def test_jev_request_keeps_shell_expansions_visible(rubric_path, jev_key):
    """$(...) and ${VAR} are not secrets; hiding them would hide intent (keychain reads) from Jev."""
    fake = FakeJev()
    eng = make_jev(rubric_path, fake)
    eng.evaluate(cmd("export OPENAI_API_KEY=$(security find-generic-password -s openai -w)"))
    assert "find-generic-password -s openai -w)" in fake.calls[0]["body"]["state"]
    assert "$(security" in fake.calls[0]["body"]["state"]


# --------------------------------------------------------------------------- loop refusal events

class RecordingStage(Fixed):
    """A stage that would log loop refusal events itself, like the Jev engine."""

    def __init__(self):
        super().__init__(Verdict.ALLOW)
        self.repeats, self.limits = [], []

    def record_refusal_repeat(self, *a, **kw):
        self.repeats.append((a, kw))

    def record_refusal_limit(self, *a, **kw):
        self.limits.append((a, kw))


def _events(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_chain_logs_loop_refusal_events_once(tmp_path):
    """The chain writes loop refusal events to its own log only; stages are not asked to log them too."""
    log = tmp_path / "chain.jsonl"
    stage = RecordingStage()
    chain = ChainedPolicyEngine([ChainStage("builtin", Fixed(Verdict.ALLOW)), ChainStage("jev", stage, mode="shadow")], log_path=str(log))
    chain.record_refusal_repeat("rid-1", "run_command", parameters={"command": "ls"}, reason="denied", session_id="s1")
    chain.record_refusal_limit(3, request_ids=["rid-1"], refused_calls=[{"turn": 1, "tool": "run_command", "arguments": {"command": "ls"}, "reason": "denied", "request_id": "rid-1"}], session_id="s1")
    assert stage.repeats == [] and stage.limits == []
    events = _events(log)
    assert [e["event"] for e in events] == ["refusal_repeat", "refusal_limit"]
    assert events[1]["refused_calls"][0]["request_id"] == "rid-1"


def test_loop_refusal_events_redact_reasons_and_arguments(tmp_path, rubric_path, jev_key):
    """Reasons and arguments are redacted and cut in both the chain and the jev log."""
    secret = "sk-or-v1-" + "0123456789abcdef" * 4
    long_reason = f"Output Withheld: token {secret} " + "x" * 9000
    calls = [{"turn": 1, "tool": "read_file", "arguments": {"path": "a.env", "note": f"KEY={secret}"}, "reason": long_reason, "request_id": "r1"}]

    chain_log = tmp_path / "chain.jsonl"
    chain = ChainedPolicyEngine([ChainStage("a", Fixed(Verdict.ALLOW))], log_path=str(chain_log))
    jev = make_jev(rubric_path, FakeJev())
    jev.log_path = str(tmp_path / "jev.jsonl")
    for eng in (chain, jev):
        eng.record_refusal_repeat("r1", "read_file", parameters={"note": f"KEY={secret}"}, reason=long_reason, session_id="s")
        eng.record_refusal_limit(3, request_ids=["r1"], refused_calls=calls, session_id="s")

    for path in (chain_log, tmp_path / "jev.jsonl"):
        text = path.read_text()
        assert secret not in text
        assert "TRUNCATED" in text
        repeat, limit = _events(path)
        assert len(repeat["reason"]) < 4200
        assert len(limit["refused_calls"][0]["reason"]) < 4200
    # caller's records are not modified in place
    assert calls[0]["reason"] == long_reason


def test_loop_refusal_events_fail_closed_when_redaction_breaks(tmp_path, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("scanner broke")

    monkeypatch.setattr("chatybot.security.jev._prepare", boom)
    log = tmp_path / "chain.jsonl"
    chain = ChainedPolicyEngine([ChainStage("a", Fixed(Verdict.ALLOW))], log_path=str(log))
    chain.record_refusal_repeat("r1", "run_command", parameters={"command": "echo hunter2-secret"}, reason="hunter2-secret", session_id="s")
    chain.evaluate(cmd("echo hunter2-secret"))
    text = log.read_text()
    assert "hunter2-secret" not in text
    assert "<omitted: redaction failed>" in text
