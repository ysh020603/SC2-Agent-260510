from __future__ import annotations

import json

from SC2_Agent.knowledge_v2_2_v2 import (
    build_knowledge_decision_context as build_v2_context,
)
from SC2_Agent.knowledge_v2_2_v2.main_agent import MainAgent as V2MainAgent
from SC2_Agent.knowledge_v2_2_v2.planner import (
    stabilize_queue_constraints as v2_stabilize_queue,
)
from SC2_Agent.knowledge_v2_2_v2_no_knowledge import (
    build_knowledge_decision_context as build_control_context,
)
from SC2_Agent.knowledge_v2_2_v2_no_knowledge import agent as control_agent
from SC2_Agent.knowledge_v2_2_v2_no_knowledge.sub_agent import DataSubAgent
from dummies.generic.universal_llm_bot import (
    KNOWLEDGE_V22_V2_DECISION_AGENT_MODE,
    KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE,
    SUPPORTED_DECISION_AGENT_MODES,
)


class Recorder:
    def __init__(self):
        self.events = []

    def record(self, event_type, payload=None):
        self.events.append((event_type, payload or {}))


class CapturingInvoker:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def __call__(self, phase, messages, **kwargs):
        self.calls.append((phase, messages, kwargs))
        return {"content": self.content}


def test_no_knowledge_mode_is_additive_and_preserves_v2():
    assert KNOWLEDGE_V22_V2_DECISION_AGENT_MODE == "data-v2.2-v2"
    assert (
        KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE
        == "data-v2.2-v2-no-knowledge"
    )
    assert KNOWLEDGE_V22_V2_DECISION_AGENT_MODE in SUPPORTED_DECISION_AGENT_MODES
    assert (
        KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE
        in SUPPORTED_DECISION_AGENT_MODES
    )
    assert build_control_context is build_v2_context
    assert control_agent.MainAgent is V2MainAgent
    assert control_agent.stabilize_queue_constraints is v2_stabilize_queue


def test_no_knowledge_subagent_answers_once_without_tools():
    invoker = CapturingInvoker(json.dumps({
        "answer": "Hydralisk can attack air.",
        "confidence": "medium",
        "entities_mentioned": ["Hydralisk"],
        "candidate_entities": [],
        "evidence_summary": "Model-prior answer only.",
        "limitations": ["No knowledge database or retrieval tools were available."],
    }))
    recorder = Recorder()

    session = DataSubAgent(invoker, recorder).run(
        "Which Zerg unit can attack Battlecruiser?", 2
    )

    assert len(invoker.calls) == 1
    phase, messages, kwargs = invoker.calls[0]
    assert phase.endswith("_direct_answer")
    assert "tools" not in kwargs
    assert kwargs["reasoning"] is False
    assert "Answer that question directly" in messages[0]["content"]
    assert "without calling tools" in messages[0]["content"]
    assert session["selected_tools"] == []
    assert session["observations"] == []
    assert session["answer_source"] == "model_prior"
    assert session["knowledge_database_access"] is False
    assert not any(
        event in {"tool_request", "tool_response"} for event, _ in recorder.events
    )


def test_no_knowledge_subagent_falls_back_for_unstructured_reply():
    invoker = CapturingInvoker("Hydralisk is probably appropriate.")
    session = DataSubAgent(invoker, Recorder()).run("Answer directly.", -1)

    assert session["reply"]["confidence"] == "low"
    assert session["reply"]["answer"] == "Hydralisk is probably appropriate."
    assert "Reply contract error" in session["reply"]["limitations"][0]
