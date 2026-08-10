from __future__ import annotations

import json

from SC2_Agent.baseline_suntzu.agent import run_decision
from SC2_Agent.baseline_suntzu.decision_prompt import build_decision_context
from SC2_Agent.baseline_suntzu.schemas import parse_plan_response, parse_plan_verification
from SC2_Agent.baseline_suntzu.verifier import verify_macro_queue
from SC2_Agent.baseline_suntzu.decision_prompt import MacroDecision
from SC2_Agent.data_tools import race_prompt_context, race_unit_names, race_upgrade_names


def _ctx():
    return build_decision_context(
        race="terran",
        enemy_race="zerg",
        strategy_summary="Marine rush.",
        strategy_automation_context="Attack.",
        obs_text="OBS-FROZEN",
        unfinished_canonical_names=[],
        canonical_unit_names=race_unit_names("terran"),
        canonical_upgrade_names=race_upgrade_names("terran"),
        race_context=race_prompt_context("terran"),
    )


class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, *, messages, model_key):
        self.calls.append({"messages": list(messages), "model_key": model_key})
        content = self.replies.pop(0)
        return {
            "content": content,
            "raw_content": content,
            "reasoning": "",
            "model_key": model_key,
            "model": "mock",
            "is_reasoning": False,
            "error": "",
            "reasoning_source": "none",
            "reasoning_extract_mode": "none",
        }


def test_plan_and_verifier_parsers():
    assert parse_plan_response(
        json.dumps({"plan_reason": "Go", "commands": ["Open barracks"]})
    )
    assert parse_plan_response(json.dumps({"plan_reason": "Go", "commands": []})) is None
    assert parse_plan_verification(json.dumps({"error_number": 0, "errors": []}))
    assert (
        parse_plan_verification(json.dumps({"error_number": 1, "errors": []})) is None
    )


def test_verify_macro_queue():
    ok = MacroDecision(reason="ok", ordered_names=["Marine", "SupplyDepot"])
    assert verify_macro_queue(ok, allowed_names=["Marine", "SupplyDepot"])["valid"]
    empty_reason = MacroDecision(reason="", ordered_names=["Marine"])
    assert not verify_macro_queue(empty_reason, allowed_names=["Marine"])["valid"]
    invalid_list = MacroDecision(reason="ok", ordered_names=None)  # type: ignore[arg-type]
    assert not verify_macro_queue(invalid_list, allowed_names=["Marine"])["valid"]
    bad = MacroDecision(reason="ok", ordered_names=["NotAUnit"])
    assert not verify_macro_queue(bad, allowed_names=["Marine"])["valid"]
    long = MacroDecision(reason="ok", ordered_names=["Marine"] * 21)
    assert not verify_macro_queue(long, allowed_names=["Marine"])["valid"]


def test_plan_refine_then_executor():
    ctx = _ctx()
    scripted = ScriptedLLM(
        [
            json.dumps({"plan_reason": "p0", "commands": ["Build army"]}),
            json.dumps({"error_number": 1, "errors": ["Too vague"]}),
            json.dumps({"plan_reason": "p1", "commands": ["Train Marines"]}),
            json.dumps({"error_number": 0, "errors": []}),
            json.dumps({"reason": "Go", "ordered_names": ["Marine", "Marine"]}),
        ]
    )
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        decision_metadata=ctx["metadata"],
        llm_call=scripted,
    )
    assert result["status"] == "completed"
    assert [c["role"] for c in result["llm_calls"]] == [
        "planner",
        "plan_verifier",
        "plan_refiner",
        "plan_verifier",
        "executor",
    ]
    assert result["decision"]["ordered_names"] == ["Marine", "Marine"]
    for call in scripted.calls:
        assert "OBS-FROZEN" in call["messages"][1]["content"]


def test_max_plan_refine_bound():
    ctx = _ctx()
    replies = [json.dumps({"plan_reason": "p", "commands": ["A"]})]
    for _ in range(3):
        replies.append(json.dumps({"error_number": 1, "errors": ["bad"]}))
        replies.append(json.dumps({"plan_reason": "p", "commands": ["B"]}))
    replies.append(json.dumps({"error_number": 1, "errors": ["bad"]}))
    replies.append(json.dumps({"reason": "Go", "ordered_names": ["Marine"]}))
    scripted = ScriptedLLM(replies)
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        decision_metadata=ctx["metadata"],
        llm_call=scripted,
    )
    assert sum(1 for c in result["llm_calls"] if c["role"] == "plan_refiner") == 3
    assert result["plan_stop_reason"] == "max_plan_refine"
    assert result["status"] == "completed"


def test_malformed_initial_executor_enters_retry():
    ctx = _ctx()
    scripted = ScriptedLLM(
        [
            json.dumps({"plan_reason": "p", "commands": ["Train army"]}),
            json.dumps({"error_number": 0, "errors": []}),
            "not-json",
            json.dumps(
                {
                    "reason": "Recovered on retry.",
                    "ordered_names": ["Marine"],
                }
            ),
        ]
    )
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        decision_metadata=ctx["metadata"],
        llm_call=scripted,
    )
    assert result["status"] == "completed"
    assert [call["role"] for call in result["llm_calls"]] == [
        "planner",
        "plan_verifier",
        "executor",
        "executor_retry",
    ]
    assert result["decision"]["ordered_names"] == ["Marine"]
    retry_user = scripted.calls[-1]["messages"][1]["content"]
    assert "missing_or_malformed_decision" in retry_user
