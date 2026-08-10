from __future__ import annotations

import json

from SC2_Agent.baseline_hima.agent import run_decision
from SC2_Agent.baseline_hima.decision_prompt import build_decision_context
from SC2_Agent.data_tools import race_prompt_context, race_unit_names, race_upgrade_names


def _ctx():
    return build_decision_context(
        race="terran",
        enemy_race="zerg",
        strategy_summary="Marine rush.",
        strategy_automation_context="Attack.",
        obs_text="OBS-HIMA",
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


def test_advisors_independent_and_leader_aggregates():
    ctx = _ctx()
    scripted = ScriptedLLM(
        [
            json.dumps(
                {
                    "advisor": "A",
                    "assessment": "Need supply",
                    "suggested_actions": ["SupplyDepot"],
                }
            ),
            json.dumps(
                {
                    "advisor": "B",
                    "assessment": "Need army",
                    "suggested_actions": ["Marine"],
                }
            ),
            json.dumps(
                {
                    "advisor": "C",
                    "assessment": "Need barracks",
                    "suggested_actions": ["Barracks"],
                }
            ),
            json.dumps(
                {
                    "reason": "Blend advisors.",
                    "ordered_names": ["SupplyDepot", "Barracks", "Marine"],
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
    # B does not see A's output.
    assert "Need supply" not in scripted.calls[1]["messages"][1]["content"]
    assert "Need army" not in scripted.calls[2]["messages"][1]["content"]
    leader_user = scripted.calls[3]["messages"][1]["content"]
    assert "Need supply" in leader_user
    assert "Need army" in leader_user
    assert "Need barracks" in leader_user
    assert all(call["model_key"] == "qwen3-32b" for call in scripted.calls)


def test_one_invalid_advisor_still_runs_leader():
    ctx = _ctx()
    scripted = ScriptedLLM(
        [
            json.dumps(
                {
                    "advisor": "A",
                    "assessment": "ok",
                    "suggested_actions": ["Marine"],
                }
            ),
            "bad-b",
            json.dumps(
                {
                    "advisor": "C",
                    "assessment": "ok",
                    "suggested_actions": ["SupplyDepot"],
                }
            ),
            json.dumps({"reason": "Use A/C", "ordered_names": ["Marine"]}),
        ]
    )
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["valid_advisor_count"] == 2
    assert result["status"] == "completed"


def test_all_advisors_invalid():
    ctx = _ctx()
    scripted = ScriptedLLM(["x", "y", "z"])
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["status"] == "invalid"
    assert result["stop_reason"] == "no_valid_advisors"


def test_malformed_leader_invalidates_whole_decision():
    ctx = _ctx()
    replies = [
        json.dumps(
            {
                "advisor": advisor,
                "assessment": "valid",
                "suggested_actions": ["Marine"],
            }
        )
        for advisor in ("A", "B", "C")
    ]
    scripted = ScriptedLLM([*replies, "bad-leader"])
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["model_call_count"] == 4
    assert result["status"] == "invalid"
    assert result["decision"] is None
    assert result["stop_reason"] == "leader_invalid"
