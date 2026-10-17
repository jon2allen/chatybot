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

