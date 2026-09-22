"""Tests for decide_score, decide_choice, and decide_noul tools."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from chatybot.decision_client import DecisionAPIError
from chatybot.tools.decide_tools import decide_choice, decide_noul, decide_score


def _mock_score_response(score="8", confidence=0.91, probabilities=None):
    if probabilities is None:
        probabilities = {"7": 0.15, "8": 0.75, "9": 0.10}
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
    }


def _mock_choice_response(choice="approve", confidence=0.88, probabilities=None):
    if probabilities is None:
        probabilities = {"approve": 0.88, "reject": 0.12}
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
    }


def _mock_noul_response(answer=True, confidence=0.94):
    return {
        "model": "typesafe/jev-1.13",
        "answers": {
            "q": {
                "type": "noul",
                "answer": answer,
                "confidence": confidence,
                "probabilities": {"true": 0.94, "false": 0.06},
            }
        },
    }


def test_decide_score_scale():
    mock_resp = _mock_score_response(score="8", confidence=0.91)
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        res = decide_score(
            state="Draft report text",
            instructions="Grade accuracy from 1 to 10",
            scale="1:10",
        )

    assert res["status"] == "success"
    assert res["type"] == "score"
    assert res["result"] == "8"
    assert res["score"] == "8"
    assert res["confidence"] == 0.91
    assert res["top_probability"] == 0.75
    assert res["probabilities"] == {"7": 0.15, "8": 0.75, "9": 0.10}
    assert res["is_fallback"] is False
    assert res["model"] == "typesafe/jev-1.13"

    mock_eval.assert_called_once()
    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["questions"]["q"]["type"] == "score"
    assert call_kwargs["questions"]["q"]["criteria"] == [str(i) for i in range(1, 11)]


def test_decide_score_custom_levels():
    mock_resp = _mock_score_response(score="high", confidence=0.85, probabilities={"low": 0.05, "medium": 0.10, "high": 0.85})
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        res = decide_score(
            state="Server metrics",
            instructions="Assess load severity",
            levels=["low", "medium", "high"],
        )

    assert res["status"] == "success"
    assert res["score"] == "high"
    assert res["confidence"] == 0.85
    call_kwargs = mock_eval.call_args.kwargs
    assert call_kwargs["questions"]["q"]["criteria"] == ["low", "medium", "high"]


def test_decide_score_invalid_scale():
    res = decide_score(
        state="Test",
        instructions="Grade",
        scale="10:1",
    )
    assert res["status"] == "error"
    assert "must be less than max" in res["message"]


def test_decide_score_scale_too_large():
    res = decide_score(
        state="Test",
        instructions="Grade",
        scale="1:100",
    )
    assert res["status"] == "error"
    assert "exceeds maximum of 10 points" in res["message"]


def test_decide_choice_dict():
    mock_resp = _mock_choice_response(choice="approve", confidence=0.88)
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        res = decide_choice(
            state="PR review details",
            instructions="Approve or reject?",
            options={"approve": "Meets guidelines", "reject": "Has regressions"},
        )

    assert res["status"] == "success"
    assert res["type"] == "choice"
    assert res["result"] == "approve"
    assert res["choice"] == "approve"
    assert res["confidence"] == 0.88
    assert res["top_probability"] == 0.88


def test_decide_choice_list_and_string():
    mock_resp = _mock_choice_response(choice="opt_b", confidence=0.75)
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        # List of strings
        res_list = decide_choice(
            state="Data",
            instructions="Pick one",
            options=["opt_a", "opt_b"],
        )
        assert res_list["status"] == "success"
        assert res_list["result"] == "opt_b"

        # Formatted string
        res_str = decide_choice(
            state="Data",
            instructions="Pick one",
            options="opt_a: Option Alpha, opt_b: Option Beta",
        )
        assert res_str["status"] == "success"
        assert res_str["result"] == "opt_b"


def test_decide_choice_empty_options():
    res = decide_choice(
        state="Data",
        instructions="Pick",
        options={},
    )
    assert res["status"] == "error"
    assert "At least one option must be provided" in res["message"]


def test_decide_noul():
    mock_resp = _mock_noul_response(answer=True, confidence=0.94)
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        res = decide_noul(
            state="The capital of France is Paris.",
            instructions="Is this claim factually accurate?",
        )

    assert res["status"] == "success"
    assert res["type"] == "noul"
    assert res["result"] == "true"
    assert res["answer"] == "true"
    assert res["confidence"] == 0.94


def test_threshold_fallback():
    mock_resp = _mock_score_response(score="8", confidence=0.45)
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        res = decide_score(
            state="Ambiguous draft",
            instructions="Grade",
            scale="1:10",
            threshold=0.70,
        )

    assert res["status"] == "success"
    assert res["is_fallback"] is True
    assert res["result"] == "FALLBACK"
    assert res["raw_answer"] == "8"
    assert res["confidence"] == 0.45


def test_target_variable_binding():
    class DummyBufferManager:
        def __init__(self):
            self.vars = {}

        def set_script_var(self, name, val, allow_protected=False):
            self.vars[name] = val

    class DummyApp:
        def __init__(self):
            self.buffer_manager = DummyBufferManager()

    app = DummyApp()
    mock_resp = _mock_choice_response(choice="approve", confidence=0.88)
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        res = decide_choice(
            state="Draft",
            instructions="Pick",
            options={"approve": "OK", "reject": "No"},
            target_variable="review_verdict",
            app=app,
        )

    assert res["target_variable"] == "review_verdict"
    assert app.buffer_manager.vars["review_verdict"] == "approve"
    assert app.buffer_manager.vars["review_verdict_conf"] == "0.88"


def test_api_error_handling():
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, side_effect=DecisionAPIError(500, "Service unavailable")):
        res = decide_noul(
            state="Test",
            instructions="Check",
        )
    assert res["status"] == "error"
    assert "Decision API error (500)" in res["message"]


def test_missing_api_key():
    with patch("chatybot.tools.decide_tools._resolve_decision_config", return_value=({"api_key": "NON_EXISTENT_KEY"}, "")):
        res = decide_score(
            state="Test",
            instructions="Check",
        )
    assert res["status"] == "error"
    assert "API key 'NON_EXISTENT_KEY' is not set" in res["message"]


def test_dispatcher_route_decide_tools():
    import os
    from chatybot.dispatcher import load_configs, validate_and_route

    config_path = os.path.join(os.path.dirname(__file__), "..", "src", "chatybot", "tools_config.toml")
    config = load_configs(config_path)

    assert "decide_score" in config["tools"]
    assert "decide_choice" in config["tools"]
    assert "decide_noul" in config["tools"]
    assert config["tools"]["decide_score"]["enabled"] is False

    # Route with tool override enabled
    with patch.dict(os.environ, {"CHATYBOT_TOOL_OVERRIDES": json.dumps({"decide_score": True})}):
        invocation = {
            "tool": "decide_score",
            "arguments": {
                "state": "Sample text",
                "instructions": "Grade on 1:5 scale",
                "scale": "1:5",
            },
        }
        func, args, kwargs = validate_and_route(invocation, config)
        assert func.__name__ == "decide_score"
        assert kwargs["state"] == "Sample text"
        assert kwargs["scale"] == "1:5"


def test_threshold_out_of_range():
    res_neg = decide_score(
        state="Test",
        instructions="Grade",
        threshold=-0.5,
    )
    assert res_neg["status"] == "error"
    assert "threshold must be between 0.0 and 1.0" in res_neg["message"]

    res_high = decide_score(
        state="Test",
        instructions="Grade",
        threshold=1.5,
    )
    assert res_high["status"] == "error"
    assert "threshold must be between 0.0 and 1.0" in res_high["message"]


def test_decide_score_json_string_levels():
    mock_resp = _mock_score_response(score="good", confidence=0.88)
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        res = decide_score(
            state="Draft",
            instructions="Grade",
            levels='["poor", "fair", "good"]',
        )
    assert res["status"] == "success"
    assert res["score"] == "good"
    assert mock_eval.call_args.kwargs["questions"]["q"]["criteria"] == ["poor", "fair", "good"]


def test_decide_choice_json_string_options():
    mock_resp = _mock_choice_response(choice="opt_a", confidence=0.92)
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp) as mock_eval:
        res = decide_choice(
            state="Draft",
            instructions="Pick",
            options='{"opt_a": "First Option", "opt_b": "Second Option"}',
        )
    assert res["status"] == "success"
    assert res["choice"] == "opt_a"
    assert mock_eval.call_args.kwargs["questions"]["q"]["criteria"] == {
        "opt_a": "First Option",
        "opt_b": "Second Option",
    }


def test_decide_noul_case_insensitive_prob():
    # Probability keys as capitalized string or boolean True
    mock_resp = {
        "model": "typesafe/jev-1.13",
        "answers": {
            "q": {
                "type": "noul",
                "answer": True,
                "confidence": 0.94,
                "probabilities": {"True": 0.94, "False": 0.06},
            }
        },
    }
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        res = decide_noul(
            state="Paris is the capital of France.",
            instructions="Is this claim true?",
        )
    assert res["status"] == "success"
    assert res["result"] == "true"
    assert res["top_probability"] == 0.94


@pytest.mark.anyio
async def test_app_dispatch_tool_in_process_with_registers():
    from chatybot.chatybot_app import ChatybotApp

    app = ChatybotApp()
    app.initialize()
    app.tool_overrides["decide_choice"] = True

    tool_call = {
        "tool": "decide_choice",
        "arguments": {
            "state": "Code diff looks clean and tested.",
            "instructions": "Should this PR be approved?",
            "options": {"approve": "Safe to merge", "reject": "Needs work"},
            "target_variable": "merge_decision",
        },
    }

    mock_resp = _mock_choice_response(choice="approve", confidence=0.89, probabilities={"approve": 0.89, "reject": 0.11})
    with patch("chatybot.tools.decide_tools.evaluate", new_callable=AsyncMock, return_value=mock_resp):
        result_str = await app.dispatch_tool(json.dumps(tool_call))

    assert result_str is not None
    res_data = json.loads(result_str)
    assert res_data["status"] == "success"
    assert res_data["result"]["choice"] == "approve"

    # Verify that in-process dispatch set target_variable and calibration registers
    assert app.buffer_manager.get_script_var("merge_decision") == "approve"
    assert app.buffer_manager.get_script_var("merge_decision_conf") == "0.89"
    assert app.buffer_manager.get_script_var("merge_decision_prob") == "0.89"


