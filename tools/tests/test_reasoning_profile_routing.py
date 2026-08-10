from __future__ import annotations

import importlib
import json

import pytest


class Recorder:
    def __init__(self):
        self.events = []

    def record(self, event_type, payload=None):
        self.events.append((event_type, payload or {}))


class ScriptedInvoker:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def __call__(self, phase, messages, **kwargs):
        self.calls.append({"phase": phase, "messages": messages, "kwargs": kwargs})
        reply = next(self.replies)
        if isinstance(reply, dict):
            return reply
        return {"content": reply, "raw_message": {"content": reply}}


@pytest.mark.parametrize(
    "module_name",
    [
        "SC2_Agent.knowledge_v2_2.runtime",
        "SC2_Agent.knowledge_v2_2_v2.runtime",
    ],
)
def test_profile_is_the_default_reasoning_authority(monkeypatch, module_name):
    runtime = importlib.import_module(module_name)
    pool = {
        "llm_agents_pool": {
            "qwen3-32b": {"is_reasoning": False},
            "qwen3-32b_think": {"is_reasoning": True},
        }
    }
    calls = []

    monkeypatch.setattr(runtime, "load_agent_pool", lambda: pool)
    monkeypatch.setattr(runtime, "acquire_provider_slot", lambda *args: 0.0)

    def fake_call_openai_detailed(**kwargs):
        calls.append(kwargs)
        return {
            "content": "{}",
            "model_key": kwargs["model_key"],
            "model": "Qwen3-32B",
            "is_reasoning": kwargs["is_reasoning"],
            "reasoning": "reasoning" if kwargs["is_reasoning"] else "",
            "reasoning_source": "content_think_tags" if kwargs["is_reasoning"] else "none",
            "reasoning_extract_mode": "content_think_tags",
            "raw_content": "<think>reasoning</think>{}" if kwargs["is_reasoning"] else "{}",
            "raw_message": {"content": "{}"},
            "error": "",
        }

    monkeypatch.setattr(runtime, "call_openai_detailed", fake_call_openai_detailed)

    think = runtime.LLMInvoker(
        Recorder(),
        "qwen3-32b_think",
        None,
        agent_role="main_agent",
    )
    think_result = think("main_round_1", [{"role": "user", "content": "decide"}])

    assert think.reasoning_mode is True
    assert calls[-1]["model_key"] == "qwen3-32b_think"
    assert calls[-1]["is_reasoning"] is True
    assert think_result["configured_model_key"] == "qwen3-32b_think"
    assert think_result["model_key"] == "qwen3-32b_think"
    assert think_result["reasoning_requested"] is True
    assert think_result["is_reasoning"] is True

    nothink = runtime.LLMInvoker(
        Recorder(),
        "qwen3-32b",
        None,
        agent_role="main_agent",
    )
    nothink_result = nothink(
        "main_round_1", [{"role": "user", "content": "decide"}]
    )

    assert nothink.reasoning_mode is False
    assert calls[-1]["model_key"] == "qwen3-32b"
    assert calls[-1]["is_reasoning"] is False
    assert nothink_result["reasoning_requested"] is False
    assert nothink_result["is_reasoning"] is False


@pytest.mark.parametrize(
    "module_name",
    [
        "SC2_Agent.knowledge_v2_2.runtime",
        "SC2_Agent.knowledge_v2_2_v2.runtime",
    ],
)
def test_explicit_nonreasoning_subcall_uses_matching_profile(monkeypatch, module_name):
    runtime = importlib.import_module(module_name)
    pool = {
        "llm_agents_pool": {
            "qwen3-32b": {"is_reasoning": False},
            "qwen3-32b_think": {"is_reasoning": True},
        }
    }
    calls = []
    monkeypatch.setattr(runtime, "load_agent_pool", lambda: pool)
    monkeypatch.setattr(runtime, "acquire_provider_slot", lambda *args: 0.0)

    def fake_call_openai_detailed(**kwargs):
        calls.append(kwargs)
        return {
            "content": "{}",
            "model_key": kwargs["model_key"],
            "model": "Qwen3-32B",
            "is_reasoning": kwargs["is_reasoning"],
            "reasoning": "",
            "reasoning_source": "none",
            "reasoning_extract_mode": "none",
            "raw_content": "{}",
            "raw_message": {"content": "{}"},
            "error": "",
        }

    monkeypatch.setattr(runtime, "call_openai_detailed", fake_call_openai_detailed)
    invoker = runtime.LLMInvoker(
        Recorder(),
        "qwen3-32b_think",
        None,
        agent_role="data_subagent_no_knowledge",
    )

    result = invoker(
        "direct_answer",
        [{"role": "user", "content": "answer"}],
        reasoning=False,
    )

    assert calls[-1]["model_key"] == "qwen3-32b"
    assert calls[-1]["is_reasoning"] is False
    assert result["configured_model_key"] == "qwen3-32b_think"
    assert result["model_key"] == "qwen3-32b"
    assert result["profile_reasoning_mode"] is True
    assert result["reasoning_override"] is False
    assert result["reasoning_requested"] is False


