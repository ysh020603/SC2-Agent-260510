from __future__ import annotations

import json

import pytest

from SC2_Agent.knowledge_v2_3.knowledge_router import PortableKnowledgeRouter
from SC2_Agent.knowledge_v2_3.main_agent import MainAgent
from SC2_Agent.knowledge_v2_3.planner import (
    build_planning_snapshot,
    stabilize_queue_constraints,
)
from SC2_Agent.knowledge_v2_3.query.search_tools import DEFAULT_DATA_PATH
from SC2_Agent.knowledge_v2_3.query.query_engine import query_upgrade_candidates
from SC2_Agent.knowledge_v2_3.runtime import LLMInvoker
from SC2_Agent.knowledge_v2_3.sub_agent import DataSubAgent
from SC2_Agent.knowledge_v2_3.tool_registry import ToolRegistry
from dummies.generic.universal_llm_bot import (
    KNOWLEDGE_V23_DECISION_AGENT_MODE,
    SUPPORTED_DECISION_AGENT_MODES,
)


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
        self.calls.append((phase, messages, kwargs))
        return {"content": next(self.replies)}


def snapshot():
    return {
        "race": "terran",
        "horizon_seconds": 60,
        "current": {"minerals": 100, "gas": 0},
        "projected_without_new_spending": {"minerals": 900, "gas": 0},
        "committed_and_available_assets": {"completed": {"Barracks": 4}},
        "task_decomposition": {
            "fallback_units": {
                "anti_ground": ["Marine", "Hellion"],
                "anti_air": ["Marine"],
                "mineral_sink": ["Marine"],
            }
        },
    }


def test_v2_3_is_additive():
    assert KNOWLEDGE_V23_DECISION_AGENT_MODE == "data-v2.3"
    assert KNOWLEDGE_V23_DECISION_AGENT_MODE in SUPPORTED_DECISION_AGENT_MODES


def test_portable_router_executes_repository_tools_without_api_tool_calls():
    recorder = Recorder()
    packet, observations, tools = PortableKnowledgeRouter(
        ToolRegistry(),
        recorder,
        data_path=DEFAULT_DATA_PATH,
        planning_snapshot=snapshot(),
    ).run({
        "query_type": "enemy_counter",
        "targets": ["Zergling"],
        "requested_fields": ["cost", "producer", "target_layer"],
    }, "portable")

    assert packet["status"] == "success"
    assert packet["recommended_shortlist"][0] == "Marine"
    assert packet["feasible_candidates"][0]["mobile_combat"] is True
    assert packet["feasible_candidates"][0]["immediately_executable"] is True
    assert tools == ["query_composition_response_matrix"]
    assert observations and not observations[0].get("error")
    assert any(event == "tool_response" for event, _ in recorder.events)


def test_router_distinguishes_zerg_ready_and_horizon_reachable_production():
    zerg_snapshot = {
        "race": "zerg",
        "horizon_seconds": 60,
        "current": {"minerals": 700, "gas": 200},
        "projected_without_new_spending": {"minerals": 1400, "gas": 400},
        "committed_and_available_assets": {
            "completed": {"Hatchery": 2, "SpawningPool": 1, "Drone": 30},
            "under_construction": {"RoachWarren": 1},
        },
        "task_decomposition": {
            "fallback_units": {
                "anti_ground": ["Zergling", "Roach"],
                "anti_air": ["Hydralisk"],
                "mineral_sink": ["Zergling"],
            },
            "combat_emergency": False,
        },
    }
    packet, _, _ = PortableKnowledgeRouter(
        ToolRegistry(),
        Recorder(),
        data_path=DEFAULT_DATA_PATH,
        planning_snapshot=zerg_snapshot,
    ).run({
        "query_type": "enemy_counter",
        "targets": ["Zealot", "Stalker"],
    }, "zerg-portable")

    rows = {item["name"]: item for item in packet["feasible_candidates"]}
    assert rows["Roach"]["producer_ready"] is False
    assert rows["Roach"]["producer_reachable_in_horizon"] is True
    assert "Roach" in packet["horizon_mobile_shortlist"]
    assert packet["decision_guidance"]["actionable"] is True


def test_upgrade_query_rejects_broad_race_ontology_false_positive():
    result = query_upgrade_candidates(
        ["Marine", "SiegeTank"],
        "terran",
        data_path=DEFAULT_DATA_PATH,
    )
    rows = {item["name"]: item for item in result["results"]}

    assert rows["TerranInfantryWeaponsLevel1"]["affected_named_units"] == ["Marine"]
    assert result["rejected_broad_expansions"] > 0


