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


@pytest.mark.anyio
async def test_decide_bare_options_criteria_non_null(capsys):
    """Bare options (e.g. 'yes, no') should map to string descriptions, avoiding null in API criteria."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="yes", confidence=0.99)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        cmd = '/decide "Is battery charged?" choice "Select state" options="yes, no, maybe" var=status'
        res = await app.handle_escape_command(cmd)
        assert res is True

    call_kwargs = mock_eval.call_args.kwargs
    criteria = call_kwargs["questions"]["q"]["criteria"]
    assert criteria == {"yes": "yes", "no": "no", "maybe": "maybe"}
    # Ensure no values are None (which would serialize as null in JSON)
    assert all(isinstance(v, str) and v for v in criteria.values())
    assert app.buffer_manager.script_vars["status"] == "yes"


@pytest.mark.anyio
async def test_decide_state_containing_internal_decision_keywords(capsys):
    """State containing quotes followed by decision keywords ('choice', etc.) should not split prematurely."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="positive", confidence=0.91)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        cmd = '/decide \'He said "test" choice "again"\' choice "Was the sentiment positive?" options="positive:Yes,negative:No" var=sentiment'
        res = await app.handle_escape_command(cmd)
        assert res is True

    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["state"] == 'He said "test" choice "again"'
    assert call_kwargs["questions"]["q"]["type"] == "choice"
    assert call_kwargs["questions"]["q"]["instructions"] == "Was the sentiment positive?"
    assert app.buffer_manager.script_vars["sentiment"] == "positive"


@pytest.mark.anyio
async def test_score_negative_scale_param(capsys):
    """Score: scale='-2:2' generates levels ['-2','-1','0','1','2'] and sorts probabilities correctly."""
    app = _make_app(capsys)

    mock_resp = _mock_score_response(
        score=0,
        confidence=0.85,
        probabilities={"-2": 0.05, "2": 0.10, "-1": 0.15, "0": 0.50, "1": 0.20},
    )
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        await app.handle_escape_command(
            '/decide "overall trend" score "Rate momentum" scale="-2:2" var=momentum'
        )

    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["questions"]["q"]["criteria"] == ["-2", "-1", "0", "1", "2"]

    sv = app.buffer_manager.script_vars
    assert sv["momentum"] == "0"
    assert sv["momentum_conf"] == "0.85"

    out = capsys.readouterr().out
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    prob_indices = {
        "-2": next(i for i, l in enumerate(lines) if l.startswith("-2")),
        "-1": next(i for i, l in enumerate(lines) if l.startswith("-1")),
        "0": next(i for i, l in enumerate(lines) if l.startswith("0")),
        "1": next(i for i, l in enumerate(lines) if l.startswith("1")),
        "2": next(i for i, l in enumerate(lines) if l.startswith("2")),
    }
    assert prob_indices["-2"] < prob_indices["-1"] < prob_indices["0"] < prob_indices["1"] < prob_indices["2"]


@pytest.mark.anyio
async def test_score_level_limit_exceeded(capsys):
    """Score questions with more than 10 levels should fail with an error."""
    app = _make_app(capsys)

    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock) as mock_eval:
        await app.handle_escape_command(
            '/decide "test text" score "Rate 1 to 20" scale="1:20"'
        )
        # Should not call evaluate
        mock_eval.assert_not_called()

    out = capsys.readouterr().out
    assert "Error: score questions support at most 10 levels, got 20" in out


@pytest.mark.anyio
async def test_decide_saved_to_session_turn(capsys):
    """When a session is active, /decide records prompt and structured result in session turns."""
    app = _make_app(capsys)
    app.session_mode = "on"
    app.active_session_id = "test_decide_session_001"

    mock_resp = _mock_choice_response(
        choice="billing",
        confidence=0.94,
        probabilities={"billing": 0.94, "tech": 0.06},
    )
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        cmd = '/decide "invoice inquiry" choice "Which department?" options="billing:Billing,tech:Technical" var=dept'
        res = await app.handle_escape_command(cmd)
        assert res is True

    # Assert turn was appended to session_turns
    assert len(app.session_turns) == 1
    turn = app.session_turns[0]
    assert turn["type"] == "decision"
    assert turn["question_type"] == "choice"
    assert turn["instructions"] == "Which department?"
    assert turn["state"] == "invoice inquiry"
    assert turn["response"] == "billing"
    assert turn["confidence"] == 0.94
    assert turn["probabilities"] == {"billing": 0.94, "tech": 0.06}
    assert turn["target_var"] == "dept"

    # Test /session show formats the decision turn properly
    await app.handle_escape_command("/session show")
    out = capsys.readouterr().out
    assert "[Turn 1] [DECISION:CHOICE]" in out
    assert "Question: Which department?" in out
    assert "State: invoice inquiry" in out
    assert "Decision: billing (confidence: 0.94)" in out

    # Verify decision turn is not lost when save_active_session() is called
    assert any(act.get("type") == "decision" for act in app.session_activity)
    app.save_active_session()
    _, loaded_turns = app._get_session_store().load_session(app.active_session_id)
    decision_turns_on_disk = [t for t in loaded_turns if t.get("type") == "decision"]
    assert len(decision_turns_on_disk) == 1
    assert decision_turns_on_disk[0]["response"] == "billing"
    assert decision_turns_on_disk[0]["instructions"] == "Which department?"


@pytest.mark.anyio
async def test_decide_keywords_inside_state_and_instructions(capsys):
    """Keywords like var=, scale=, or options= inside state or instructions must not trigger premature splitting."""
    app = _make_app(capsys)

    mock_resp = _mock_choice_response(choice="config", confidence=0.88)
    with patch("chatybot.decision_client.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        cmd = '/decide "The system with var=5 and scale=1:5 is failing" choice "Why did var=5 fail?" options="bug:Bug,config:Config" var=cause'
        res = await app.handle_escape_command(cmd)
        assert res is True

    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["state"] == "The system with var=5 and scale=1:5 is failing"
    assert call_kwargs["questions"]["q"]["type"] == "choice"
    assert call_kwargs["questions"]["q"]["instructions"] == "Why did var=5 fail?"
    assert call_kwargs["questions"]["q"]["criteria"] == {"bug": "Bug", "config": "Config"}
    assert app.buffer_manager.script_vars["cause"] == "config"
