from __future__ import annotations

import json

from SC2_Agent.data_tools import race_unit_names, race_upgrade_names
from SC2_Agent.knowledge_v2_2_v2.contracts import validate_main_decision
from SC2_Agent.knowledge_v2_2_v2.decision_prompt import build_knowledge_decision_context
from SC2_Agent.knowledge_v2_2_v2.main_agent import MAX_MAIN_ROUNDS, MainAgent
from SC2_Agent.knowledge_v2_2_v2.planner import (
    build_planning_snapshot,
    build_queue_audit,
    ledger_lookup,
    ledger_store,
    normalize_queue_constraints,
    stabilize_queue_constraints,
)
from SC2_Agent.knowledge_v2_2_v2.query.query_engine import (
    query_candidate_plan_facts,
    query_combat_capabilities,
    query_enemy_response_candidates,
    query_upgrade_candidates,
)
from SC2_Agent.knowledge_v2_2_v2.tool_registry import CATALOG, dispatcher_tool_names
from SC2_Agent.knowledge_v2_2_v2.trace import TraceRecorder
from dummies.generic.universal_llm_bot import (
    KNOWLEDGE_V22_DECISION_AGENT_MODE,
    KNOWLEDGE_V22_V2_DECISION_AGENT_MODE,
    NAIVE_DECISION_AGENT_MODE,
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

    def __call__(self, phase, messages, **kwargs):
        return {"content": next(self.replies)}


def observation():
    return {
        "time": 600.0,
        "economy": {
            "minerals": 900,
            "vespene": 200,
            "minerals_per_min": 900,
            "vespene_per_min": 240,
            "supply_used": 110,
            "supply_cap": 130,
            "supply_left": 20,
            "supply_workers": 55,
            "ideal_worker_count": 66,
        },
    }


def test_v2_is_an_additive_mode_and_does_not_replace_v1_or_naive():
    assert {NAIVE_DECISION_AGENT_MODE, KNOWLEDGE_V22_DECISION_AGENT_MODE} <= SUPPORTED_DECISION_AGENT_MODES
    assert KNOWLEDGE_V22_V2_DECISION_AGENT_MODE == "data-v2.2-v2"
    assert KNOWLEDGE_V22_V2_DECISION_AGENT_MODE in SUPPORTED_DECISION_AGENT_MODES


def test_planning_snapshot_projects_income_and_tracks_bank_delta():
    snapshot = build_planning_snapshot(
        observation(),
        horizon_seconds=60,
        previous={"game_time_seconds": 540, "minerals": 600, "gas": 250},
    )
    assert snapshot["projected_without_new_spending"] == {"minerals": 1800.0, "gas": 440.0}
    assert snapshot["bank_trend_since_previous_decision"]["minerals_delta"] == 300.0
    assert snapshot["bank_trend_since_previous_decision"]["gas_delta"] == -50.0
    assert snapshot["time_units"]["game_loops_per_second"] == 22.4


def test_v2_context_contains_planning_snapshot_and_optional_query_policy():
    context = build_knowledge_decision_context(
        race="terran",
        enemy_race="protoss",
        strategy_summary="Build a mech force.",
        obs_text="[Economy] 900 minerals, 200 gas. Supply 110/130.",
        observation_structured=observation(),
        unfinished_canonical_names=[],
        canonical_unit_names=race_unit_names("terran"),
        canonical_upgrade_names=race_upgrade_names("terran"),
        decision_interval_seconds=60,
        planner_state={},
        knowledge_ledger={"facts": {}},
    )
    assert "Explicit query triggers" in context["system_prompt"]
    assert "enemy_counter" in context["system_prompt"]
    assert "[Derived Planning Snapshot]" in context["decision_event"]
    assert '"minerals": 1800.0' in context["decision_event"]


def test_v2_contract_preserves_query_metadata_and_knowledge_application():
    ask = validate_main_decision({
        "action": "ask_subagent",
        "query_type": "enemy_counter",
        "targets": ["Mutalisk"],
        "requested_fields": ["counters", "minerals"],
        "sub_question": "Which Terran units counter Mutalisk?",
    })
    assert ask["query_type"] == "enemy_counter"
    final = validate_main_decision({
        "action": "final_decision",
        "reason": "Add verified anti-air.",
        "ordered_names": ["VikingFighter"],
        "knowledge_application": [{
            "fact": "VikingFighter can attack air.",
            "effect_on_queue": ["VikingFighter"],
        }],
    })
    assert final["knowledge_application"][0]["effect_on_queue"] == ["VikingFighter"]


def test_v2_mainagent_passes_structured_query_to_callback():
    invoker = ScriptedInvoker([
        json.dumps({
            "action": "ask_subagent",
            "query_type": "resource_facts",
            "targets": ["Battlecruiser"],
            "requested_fields": ["minerals", "gas", "time"],
            "sub_question": "What are Battlecruiser planning facts?",
        }),
        json.dumps({
            "action": "final_decision",
            "reason": "Use the verified technology route.",
            "ordered_names": ["FusionCore", "Battlecruiser"],
            "knowledge_application": [{
                "fact": "Battlecruiser requires FusionCore.",
                "effect_on_queue": ["FusionCore", "Battlecruiser"],
            }],
        }),
    ])
    received = []

    def ask(decision, main_round):
        received.append(decision)
        return {
            "session_id": "one",
            "main_round": main_round,
            "question": decision["sub_question"],
            "selected_tools": [],
            "reply": {"answer": "Verified.", "confidence": "high", "limitations": []},
            "observations": [],
        }

    decision, _, sessions = MainAgent(invoker, Recorder()).run("system", "event", ask)
    assert MAX_MAIN_ROUNDS == 5
    assert received[0]["query_type"] == "resource_facts"
    assert decision["ordered_names"] == ["FusionCore", "Battlecruiser"]
    assert len(sessions) == 1


def test_v2_final_round_is_still_deterministically_validated():
    invalid = json.dumps({
        "action": "final_decision",
        "reason": "Still invalid.",
        "ordered_names": ["SCV"],
    })
    valid = json.dumps({
        "action": "final_decision",
        "reason": "Converted resources to army.",
        "ordered_names": ["Marine"],
    })
    invoker = ScriptedInvoker([invalid] * MAX_MAIN_ROUNDS + [valid])

    def validate(decision):
        return {"worker_overproduction": 1} if decision["ordered_names"] == ["SCV"] else None

    decision, decisions, _ = MainAgent(invoker, Recorder()).run(
        "system", "event", lambda *_: None, validate
    )
    assert decision["ordered_names"] == ["Marine"]
    assert len(decisions) == MAX_MAIN_ROUNDS + 1


def test_match_ledger_reuses_exact_static_question():
    ledger = {"facts": {}}
    ledger_store(
        ledger,
        question="What does Battlecruiser cost?",
        query_type="resource_facts",
        targets=["Battlecruiser"],
        reply={"answer": "400 minerals and 300 gas", "confidence": "high"},
    )
    assert ledger_lookup(
        ledger,
        "wording may change",
        "resource_facts",
        ["Battlecruiser"],
    )["reply"]["confidence"] == "high"


def test_planning_tools_return_converted_and_directional_facts():
    facts = query_candidate_plan_facts(["Battlecruiser"], race="Terran")["results"][0]
    assert facts["time_loops"] == 1440
    assert facts["time_seconds"] == 64.29
    counters = query_enemy_response_candidates(["Mutalisk"], "Terran", limit=10)["results"]
    assert counters
    assert all(row["relation_direction"].endswith("counters Mutalisk") for row in counters)
    assert all(row["race"] == "Terran" for row in counters)
    assert all(row["can_directly_attack_target_layer"] for row in counters)
    capabilities = query_combat_capabilities(
        ["Roach", "Hydralisk"], enemy_names=["Battlecruiser"], race="Zerg"
    )["results"]
    assert capabilities[0]["can_attack_air"] is False
    assert capabilities[0]["engagement"][0]["can_directly_attack"] is False
    assert capabilities[1]["can_attack_air"] is True
    upgrades = query_upgrade_candidates(["Marine", "Marauder"], "Terran", limit=20)["results"]
    assert upgrades
    assert any("Marine" in row["affected_named_units"] for row in upgrades)


def test_queue_audit_reports_budget_and_supply_projection():
    snapshot = build_planning_snapshot(observation(), horizon_seconds=60)
    audit = build_queue_audit(["SupplyDepot", "Marine", "Marine", "Stimpack"], snapshot)
    assert audit["planned_cost"]["minerals"] > 0
    assert audit["supply_projection"]["providers_planned"] == 1
    assert audit["unknown_names"] == []


def test_queue_audit_detects_missing_tech_and_redundant_supply():
    obs = observation()
    obs["own_forces"] = {
        "completed": {"PROBE": 55, "NEXUS": 3},
        "under_construction": {},
        "workers_en_route": {},
        "active_queues": {},
    }
    snapshot = build_planning_snapshot(obs, horizon_seconds=60)
    bad = build_queue_audit(["Pylon", "CyberneticsCore"], snapshot)
    assert bad["prerequisite_violations"][0]["missing_before_item"] == ["Gateway"]
    assert bad["supply_projection"]["overbuild_warning"] is True
    good = build_queue_audit(["Pylon", "Gateway", "CyberneticsCore"], snapshot)
    assert good["prerequisite_violations"] == []


def test_v2_snapshot_and_audit_enforce_resource_to_strength_conversion():
    obs = observation()
    obs["economy"].update({
        "minerals": 4000,
        "vespene": 100,
        "supply_workers": 70,
        "ideal_worker_count": 66,
        "supply_army": 40,
    })
    obs["combat"] = {
        "army_advantage": "ClearDisadvantage",
        "advantage_predicted": "OverwhelmingDisadvantage",
        "our_army_power": 20,
        "enemy_army_power": 60,
    }
    obs["own_forces"] = {
        "completed": {"SCV": 70, "COMMANDCENTER": 2, "REFINERY": 1, "BARRACKS": 2},
        "under_construction": {},
        "workers_en_route": {},
        "active_queues": {},
    }
    snapshot = build_planning_snapshot(obs, horizon_seconds=60, race="terran")
    assert snapshot["combat_state"]["power_ratio"] == 0.333
    assert snapshot["resource_conversion_targets"]["worker_additions_allowed"] == 0
    assert snapshot["resource_conversion_targets"]["gas_capacity_gap"] is True
    weak = build_queue_audit(["SCV", "CommandCenter"], snapshot)
    validation = weak["resource_and_strength_conversion"]["validation"]
    assert validation["worker_overproduction"] == 1
    assert validation["mineral_commitment_shortfall"] > 0
    assert validation["strength_investment_shortfall"] > 0
    assert validation["mobile_strength_investment_shortfall"] > 0
    assert validation["gas_capacity_gap_unaddressed"] is True


def test_queue_audit_caps_queue_and_requires_mobile_layer_response():
    obs = observation()
    obs["own_forces"] = {
        "completed": {"DRONE": 60, "HATCHERY": 3, "SPAWNINGPOOL": 1},
        "under_construction": {}, "workers_en_route": {}, "active_queues": {},
    }
    obs["enemy"] = {"composition": {"BANSHEE": 6}}
    snapshot = build_planning_snapshot(obs, horizon_seconds=60, race="zerg")
    audit = build_queue_audit(["SporeCrawler"] * 21, snapshot)
    validation = audit["resource_and_strength_conversion"]["validation"]
    assert validation["queue_length_overflow"] == 1
    assert validation["mobile_anti_air_response_shortfall"] > 0


def test_zerg_larva_is_not_treated_as_a_technology_prerequisite():
    obs = observation()
    obs["own_forces"] = {
        "completed": {"DRONE": 50, "HATCHERY": 3, "HYDRALISKDEN": 1},
        "under_construction": {}, "workers_en_route": {}, "active_queues": {},
    }
    snapshot = build_planning_snapshot(obs, horizon_seconds=60, race="zerg")
    audit = build_queue_audit(["Hydralisk"], snapshot)
    assert audit["prerequisite_violations"] == []


def test_queue_normalization_removes_safe_mechanical_excesses():
    obs = observation()
    obs["economy"].update({
        "minerals": 4000, "vespene": 100, "supply_left": 60,
        "supply_used": 100, "supply_cap": 160, "supply_workers": 70,
        "ideal_worker_count": 66,
    })
    obs["own_forces"] = {
        "completed": {"SCV": 70, "COMMANDCENTER": 2, "BARRACKS": 3},
        "under_construction": {}, "workers_en_route": {}, "active_queues": {},
    }
    snapshot = build_planning_snapshot(obs, horizon_seconds=60, race="terran")
    names, corrections = normalize_queue_constraints(
        ["SCV", "SupplyDepot"] + ["Marine"] * 22, snapshot
    )
    assert "SCV" not in names
    assert "SupplyDepot" not in names
    assert len(names) == 20
    assert {item["type"] for item in corrections} >= {
        "remove_excess_workers", "remove_redundant_supply", "truncate_queue"
    }


def test_attack_layer_profile_keeps_supply_units_even_when_weapon_data_is_missing():
    obs = observation()
    obs["own_forces"] = {
        "completed": {"ROACH": 8, "HATCHERY": 2, "DRONE": 40},
        "under_construction": {}, "workers_en_route": {}, "active_queues": {},
    }
    obs["enemy"] = {"composition": {"BATTLECRUISER": 4}}
    snapshot = build_planning_snapshot(obs, horizon_seconds=60, race="zerg")
    profile = snapshot["attack_layer_profile"]
    assert "Battlecruiser" in profile["enemy"]["air_combat_units"]
    assert profile["air_attack_gap"] is True


def test_v2_tool_catalog_and_dispatch_are_in_sync():
    assert dispatcher_tool_names() == set(CATALOG)
    assert {
        "query_candidate_plan_facts",
        "query_enemy_response_candidates",
        "query_combat_capabilities",
        "query_upgrade_candidates",
    } <= set(CATALOG)


def test_v2_trace_uses_compact_run_id_for_long_windows_match_paths(tmp_path):
    root = tmp_path
    while len(str(root.resolve())) < 204:
        root = root / "x"
    recorder = TraceRecorder("long path regression", log_dir=root)
    assert len(recorder.run_id) == 19
    assert len(str(recorder.events_path)) < 260 or not str(recorder.events_path).startswith("C:\\")
    assert recorder.finalize({"ok": True}, "completed").is_file()


def test_task_harness_throttles_workers_when_enemy_exists_and_army_is_zero():
    obs = observation()
    obs["economy"].update({
        "minerals": 700,
        "supply_workers": 23,
        "ideal_worker_count": 35,
        "supply_army": 0,
    })
    obs["combat"] = {
        "army_advantage": "SlightDisadvantage",
        "advantage_predicted": "SlightDisadvantage",
        "our_army_power": 0,
        "enemy_army_power": 2,
    }
    obs["own_forces"] = {
        "completed": {
            "SCV": 23, "COMMANDCENTER": 2, "SUPPLYDEPOT": 2,
            "BARRACKS": 1, "FACTORY": 1,
        },
        "under_construction": {}, "workers_en_route": {}, "active_queues": {},
    }
    snapshot = build_planning_snapshot(obs, horizon_seconds=60, race="terran")
    assert snapshot["task_decomposition"]["operational_mode"] == "survival"
    assert snapshot["resource_conversion_targets"]["worker_additions_allowed"] <= 2
    names, _ = stabilize_queue_constraints(
        ["SCV"] * 12 + ["Marine"] * 5, snapshot
    )
    assert names.count("SCV") <= 2
    assert names.count("Marine") >= 5


def test_task_harness_adds_real_production_before_filling_a_large_bank():
    obs = observation()
    obs["economy"].update({
        "minerals": 6000,
        "vespene": 100,
        "minerals_per_min": 1200,
        "supply_left": 60,
        "supply_workers": 48,
        "ideal_worker_count": 44,
        "supply_army": 20,
    })
    obs["combat"] = {
        "army_advantage": "Even", "advantage_predicted": "Even",
        "our_army_power": 20, "enemy_army_power": 20,
    }
    obs["own_forces"] = {
        "completed": {
            "PROBE": 48, "NEXUS": 2, "PYLON": 8,
            "GATEWAY": 2, "CYBERNETICSCORE": 1,
        },
        "under_construction": {}, "workers_en_route": {}, "active_queues": {},
    }
    snapshot = build_planning_snapshot(obs, horizon_seconds=60, race="protoss")
    assert snapshot["task_decomposition"]["production_capacity"]["capacity_gap"] is True
    names, corrections = stabilize_queue_constraints(["Zealot", "Zealot"], snapshot)
    assert names.count("Gateway") >= 1
    assert names.count("Zealot") > 2
    assert "add_production_capacity" in {item["type"] for item in corrections}
    audit = build_queue_audit(names, snapshot)
    assert audit["unknown_names"] == []
    assert audit["prerequisite_violations"] == []
    assert not any(audit["budget_overrun"].values())


def test_task_harness_breaks_zerg_gas_trim_commitment_deadlock():
    obs = observation()
    obs["economy"].update({
        "minerals": 11000,
        "vespene": 360,
        "minerals_per_min": 1500,
        "vespene_per_min": 300,
        "supply_used": 120,
        "supply_cap": 180,
        "supply_left": 60,
        "supply_workers": 60,
        "ideal_worker_count": 55,
        "supply_army": 60,
    })
    obs["combat"] = {
        "army_advantage": "Even", "advantage_predicted": "Even",
        "our_army_power": 80, "enemy_army_power": 80,
    }
    obs["own_forces"] = {
        "completed": {
            "DRONE": 60, "HATCHERY": 3, "SPAWNINGPOOL": 1,
            "LAIR": 1, "HYDRALISKDEN": 1, "LURKERDENMP": 1,
        },
        "under_construction": {}, "workers_en_route": {}, "active_queues": {},
    }
    snapshot = build_planning_snapshot(obs, horizon_seconds=60, race="zerg")
    initial = ["LurkerMP"] * 4 + ["Hydralisk"] * 8 + ["Roach"] * 8
    names, corrections = stabilize_queue_constraints(initial, snapshot)
    assert len(names) <= 20
    assert any(item["type"] == "trim_gas_overrun" for item in corrections)
    assert any(name in {"Zergling", "Queen"} for name in names)
    audit = build_queue_audit(names, snapshot)
    assert audit["unknown_names"] == []
    assert audit["prerequisite_violations"] == []
    assert not any(audit["budget_overrun"].values())