def test_upgrade_router_does_not_recommend_completed_level_again():
    upgrade_snapshot = snapshot()
    upgrade_snapshot["current"] = {"minerals": 800, "gas": 500}
    upgrade_snapshot["projected_without_new_spending"] = {
        "minerals": 1600,
        "gas": 900,
    }
    upgrade_snapshot["committed_and_available_assets"]["completed"].update({
        "EngineeringBay": 1,
        "Armory": 1,
    })
    upgrade_snapshot["completed_upgrades"] = ["TerranInfantryWeaponsLevel1"]
    packet, _, _ = PortableKnowledgeRouter(
        ToolRegistry(),
        Recorder(),
        data_path=DEFAULT_DATA_PATH,
        planning_snapshot=upgrade_snapshot,
    ).run({
        "query_type": "upgrade_path",
        "targets": ["Marine"],
    }, "upgrade-portable")

    names = [item["name"] for item in packet["feasible_candidates"]]
    assert "TerranInfantryWeaponsLevel1" not in names
    assert "TerranInfantryWeaponsLevel2" in names


def test_verified_mobile_knowledge_can_fill_a_real_layer_gap():
    planning = build_planning_snapshot({
        "economy": {
            "minerals": 1800,
            "vespene": 800,
            "minerals_per_min": 1800,
            "vespene_per_min": 600,
            "supply_used": 70,
            "supply_cap": 120,
            "supply_workers": 45,
            "supply_army": 25,
            "ideal_worker_count": 50,
        },
        "own_forces": {
            "completed": {
                "Hatchery": 3,
                "Drone": 45,
                "SpawningPool": 1,
                "Lair": 1,
                "HydraliskDen": 1,
                "Hydralisk": 4,
            },
            "under_construction": {},
            "active_queues": {},
            "workers_en_route": {},
        },
        "enemy": {"composition": {"Mutalisk": 10}},
        "combat": {
            "army_advantage": "ClearDisadvantage",
            "advantage_predicted": "ClearDisadvantage",
            "income_advantage": "Advantage",
            "our_army_power": 40,
            "enemy_army_power": 80,
            "enemy_air": "Air",
        },
        "upgrades": [],
    }, horizon_seconds=60, race="zerg")

    names, corrections = stabilize_queue_constraints(
        [],
        planning,
        knowledge_preferences=["Hydralisk"],
    )

    assert names.count("Hydralisk") >= 4
    verified = [
        item for item in corrections
        if item["type"] == "fill_verified_knowledge_response"
    ]
    assert len(verified) >= 4


def test_combat_capability_prefers_unit_covering_air_and_ground_gap():
    protoss_snapshot = {
        "race": "protoss",
        "horizon_seconds": 60,
        "current": {"minerals": 900, "gas": 500},
        "projected_without_new_spending": {"minerals": 1800, "gas": 900},
        "committed_and_available_assets": {
            "completed": {
                "Nexus": 2,
                "Gateway": 5,
                "CyberneticsCore": 1,
                "Zealot": 8,
                "Stalker": 4,
            },
        },
        "attack_layer_profile": {
            "air_attack_gap": True,
            "ground_attack_gap": False,
            "own": {
                "air_combat_units": [],
                "ground_combat_units": ["Zealot", "Stalker"],
            },
        },
        "task_decomposition": {
            "fallback_units": {
                "anti_air": ["Stalker"],
                "anti_ground": ["Zealot", "Stalker"],
                "mineral_sink": ["Zealot"],
            },
            "combat_emergency": True,
        },
    }
    packet, _, tools = PortableKnowledgeRouter(
        ToolRegistry(),
        Recorder(),
        data_path=DEFAULT_DATA_PATH,
        planning_snapshot=protoss_snapshot,
    ).run({
        "query_type": "combat_capability",
        "targets": ["Raven", "Marine", "SiegeTank"],
    }, "air-gap")

    assert packet["immediate_mobile_shortlist"][0] == "Stalker"
    stalker = next(
        item for item in packet["feasible_candidates"] if item["name"] == "Stalker"
    )
    zealot = next(
        item for item in packet["feasible_candidates"] if item["name"] == "Zealot"
    )
    assert stalker["covers_all_requested_targets"] is True
    assert zealot["covers_all_requested_targets"] is False
    assert tools == [
        "query_composition_response_matrix",
        "query_combat_production_options",
        "query_combat_capabilities",
        "query_candidate_plan_facts",
    ]


