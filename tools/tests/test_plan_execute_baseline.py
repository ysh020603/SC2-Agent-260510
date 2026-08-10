from __future__ import annotations

import json

from SC2_Agent.baseline_plan_execute.agent import run_decision
from SC2_Agent.baseline_plan_execute.decision_prompt import build_decision_context
from SC2_Agent.baseline_plan_execute.schemas import (
    MAX_QUEUE_NAMES,
    parse_executor_response,
    parse_plan_response,
)
from SC2_Agent.data_tools import race_prompt_context, race_unit_names, race_upgrade_names


def _context():
    return build_decision_context(
        race="terran",
        enemy_race="zerg",
        strategy_summary="Marine rush pressure.",
        strategy_automation_context="Attack at power 20.",
        obs_text="[Time] 02:00\n[Economy] 500 minerals, 100 gas. Supply 20/23.",
        unfinished_canonical_names=["Barracks"],
        canonical_unit_names=race_unit_names("terran"),
        canonical_upgrade_names=race_upgrade_names("terran"),
        race_context=race_prompt_context("terran"),
        decision_cycle=1,
        trigger_reason="initial_decision",
        game_time_seconds=120,
        decision_interval_seconds=60,
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


def test_parse_plan_valid_and_invalid():
    valid = parse_plan_response(
        json.dumps(
            {
                "plan_summary": "Stabilize then produce.",
                "steps": [
                    {"step_id": 1, "objective": "Defend"},
                    {"step_id": 2, "objective": "Produce"},
                ],
            }
        )
    )
    assert valid is not None
    assert len(valid.steps) == 2
    assert parse_plan_response('{"plan_summary":"x","steps":[]}') is None
    assert (
        parse_plan_response(
            json.dumps(
                {
                    "plan_summary": "too many",
                    "steps": [
                        {"step_id": i, "objective": f"s{i}"} for i in range(1, 6)
                    ],
                }
            )
        )
        is None
    )
    assert (
        parse_plan_response(
            json.dumps(
                {
                    "plan_summary": "bad ids",
                    "steps": [
                        {"step_id": 2, "objective": "A"},
                        {"step_id": 1, "objective": "B"},
                    ],
                }
            )
        )
        is None
    )


def test_parse_executor_step_id_must_match():
    text = json.dumps(
        {"step_id": 1, "reason": "Marines now.", "ordered_names": ["Marine"]}
    )
    assert parse_executor_response(text, expected_step_id=1) is not None
    assert parse_executor_response(text, expected_step_id=2) is None


def test_sequential_orchestration_and_frozen_context():
    ctx = _context()
    scripted = ScriptedLLM(
        [
            json.dumps(
                {
                    "plan_summary": "Open with production then army.",
                    "steps": [
                        {"step_id": 1, "objective": "Build barracks"},
                        {"step_id": 2, "objective": "Train marines"},
                        {"step_id": 3, "objective": "Add supply"},
                    ],
                }
            ),
            json.dumps(
                {
                    "step_id": 1,
                    "reason": "Barracks first.",
                    "ordered_names": ["Barracks"],
                }
            ),
            json.dumps(
                {
                    "step_id": 2,
                    "reason": "Army next.",
                    "ordered_names": ["Marine", "Marine"],
                }
            ),
            json.dumps(
                {
                    "step_id": 3,
                    "reason": "Supply.",
                    "ordered_names": ["SupplyDepot"],
                }
            ),
        ]
    )
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["status"] == "completed"
    assert result["model_call_count"] == 4
    assert [call["role"] for call in result["llm_calls"]] == [
        "planner",
        "executor",
        "executor",
        "executor",
    ]
    assert result["decision"]["ordered_names"] == [
        "Barracks",
        "Marine",
        "Marine",
        "SupplyDepot",
    ]
    assert result["decision"]["reason"] == "Open with production then army."
    # Executor 2 sees step-1 fragment.
    step2_user = scripted.calls[2]["messages"][1]["content"]
    assert '"step_id": 1' in step2_user
    assert "Barracks" in step2_user
    # Frozen observation in every call.
    for call in scripted.calls:
        assert ctx["decision_event"] in call["messages"][1]["content"]
    # Only one planner call.
    assert sum(1 for call in result["llm_calls"] if call["role"] == "planner") == 1


def test_malformed_executor_fail_closed():
    ctx = _context()
    scripted = ScriptedLLM(
        [
            json.dumps(
                {
                    "plan_summary": "Two steps.",
                    "steps": [
                        {"step_id": 1, "objective": "A"},
                        {"step_id": 2, "objective": "B"},
                    ],
                }
            ),
            "not-json",
        ]
    )
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["status"] == "invalid"
    assert result["decision"] is None
    assert result["orchestration"]["error"] == "executor_step_1_malformed"


def test_queue_length_violation():
    ctx = _context()
    long_names = ["Marine"] * (MAX_QUEUE_NAMES + 1)
    scripted = ScriptedLLM(
        [
            json.dumps(
                {
                    "plan_summary": "Overflow.",
                    "steps": [{"step_id": 1, "objective": "Spam"}],
                }
            ),
            json.dumps(
                {
                    "step_id": 1,
                    "reason": "Too many.",
                    "ordered_names": long_names,
                }
            ),
        ]
    )
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["status"] == "invalid"
    assert result["orchestration"]["queue_length_violation"] is True


def test_no_knowledge_imports_in_package():
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2] / "SC2_Agent" / "baseline_plan_execute"
    pattern = re.compile(
        r"DataSubAgent|knowledge_v2|query_enemy|query_combat|dataset_store"
    )
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert pattern.search(text) is None, path.name
