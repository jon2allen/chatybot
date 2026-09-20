"""Tests for /decide command calibration unpacking and variable flattening.

Mocks the decision API response to verify that confidence, probabilities,
and threshold gating are correctly unpacked into script variables.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from chatybot.chatybot_app import ChatybotApp


def _make_app(capsys=None):
    app = ChatybotApp()
    app.initialize()
    if capsys is not None:
        capsys.readouterr()
    return app


def _mock_choice_response(choice="stay", confidence=0.55, probabilities=None):
    if probabilities is None:
        probabilities = {"go": 0.22, "stay": 0.78}
    return {
        "model": "typesafe/jev-1.13",
        "answers": {
            "q": {
                "type": "choice",
                "choice": choice,
                "confidence": confidence,
                "probabilities": probabilities,
            }
        },
        "usage": {"input_tokens": 335, "output_tokens": 31},
        "id": "gen-test",
        "provider": "TypeSafe",
    }


def _mock_noul_response(answer=True, confidence=0.92, with_confidence_field=True):
    """Mock a noul response.

    The real TypeSafe Jev API returns {"type": "noul", "noul": 0.92} with no
    separate confidence field — the noul probability IS the confidence.
    Set with_confidence_field=False to simulate the real API format.
    """
    q = {"type": "noul"}
    if with_confidence_field:
        q["answer"] = answer
        q["confidence"] = confidence
    else:
        # Real API format: noul is a float probability, no confidence field
        q["noul"] = confidence if isinstance(confidence, (int, float)) else (1.0 if answer else 0.0)
    return {
        "model": "typesafe/jev-1.13",
        "answers": {"q": q},
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }


def _mock_score_response(score=4, confidence=0.80, probabilities=None):
    if probabilities is None:
        probabilities = {"1": 0.05, "2": 0.05, "3": 0.10, "4": 0.70, "5": 0.10}
    return {
        "model": "typesafe/jev-1.13",
        "answers": {
            "q": {
                "type": "score",
                "score": score,
                "confidence": confidence,
                "probabilities": probabilities,
            }
        },
        "usage": {"input_tokens": 200, "output_tokens": 20},
    }


@pytest.mark.anyio
async def test_choice_flattening(capsys):
    """Choice: confidence and per-option probabilities are flattened into vars."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="stay", confidence=0.55,
                                      probabilities={"go": 0.22, "stay": 0.78})
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        await app.handle_escape_command(
            '/decide "wind 22mph" choice "Launch or stay?" options="stay:Safe,go:Risky" var=sail_plan'
        )

    sv = app.buffer_manager.script_vars
    assert sv["sail_plan"] == "stay"
    assert sv["sail_plan_choice"] == "stay"
    assert sv["sail_plan_conf"] == "0.55"
    assert sv["sail_plan_confidence"] == "0.55"
    assert sv["sail_plan_prob"] == "0.78"
    assert sv["sail_plan_prob_go"] == "0.22"
    assert sv["sail_plan_prob_stay"] == "0.78"

    # Global registers
    assert sv["DECIDE"] == "stay"
    assert sv["DECIDE_CONF"] == "0.55"
    assert sv["DECIDE_PROB"] == "0.78"
    assert isinstance(sv["DECIDE_FULL"], dict)


@pytest.mark.anyio
async def test_threshold_fallback(capsys):
    """When confidence < threshold, primary var resolves to FALLBACK."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="go", confidence=0.40,
                                      probabilities={"go": 0.60, "stay": 0.40})
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        await app.handle_escape_command(
            '/decide "wind 22mph" choice "Launch or stay?" options="stay:Safe,go:Risky" threshold=0.70 var=sail_plan'
        )

    sv = app.buffer_manager.script_vars
    assert sv["sail_plan"] == "FALLBACK"
    assert sv["sail_plan_choice"] == "go"
    assert sv["sail_plan_conf"] == "0.40"
    assert sv["DECIDE"] == "FALLBACK"
    assert sv["DECIDE_CONF"] == "0.40"


@pytest.mark.anyio
async def test_threshold_passes(capsys):
    """When confidence >= threshold, normal result is stored."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="stay", confidence=0.85,
                                      probabilities={"go": 0.10, "stay": 0.90})
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        await app.handle_escape_command(
            '/decide "calm winds" choice "Launch or stay?" options="stay:Safe,go:Risky" threshold=0.70 var=sail_plan'
        )

    sv = app.buffer_manager.script_vars
    assert sv["sail_plan"] == "stay"
    assert sv["sail_plan_conf"] == "0.85"


@pytest.mark.anyio
async def test_noul_flattening(capsys):
    """Noul: boolean answer is flattened to true/false string."""
    app = _make_app(capsys)

    mock_resp = _mock_noul_response(answer=True, confidence=0.92)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        await app.handle_escape_command(
            '/decide "rm -rf /" noul "Is this destructive?" var=is_destructive'
        )

    sv = app.buffer_manager.script_vars
    assert sv["is_destructive"] == "true"
    assert sv["is_destructive_choice"] == "true"
    assert sv["is_destructive_conf"] == "0.92"
    assert sv["DECIDE"] == "true"
    assert sv["DECIDE_CONF"] == "0.92"