def test_verified_layer_portfolio_is_exposed_and_promoted_ahead_of_generic_tail():
    planning = build_planning_snapshot({
        "economy": {
            "minerals": 1400,
            "vespene": 700,
            "minerals_per_min": 1300,
            "vespene_per_min": 450,
            "supply_used": 60,
            "supply_cap": 120,
            "supply_workers": 40,
            "supply_army": 20,
            "ideal_worker_count": 44,
        },
        "own_forces": {
            "completed": {
                "Nexus": 2,
                "Probe": 40,
                "Gateway": 4,
                "CyberneticsCore": 1,
                "Zealot": 8,
            },
            "under_construction": {},
            "active_queues": {},
            "workers_en_route": {},
        },
        "enemy": {"composition": {"Raven": 2, "Marine": 8}},
        "combat": {
            "army_advantage": "ClearDisadvantage",
            "advantage_predicted": "ClearDisadvantage",
            "our_army_power": 20,
            "enemy_army_power": 38,
            "enemy_air": "Mixed",
        },
        "upgrades": [],
    }, horizon_seconds=60, race="protoss")

    packet, _, _ = PortableKnowledgeRouter(
        ToolRegistry(),
        Recorder(),
        data_path=DEFAULT_DATA_PATH,
        planning_snapshot=planning,
    ).run({
        "query_type": "combat_capability",
        "targets": ["Raven", "Marine"],
    }, "portfolio")
    by_layer = packet["decision_guidance"]["preferred_mobile_by_layer"]
    assert by_layer["air"]
    assert by_layer["ground"]

    names, corrections = stabilize_queue_constraints(
        ["Zealot", "Zealot", "Zealot", "Stalker"],
        planning,
        knowledge_preferences=packet["decision_guidance"]["preferred_mobile_now"],
        knowledge_preferences_by_layer=by_layer,
    )
    assert names[0] == by_layer["air"][0]
    assert any(
        item["type"] in {
            "promote_verified_layer_response",
            "insert_verified_layer_response",
        }
        for item in corrections
    )


def test_gas_overflow_still_requires_mobile_strength_conversion():
    planning = build_planning_snapshot({
        "economy": {
            "minerals": 890,
            "vespene": 1788,
            "minerals_per_min": 1890,
            "vespene_per_min": 509,
            "supply_used": 78,
            "supply_cap": 150,
            "supply_workers": 43,
            "supply_army": 35,
            "ideal_worker_count": 50,
        },
        "own_forces": {
            "completed": {
                "CommandCenter": 3,
                "SCV": 43,
                "Barracks": 4,
                "EngineeringBay": 1,
                "Marine": 20,
            },
            "under_construction": {},
            "active_queues": {},
            "workers_en_route": {},
        },
        "enemy": {"composition": {}},
        "combat": {
            "army_advantage": "OverwhelmingAdvantage",
            "advantage_predicted": "OverwhelmingAdvantage",
            "our_army_power": 35,
            "enemy_army_power": 2,
        },
        "upgrades": [],
    }, horizon_seconds=60, race="terran")

    names, corrections = stabilize_queue_constraints(
        ["TerranInfantryWeaponsLevel1"],
        planning,
    )

    assert planning["task_decomposition"]["gas_overflow"] is True
    assert names.count("Marine") >= 2
    assert any(
        item["type"] == "fill_executable_mobile_capacity"
        for item in corrections
    )


def test_v2_3_invoker_rejects_provider_native_tools_before_calling_api():
    invoker = LLMInvoker(Recorder(), "unused", None)
    with pytest.raises(ValueError, match="never sends provider-native tools"):
        invoker("phase", [], tools=[{"function": {"name": "x"}}])


def test_data_subagent_uses_one_ordinary_text_completion():
    invoker = ScriptedInvoker([json.dumps({
        "answer": "Marine is the best ready response.",
        "confidence": "high",
        "entities_mentioned": ["Marine"],
        "candidate_entities": [],
        "evidence_summary": "Repository packet ranks Marine first.",
        "limitations": "No additional limitation.",
    })])
    recorder = Recorder()
    session = DataSubAgent(
        invoker,
        recorder,
        planning_snapshot=snapshot(),
    ).run({
        "query_type": "enemy_counter",
        "targets": ["Zergling"],
        "requested_fields": ["cost"],
        "sub_question": "What counters Zergling now?",
    }, 1)

    assert session["status"] == "success"
    assert session["protocol"] == "portable_text_v1"
    assert session["reply"]["limitations"] == ["No additional limitation."]
    assert session["observations"]
    assert len(invoker.calls) == 1
    assert invoker.calls[0][2].get("tools") is None


def test_mainagent_continues_when_repository_query_raises():
    invoker = ScriptedInvoker([
        json.dumps({
            "action": "ask_subagent",
            "query_type": "enemy_counter",
            "targets": ["Zergling"],
            "requested_fields": ["cost"],
            "sub_question": "What counters Zergling?",
        }),
        json.dumps({
            "action": "final_decision",
            "reason": "Continue immediate production despite unavailable knowledge.",
            "ordered_names": ["Marine", "Marine"],
        }),
    ])

    def fail(*_):
        raise RuntimeError("repository unavailable")

    decision, _, sessions = MainAgent(invoker, Recorder()).run("system", "event", fail)
    assert decision["ordered_names"] == ["Marine", "Marine"]
    assert sessions[0]["status"] == "unavailable"
