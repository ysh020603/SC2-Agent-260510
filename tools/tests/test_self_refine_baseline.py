from __future__ import annotations

import json

from SC2_Agent.baseline_self_refine.agent import run_decision
from SC2_Agent.baseline_self_refine.decision_prompt import build_decision_context
from SC2_Agent.baseline_self_refine.schemas import parse_feedback_response
from SC2_Agent.data_tools import race_prompt_context, race_unit_names, race_upgrade_names


def _context(obs_text: str = "[Time] 02:00\n[Economy] 500 minerals."):
    return build_decision_context(
        race="terran",
        enemy_race="zerg",
        strategy_summary="Marine rush pressure.",
        strategy_automation_context="Attack at power 20.",
        obs_text=obs_text,
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


def test_feedback_parser():
    ok = parse_feedback_response(
        json.dumps(
            {
                "needs_refinement": True,
                "summary": "Need army first.",
                "issues": [
                    {
                        "issue": "Economy first under threat.",
                        "suggestion": "Train Marines earlier.",
                    }
                ],
            }
        )
    )
    assert ok is not None and ok.needs_refinement is True
    assert parse_feedback_response('{"needs_refinement":"yes","summary":"x"}') is None


def test_critic_immediately_satisfied():
    ctx = _context()
    scripted = ScriptedLLM(
        [
            json.dumps(
                {
                    "reason": "Initial queue.",
                    "ordered_names": ["SupplyDepot", "Barracks", "Marine"],
                }
            ),
            json.dumps(
                {
                    "needs_refinement": False,
                    "summary": "Looks good.",
                    "issues": [],
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
    assert result["stop_reason"] == "critic_satisfied"
    assert result["model_call_count"] == 2
    assert [call["role"] for call in result["llm_calls"]] == ["init", "feedback"]
    assert result["decision"]["ordered_names"] == [
        "SupplyDepot",
        "Barracks",
        "Marine",
    ]


def test_one_refinement_then_satisfied():
    ctx = _context()
    scripted = ScriptedLLM(
        [
            json.dumps({"reason": "Init.", "ordered_names": ["SCV", "SCV"]}),
            json.dumps(
                {
                    "needs_refinement": True,
                    "summary": "Need army.",
                    "issues": [
                        {
                            "issue": "No combat units.",
                            "suggestion": "Add Marines.",
                        }
                    ],
                }
            ),
            json.dumps(
                {
                    "reason": "Revised.",
                    "ordered_names": ["Marine", "Marine", "SupplyDepot"],
                }
            ),
            json.dumps(
                {
                    "needs_refinement": False,
                    "summary": "Better.",
                    "issues": [],
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
    assert result["stop_reason"] == "critic_satisfied"
    assert result["model_call_count"] == 4
    assert result["decision"]["ordered_names"] == [
        "Marine",
        "Marine",
        "SupplyDepot",
    ]


def test_max_two_refine_rounds_no_third():
    ctx = _context()
    replies = [
        json.dumps({"reason": "Init.", "ordered_names": ["SCV"]}),
    ]
    for _ in range(2):
        replies.append(
            json.dumps(
                {
                    "needs_refinement": True,
                    "summary": "Keep refining.",
                    "issues": [
                        {"issue": "Still weak.", "suggestion": "More Marines."}
                    ],
                }
            )
        )
        replies.append(
            json.dumps(
                {
                    "reason": "Refined.",
                    "ordered_names": ["Marine", "Marine"],
                }
            )
        )
    scripted = ScriptedLLM(replies)
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["stop_reason"] == "max_refine_rounds"
    assert result["model_call_count"] == 5  # init + 2*(feedback+refine)
    assert sum(1 for call in result["llm_calls"] if call["role"] == "refine") == 2
    assert sum(1 for call in result["llm_calls"] if call["role"] == "feedback") == 2


def test_malformed_feedback_keeps_candidate():
    ctx = _context()
    scripted = ScriptedLLM(
        [
            json.dumps({"reason": "Init.", "ordered_names": ["Marine"]}),
            "bad-feedback",
        ]
    )
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["stop_reason"] == "feedback_invalid"
    assert result["decision"]["ordered_names"] == ["Marine"]


def test_malformed_refine_keeps_previous():
    ctx = _context()
    scripted = ScriptedLLM(
        [
            json.dumps({"reason": "Init.", "ordered_names": ["Barracks"]}),
            json.dumps(
                {
                    "needs_refinement": True,
                    "summary": "Need units.",
                    "issues": [
                        {"issue": "Empty army.", "suggestion": "Train Marines."}
                    ],
                }
            ),
            "bad-refine",
        ]
    )
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["stop_reason"] == "refine_invalid"
    assert result["decision"]["ordered_names"] == ["Barracks"]


def test_init_invalid_whole_decision_invalid():
    ctx = _context()
    scripted = ScriptedLLM(["not-json"])
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert result["status"] == "invalid"
    assert result["decision"] is None
    assert result["stop_reason"] == "init_invalid"


def test_no_persistent_memory_across_decisions():
    ctx = _context(obs_text="FROZEN-A")
    scripted = ScriptedLLM(
        [
            json.dumps({"reason": "A1", "ordered_names": ["Marine"]}),
            json.dumps(
                {
                    "needs_refinement": False,
                    "summary": "ok",
                    "issues": [],
                }
            ),
            json.dumps({"reason": "B1", "ordered_names": ["SCV"]}),
            json.dumps(
                {
                    "needs_refinement": False,
                    "summary": "ok",
                    "issues": [],
                }
            ),
        ]
    )
    first = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    ctx2 = _context(obs_text="FROZEN-B")
    second = run_decision(
        system_prompt=ctx2["system_prompt"],
        decision_event=ctx2["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    assert first["decision"]["ordered_names"] == ["Marine"]
    assert second["decision"]["ordered_names"] == ["SCV"]
    second_init_user = scripted.calls[2]["messages"][1]["content"]
    assert "FROZEN-B" in second_init_user
    assert "Need army" not in second_init_user
    assert "A1" not in second_init_user


def test_frozen_context_all_rounds():
    ctx = _context(obs_text="SAME-OBS")
    scripted = ScriptedLLM(
        [
            json.dumps({"reason": "Init.", "ordered_names": ["SCV"]}),
            json.dumps(
                {
                    "needs_refinement": True,
                    "summary": "Refine.",
                    "issues": [
                        {"issue": "Weak.", "suggestion": "Marine."}
                    ],
                }
            ),
            json.dumps({"reason": "Refined.", "ordered_names": ["Marine"]}),
            json.dumps(
                {
                    "needs_refinement": False,
                    "summary": "Done.",
                    "issues": [],
                }
            ),
        ]
    )
    run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        llm_call=scripted,
    )
    for call in scripted.calls:
        assert "SAME-OBS" in call["messages"][1]["content"]