@pytest.mark.anyio
async def test_noul_false(capsys):
    """Noul: false answer flattens to 'false'."""
    app = _make_app(capsys)

    mock_resp = _mock_noul_response(answer=False, confidence=0.15)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        await app.handle_escape_command(
            '/decide "echo hello" noul "Is this destructive?" var=is_destructive'
        )

    sv = app.buffer_manager.script_vars
    assert sv["is_destructive"] == "false"
    assert sv["is_destructive_conf"] == "0.15"


@pytest.mark.anyio
async def test_noul_real_api_format(capsys):
    """Noul with real API format: {"noul": 0.92} and no confidence field.

    The noul probability should be used as the confidence.
    """
    app = _make_app(capsys)

    mock_resp = _mock_noul_response(confidence=0.92, with_confidence_field=False)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        await app.handle_escape_command(
            '/decide "rm -rf /" noul "Is this destructive?" threshold=0.8 var=danger'
        )

    sv = app.buffer_manager.script_vars
    assert sv["danger"] == "true"
    assert sv["danger_choice"] == "true"
    assert sv["danger_conf"] == "0.92"
    assert sv["DECIDE"] == "true"
    assert sv["DECIDE_CONF"] == "0.92"
    assert sv["DECIDE_PROB"] == "0.92"


@pytest.mark.anyio
async def test_noul_real_api_low_confidence(capsys):
    """Noul with real API format: low probability returns false, not FALLBACK.

    Noul always returns true/false. The user can gate on _conf in their script.
    """
    app = _make_app(capsys)

    mock_resp = _mock_noul_response(confidence=0.08, with_confidence_field=False)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        await app.handle_escape_command(
            '/decide "echo hello" noul "Is this destructive?" threshold=0.8 var=danger'
        )

    sv = app.buffer_manager.script_vars
    # noul=0.08 < 0.5 means answer is "false". Threshold is ignored for noul.
    assert sv["danger"] == "false"
    assert sv["danger_choice"] == "false"
    assert sv["danger_conf"] == "0.08"


@pytest.mark.anyio
async def test_score_scale_param(capsys):
    """Score: scale='1:5' generates levels [1,2,3,4,5] and flattens score."""
    app = _make_app(capsys)

    mock_resp = _mock_score_response(score=4, confidence=0.80)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        await app.handle_escape_command(
            '/decide "draft text" score "Rate quality" scale="1:5" var=rubric'
        )

    # Verify scale was converted to levels in the API call
    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["questions"]["q"]["criteria"] == ["1", "2", "3", "4", "5"]

    sv = app.buffer_manager.script_vars
    assert sv["rubric"] == "4"
    assert sv["rubric_choice"] == "4"
    assert sv["rubric_conf"] == "0.80"


