from __future__ import annotations

import hashlib
import json
from pathlib import Path

import run_vs_ai
import SC2_Agent.knowledge_v2_2.agent as knowledge_agent_module
from SC2_Agent.data_tools import race_unit_names, race_upgrade_names
from SC2_Agent.knowledge_v2_2.contracts import validate_main_decision
from SC2_Agent.knowledge_v2_2.decision_prompt import build_knowledge_decision_context
from SC2_Agent.knowledge_v2_2.main_agent import MainAgent
from SC2_Agent.knowledge_v2_2.model_view import EvidenceReferenceMap, OPAQUE_ID_KEYS
from SC2_Agent.knowledge_v2_2.query.data_store import DEFAULT_DATABASE_PATH, get_dataset_store
from SC2_Agent.knowledge_v2_2.tool_registry import CATALOG, ToolRegistry, dispatcher_tool_names
from dummies.generic.universal_llm_bot import (
    KNOWLEDGE_V22_DECISION_AGENT_MODE,
    NAIVE_DECISION_AGENT_MODE,
    UniversalLLMBot,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "SC2_Agent" / "knowledge_v2_2"


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
        self.calls.append({"phase": phase, "messages": list(messages), **kwargs})
        return {"content": next(self.replies)}


def _prompt_context():
    return build_knowledge_decision_context(
        race="terran",
        enemy_race="zerg",
        strategy_summary="Open with bio pressure.",
        strategy_automation_context="Attack at power 26.",
        obs_text="[Time] 00:00\n[Economy] 50 minerals.\nActive Queues: none.",
        unfinished_canonical_names=["Barracks", "Marine"],
        canonical_unit_names=race_unit_names("terran"),
        canonical_upgrade_names=race_upgrade_names("terran"),
        race_context="Supply provider: SupplyDepot.",
        decision_cycle=2,
        trigger_reason="interval_elapsed",
        game_time_seconds=60,
        decision_interval_seconds=60,
    )


def _contains_opaque_key(value):
    if isinstance(value, dict):
        return any(key in OPAQUE_ID_KEYS or _contains_opaque_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_opaque_key(item) for item in value)
    return False


def test_all_universal_bot_entry_points_default_to_v22():
    assert run_vs_ai.DEFAULT_DECISION_AGENT_MODE == KNOWLEDGE_V22_DECISION_AGENT_MODE
    assert run_vs_ai.DEFAULT_DECISION_MODEL == "Kimi-k2.5"
    assert run_vs_ai.DEFAULT_DATA_SUBAGENT_MODEL == "Kimi-k2.5"
    bot = UniversalLLMBot(race_name="terran")
    assert bot.decision_agent_mode == KNOWLEDGE_V22_DECISION_AGENT_MODE
    assert bot.decision_model_key == "Kimi-k2.5"
    assert bot.data_subagent_model_key == "Kimi-k2.5"
    assert NAIVE_DECISION_AGENT_MODE == "naive"


def test_knowledge_prompt_has_original_decision_context_and_data_boundary():
    context = _prompt_context()
    system = context["system_prompt"]
    user = context["decision_event"]
    assert "COMPLETE new queue" in system
    assert "SupplyDepot, Pylon, and Overlord each add 8" in system
    assert "normally no more than 20 names" in system
    assert "DataSubAgent" in system
    assert "never expand this output allowlist" in system
    assert "Open with bio pressure." in system
    assert "Supply provider: SupplyDepot." in system
    assert "Cycle: 2" in user
    assert "Trigger: interval_elapsed" in user
    assert '["Barracks", "Marine"]' in user
    assert "{{" not in system


def test_main_contract_returns_macro_decision_shape():
    decision = validate_main_decision({
        "action": "final_decision",
        "reason": "Add production.",
        "ordered_names": ["SupplyDepot", "Barracks", "Marine", "Marine"],
    })
    assert decision["reason"] == "Add production."
    assert decision["ordered_names"][-2:] == ["Marine", "Marine"]


def test_mainagent_can_finalize_without_subagent_exchange():
    invoker = ScriptedInvoker([
        json.dumps({
            "action": "final_decision",
            "reason": "The routine opening is already supported by the visible strategy and state.",
            "ordered_names": ["SCV", "SupplyDepot"],
        }),
    ])
    recorder = Recorder()
    main = MainAgent(invoker, recorder)

    decision, decisions, sessions = main.run("system", "event", lambda *_: None)
    assert decision["ordered_names"] == ["SCV", "SupplyDepot"]
    assert len(decisions) == 1
    assert sessions == []


def test_mainagent_can_choose_subagent_exchange_before_finalizing():
    invoker = ScriptedInvoker([
        json.dumps({
            "action": "ask_subagent",
            "sub_question": "Which structure produces Marine?",
            "decision_summary": "Verify production data.",
        }),
        json.dumps({
            "action": "final_decision",
            "reason": "Use the verified Barracks production route.",
            "ordered_names": ["SupplyDepot", "Barracks", "Marine"],
        }),
    ])
    recorder = Recorder()
    main = MainAgent(invoker, recorder)

    def ask(question, main_round):
        return {
            "session_id": "session-1",
            "main_round": main_round,
            "question": question,
            "selected_tools": ["query_reverse_production_sources"],
            "reply": {
                "answer": "Marine is produced by Barracks.",
                "confidence": "high",
                "evidence_summary": "Production relation.",
                "limitations": [],
            },
            "observations": [],
        }

    decision, decisions, sessions = main.run("system", "event", ask)
    assert decision["action"] == "final_decision"
    assert decision["ordered_names"] == ["SupplyDepot", "Barracks", "Marine"]
    assert len(decisions) == 2
    assert len(sessions) == 1


def test_run_decision_routes_main_and_subagent_to_independent_providers(monkeypatch, tmp_path):
    created = []

    class FakeInvoker:
        def __init__(self, recorder, provider, model, enable_reasoning, *, agent_role, trace):
            self.provider = provider
            self.agent_role = agent_role
            self.trace = trace
            created.append(self)

    class FakeSubAgent:
        def __init__(self, invoker, recorder, data_path):
            self.invoker = invoker

        def run(self, question, main_round):
            raise AssertionError("The direct-final test must not invoke DataSubAgent.")

    class FakeMainAgent:
        def __init__(self, invoker, recorder):
            self.invoker = invoker

        def run(self, system_prompt, decision_event, ask_subagent):
            return (
                {
                    "action": "final_decision",
                    "reason": "Routine decision.",
                    "ordered_names": ["SCV"],
                },
                [{"action": "final_decision", "reason": "Routine decision.", "ordered_names": ["SCV"]}],
                [],
            )

    monkeypatch.setattr(knowledge_agent_module, "LLMInvoker", FakeInvoker)
    monkeypatch.setattr(knowledge_agent_module, "DataSubAgent", FakeSubAgent)
    monkeypatch.setattr(knowledge_agent_module, "MainAgent", FakeMainAgent)
    result = knowledge_agent_module.run_decision(
        system_prompt="system",
        decision_event="event",
        provider="main-api-key",
        subagent_provider="sub-api-key",
        log_dir=tmp_path,
    )
    assert [(item.agent_role, item.provider) for item in created] == [
        ("main_agent", "main-api-key"),
        ("data_subagent", "sub-api-key"),
    ]
    assert result["routing"]["knowledge_query_used"] is False
    assert result["subagent_sessions"] == []


def test_vendored_dataset_is_local_and_covers_all_macro_names():
    database_path = DEFAULT_DATABASE_PATH.resolve()
    assert PACKAGE_ROOT in database_path.parents
    store = get_dataset_store()
    all_units = {item["name"] for item in store.data["Unit"]}
    all_upgrades = {item["name"] for item in store.data["Upgrade"]}
    for race in ("terran", "protoss", "zerg"):
        assert set(race_unit_names(race)) <= all_units
        assert set(race_upgrade_names(race)) <= all_upgrades


def test_vendored_dataset_checksums_match_copy_manifest():
    manifest = json.loads((PACKAGE_ROOT / "COPY_MANIFEST.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["checksums"].items():
        digest = hashlib.sha256((PACKAGE_ROOT / relative).read_bytes()).hexdigest()
        assert digest == expected


def test_v22_model_view_hides_hashes_and_expands_short_reference():
    registry = ToolRegistry()
    raw = registry.execute(
        "query_relations",
        {"entity_name": "SMART", "relation": ["ability_requires_upgrade"], "direction": "forward"},
    )
    references = EvidenceReferenceMap()
    compacted, metrics = references.compact(raw)
    assert not _contains_opaque_key(compacted)
    assert compacted["results"][0]["evidence_ref"] == "R1"
    assert metrics["removed_field_count"] > 0
    expanded = registry.execute(
        "query_relation_evidence",
        {"evidence_ref": "R1"},
        evidence_references=references,
    )
    assert expanded["results"][0]["relation_id"]


def test_tool_catalog_dispatcher_and_native_schemas_are_in_sync():
    assert dispatcher_tool_names() == set(CATALOG)
    tool = ToolRegistry().openai_tools(["get_entity"])[0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "get_entity"
    assert tool["function"]["parameters"]["additionalProperties"] is False


def test_v22_prompts_and_context_are_ascii_english():
    for folder in (PACKAGE_ROOT / "prompts", PACKAGE_ROOT / "context"):
        for path in folder.glob("*.md"):
            path.read_text(encoding="utf-8").encode("ascii")
