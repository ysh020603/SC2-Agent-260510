from __future__ import annotations

import json

from SC2_Agent.baseline_cos.agent import run_decision
from SC2_Agent.baseline_cos.decision_prompt import build_decision_context
from SC2_Agent.baseline_cos.state import CoSState
from SC2_Agent.data_tools import race_prompt_context, race_unit_names, race_upgrade_names


def _ctx(obs="OBS"):
    return build_decision_context(
        race="terran",
        enemy_race="zerg",
        strategy_summary="Marine rush.",
        strategy_automation_context="Attack.",
        obs_text=obs,
        unfinished_canonical_names=[],
        canonical_unit_names=race_unit_names("terran"),
        canonical_upgrade_names=race_upgrade_names("terran"),
        race_context=race_prompt_context("terran"),
    )


def _l1(t: float) -> str:
    return json.dumps(
        {
            "game_time": t,
            "economy": "ok",
            "production": "ok",
            "army": "ok",
            "enemy": "unknown",
            "supply": "ok",
            "committed_work": "none",
            "strategic_signal": f"signal-{t}",
        }
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


def test_history_grows_and_trims_to_five():
    state = CoSState(max_history=5)
    replies = []
    for t in range(1, 7):
        replies.append(_l1(float(t)))
        replies.append(
            json.dumps({"reason": f"r{t}", "ordered_names": ["Marine"]})
        )
    scripted = ScriptedLLM(replies)
    sizes = []
    for t in range(1, 7):
        ctx = _ctx(obs=f"OBS-{t}")
        result = run_decision(
            system_prompt=ctx["system_prompt"],
            decision_event=ctx["decision_event"],
            provider="qwen3-32b",
            cos_state=state,
            llm_call=scripted,
        )
        assert result["status"] == "completed"
        assert result["model_call_count"] == 2
        assert [call["role"] for call in result["llm_calls"]] == ["l1", "l2"]
        sizes.append(result["history_size"])
        # L1 call must not contain previous history payload key.
        l1_user = scripted.calls[-2]["messages"][1]["content"]
        assert "Recent L1 Summaries" not in l1_user
    assert sizes == [1, 2, 3, 4, 5, 5]
    assert [item["game_time"] for item in state.l1_history] == [2.0, 3.0, 4.0, 5.0, 6.0]
    # L2 on cycle 6 sees latest 5.
    l2_user = scripted.calls[-1]["messages"][1]["content"]
    assert "signal-2.0" in l2_user or "signal-2" in l2_user
    assert "signal-1" not in l2_user


def test_invalid_l1_keeps_history_unchanged():
    state = CoSState()
    ctx = _ctx()
    scripted = ScriptedLLM(["bad-l1"])
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        cos_state=state,
        llm_call=scripted,
    )
    assert result["status"] == "invalid"
    assert state.l1_history == []


def test_invalid_l2_keeps_appended_l1():
    state = CoSState()
    ctx = _ctx()
    scripted = ScriptedLLM([_l1(10.0), "bad-l2"])
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider="qwen3-32b",
        cos_state=state,
        llm_call=scripted,
    )
    assert result["status"] == "invalid"
    assert result["stop_reason"] == "l2_invalid"
    assert len(state.l1_history) == 1


def test_new_state_is_empty():
    assert CoSState().l1_history == []