@pytest.mark.anyio
async def test_no_var_only_globals(capsys):
    """Without var=, only global registers are set."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="stay", confidence=0.90,
                                      probabilities={"go": 0.05, "stay": 0.95})
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        await app.handle_escape_command(
            '/decide "calm winds" choice "Launch or stay?" options="stay:Safe,go:Risky"'
        )

    sv = app.buffer_manager.script_vars
    assert sv["DECIDE"] == "stay"
    assert sv["DECIDE_CONF"] == "0.90"
    assert sv["DECIDE_PROB"] == "0.95"
    # No per-var keys should exist
    assert "sail_plan" not in sv


@pytest.mark.anyio
async def test_state_with_inner_quotes(capsys):
    """State content containing double-quotes should not break parsing."""
    app = _make_app(capsys)

    mock_resp = _mock_noul_response(answer=True, confidence=0.95)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        await app.handle_escape_command(
            '/decide "echo "Do something" && rm -rf /" noul "Is this destructive?" var=danger'
        )

    # Verify the state was parsed correctly (including inner quotes)
    call_kwargs = mock_eval.call_args.kwargs
    assert 'echo "Do something" && rm -rf /' == call_kwargs["state"]

    sv = app.buffer_manager.script_vars
    assert sv["danger"] == "true"
    assert sv["danger_conf"] == "0.95"


@pytest.mark.anyio
async def test_state_with_echo_quote_pattern(capsys):
    """Multi-line state with 'echo "Usage: ..."' must not match 'echo' as type."""
    app = _make_app(capsys)

    bash_script = (
        '#!/usr/bin/env bash\n'
        'set -euo pipefail\n'
        'usage() {\n'
        '    echo "Usage: $0 <repo_path>"\n'
        '    echo "Example: $0 /home/user/myproject"\n'
        '    exit 1\n'
        '}\n'
        'if [[ $# -ne 1 ]]; then\n'
        '    echo "Error: Exactly one argument required."\n'
        '    usage\n'
        'fi\n'
        'REPO_PATH="$1"\n'
        'rm -rf "$REPO_PATH/.git"\n'
        'echo "Deleted $REPO_PATH/.git"\n'
    )

    app.buffer_manager.set_script_var("bash1", bash_script)
    capsys.readouterr()

    mock_resp = _mock_noul_response(answer=True, confidence=0.95)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        cmd = '/decide "${bash1}" noul "Does this contain dangerous commands that will delete data?" threshold=0.8 var=bash_decision'
        # Simulate variable substitution: replace ${bash1} with its content.
        # We do a targeted replacement rather than replace_placeholders_legacy
        # because that method strips all unresolved $VAR patterns (like
        # $REPO_PATH, $0) from the bash script content — a pre-existing
        # substitution system issue separate from the regex parsing fix.
        cmd = cmd.replace("${bash1}", bash_script)
        await app.handle_escape_command(cmd)

    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["state"] == bash_script
    assert call_kwargs["questions"]["q"]["type"] == "noul"

    sv = app.buffer_manager.script_vars
    assert sv["bash_decision"] == "true"
    assert sv["bash_decision_conf"] == "0.95"


@pytest.mark.anyio
@pytest.mark.parametrize("alias", ["/decidir", "/decider", "/决策", "/decidi", "/قرار"])
async def test_decide_localized_aliases(capsys, alias):
    """Localized aliases for /decide (es, fr, zh, it, ar) dispatch and parse correctly."""
    app = _make_app(capsys)

    mock_resp = _mock_noul_response(answer=True, confidence=0.91)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        res = await app.handle_escape_command(f'{alias} "sample state" noul "Is it valid?" var=res')
        assert res is True

    sv = app.buffer_manager.script_vars
    assert sv["res"] == "true"
    assert sv["DECIDE"] == "true"


@pytest.mark.anyio
@pytest.mark.parametrize("q_type,mock_fn", [
    ("choice", lambda: _mock_choice_response(choice="billing", confidence=0.85)),
    ("score", lambda: _mock_score_response(score=5, confidence=0.90)),
    ("noul", lambda: _mock_noul_response(answer=True, confidence=0.95)),
])
async def test_decide_variable_placeholder_substitution(capsys, q_type, mock_fn):
    """Placeholders ($var, ${var}) in state and instructions are resolved across choice, score, and noul."""
    app = _make_app(capsys)
    app.buffer_manager.set_script_var("ticket_text", "Customer wants invoice refund for charge #402")
    app.buffer_manager.set_script_var("subject", "invoice refund")

    mock_resp = mock_fn()
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        if q_type == "choice":
            cmd = '/decide "$ticket_text" choice "Which category for ${subject}?" options="billing:Invoicing,tech:Support" var=ans'
        elif q_type == "score":
            cmd = '/decide "$ticket_text" score "Severity of ${subject}?" scale="1:5" var=ans'
        else:
            cmd = '/decide "$ticket_text" noul "Is ${subject} urgent?" var=ans'

        res = await app.handle_escape_command(cmd)
        assert res is True

    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["state"] == "Customer wants invoice refund for charge #402"
    assert "invoice refund" in call_kwargs["questions"]["q"]["instructions"]
    assert "${subject}" not in call_kwargs["questions"]["q"]["instructions"]


@pytest.mark.anyio
async def test_decide_instructions_with_nested_quotes(capsys):
    """Instructions with inner quotes ('Welcome' or 'Hello') should parse cleanly."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="welcome", confidence=0.88)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        cmd = '/decide "User arrived" choice "Should we say \'Welcome\' or \'Hello\' to user?" options="welcome:Greet,ignore:Skip" var=greet_ans'
        res = await app.handle_escape_command(cmd)
        assert res is True

    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["state"] == "User arrived"
    assert call_kwargs["questions"]["q"]["instructions"] == "Should we say 'Welcome' or 'Hello' to user?"
    assert call_kwargs["questions"]["q"]["type"] == "choice"

    sv = app.buffer_manager.script_vars
    assert sv["greet_ans"] == "welcome"


@pytest.mark.anyio
@pytest.mark.parametrize("options_str", [
    'refund:Customer wants a refund, store credit, or return, support:General questions, inquiries, help',
    'refund:Customer wants a refund, store credit, or return; support:General questions, inquiries, help',
])
async def test_decide_options_with_commas_in_descriptions(capsys, options_str):
    """Option descriptions containing commas parse correctly via comma lookahead or semicolon."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="refund", confidence=0.93)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        cmd = f'/decide "Need money back" choice "What is the intent?" options="{options_str}" var=intent'
        res = await app.handle_escape_command(cmd)
        assert res is True

    call_kwargs = mock_eval.call_args.kwargs
    criteria = call_kwargs["questions"]["q"]["criteria"]
    assert criteria == {
        "refund": "Customer wants a refund, store credit, or return",
        "support": "General questions, inquiries, help",
    }
    assert app.buffer_manager.script_vars["intent"] == "refund"