@pytest.mark.parametrize(
    "module_name",
    [
        "SC2_Agent.knowledge_v2_2.main_agent",
        "SC2_Agent.knowledge_v2_2_v2.main_agent",
    ],
)
def test_mainagent_contract_repair_keeps_profile_reasoning(module_name):
    module = importlib.import_module(module_name)
    invoker = ScriptedInvoker(
        [
            "not valid JSON",
            json.dumps(
                {
                    "action": "final_decision",
                    "reason": "Repaired.",
                    "ordered_names": [],
                }
            ),
        ]
    )
    mainagent = module.MainAgent(invoker, Recorder())

    if module_name.endswith("knowledge_v2_2.main_agent"):
        decision, _, _ = mainagent.run(
            "system", "event", lambda question, round_index: None
        )
    else:
        decision, _, _ = mainagent.run(
            "system", "event", lambda request, round_index: None
        )

    assert decision["action"] == "final_decision"
    assert len(invoker.calls) == 2
    assert "reasoning" not in invoker.calls[0]["kwargs"]
    assert "reasoning" not in invoker.calls[1]["kwargs"]


@pytest.mark.parametrize(
    "module_name",
    [
        "SC2_Agent.knowledge_v2_2.sub_agent",
        "SC2_Agent.knowledge_v2_2_v2.sub_agent",
    ],
)
def test_data_subagent_selection_and_answer_keep_profile_reasoning(module_name):
    module = importlib.import_module(module_name)
    selection = json.dumps(
        {
            "selected_tools": ["get_entity"],
            "selection_summary": "Look up the requested entity.",
        }
    )
    answer = json.dumps(
        {
            "answer": "Marine is a Terran unit.",
            "confidence": "high",
            "entities_mentioned": ["Marine"],
            "candidate_entities": [],
            "evidence_summary": "Entity result.",
            "limitations": [],
        }
    )
    invoker = ScriptedInvoker(
        [
            selection,
            {
                "content": answer,
                "raw_message": {"content": answer, "tool_calls": []},
            },
        ]
    )
    subagent = module.DataSubAgent(invoker, Recorder())

    session = subagent.run("What is Marine?", 0)

    assert session["reply"]["confidence"] == "high"
    assert len(invoker.calls) == 2
    assert "reasoning" not in invoker.calls[0]["kwargs"]
    assert "reasoning" not in invoker.calls[1]["kwargs"]


def test_knowledge_summary_exposes_configured_and_effective_reasoning_fields():
    from dummies.generic.universal_llm_bot import UniversalLLMBot

    summary = UniversalLLMBot._knowledge_call_summary(
        {
            "knowledge_result": {
                "agent_version": "decision-data-v2.2-v2",
                "mainagent_provider": "qwen3-32b_think",
                "data_subagent_provider": "qwen3-32b",
                "reasoning_policy": "per_role_api_profile",
                "mainagent_reasoning_enabled": True,
                "data_subagent_reasoning_enabled": False,
                "reasoning_trace": [
                    {
                        "phase": "main_round_1",
                        "agent_role": "main_agent",
                        "configured_model_key": "qwen3-32b_think",
                        "model_key": "qwen3-32b_think",
                        "profile_reasoning_mode": True,
                        "reasoning_override": None,
                        "reasoning_requested": True,
                        "is_reasoning": True,
                    }
                ],
            }
        }
    )

    assert summary["configured_mainagent_model_key"] == "qwen3-32b_think"
    assert summary["reasoning_policy"] == "per_role_api_profile"
    assert summary["mainagent_reasoning_enabled"] is True
    assert summary["data_subagent_reasoning_enabled"] is False
    assert summary["model_calls"][0]["configured_model_key"] == "qwen3-32b_think"
    assert summary["model_calls"][0]["model_key"] == "qwen3-32b_think"
    assert summary["model_calls"][0]["reasoning_requested"] is True
