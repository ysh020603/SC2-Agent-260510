"""Run three bounded V2 probes for resource conversion and air/ground gaps."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from API_Tools.llm_caller import call_openai_detailed
from SC2_Agent.data_tools import race_prompt_context, race_unit_names, race_upgrade_names
from SC2_Agent.decision_agent import build_decision_messages, parse_decision_response
from SC2_Agent.knowledge_v2_2 import (
    build_knowledge_decision_context as build_v1_decision_context,
    run_decision as run_v1_decision,
)
from SC2_Agent.knowledge_v2_2_v2 import build_knowledge_decision_context, run_decision
from SC2_Agent.knowledge_v2_2_v2_no_knowledge import (
    run_decision as run_no_knowledge_decision,
)
from SC2_Agent.knowledge_v2_2_v2.planner import build_queue_audit
from SC2_Agent.prompt_context import StrategyAutomationProfile
from SC2_Agent.top_agent import parse_strategy_summary


SCENARIOS = {
    "terran": {
        "enemy_race": "protoss",
        "strategy": "yamato_rust_fleet",
        "economy": (5500, 180, 2600, 220, 120, 170, 68, 66, 52),
        "completed": {
            "SCV": 68, "COMMANDCENTER": 3, "REFINERY": 2, "BARRACKS": 4,
            "FACTORY": 3, "STARPORT": 2, "MARINE": 20, "SIEGETANK": 10,
        },
        "enemy": {"STALKER": 8, "IMMORTAL": 6, "ZEALOT": 8},
        "combat": ("ClearDisadvantage", "ClearDisadvantage", 80, 145, "NoAir"),
    },
    "protoss": {
        "enemy_race": "zerg",
        "strategy": "dark_templar_rush",
        "economy": (7000, 250, 2800, 250, 140, 190, 70, 66, 70),
        "completed": {
            "PROBE": 70, "NEXUS": 3, "ASSIMILATOR": 3, "GATEWAY": 6,
            "CYBERNETICSCORE": 1, "TWILIGHTCOUNCIL": 1, "DARKSHRINE": 1,
            "DARKTEMPLAR": 12, "ZEALOT": 14,
        },
        "enemy": {"MUTALISK": 10, "CORRUPTOR": 4, "ZERGLING": 12},
        "combat": ("OverwhelmingDisadvantage", "ClearDisadvantage", 65, 160, "Mixed"),
    },
    "zerg": {
        "enemy_race": "terran",
        "strategy": "lurkers",
        "economy": (8500, 200, 3400, 280, 155, 190, 90, 72, 65),
        "completed": {
            "DRONE": 90, "HATCHERY": 4, "EXTRACTOR": 4, "SPAWNINGPOOL": 1,
            "ROACHWARREN": 1, "HYDRALISKDEN": 1, "LURKERDENMP": 1,
            "ROACH": 20, "LURKERMP": 12,
        },
        "enemy": {"BATTLECRUISER": 5, "BANSHEE": 6, "LIBERATOR": 4},
        "combat": ("OverwhelmingDisadvantage", "OverwhelmingDisadvantage", 55, 180, "Air"),
    },
}


def run_probe(
    race: str,
    model_key: str,
    output_root: Path,
    decision_agent_mode: str = "data-v2.2-v2",
) -> dict:
    scenario = SCENARIOS[race]
    strategy = scenario["strategy"]
    strategy_dir = ROOT / "SKILL" / race / strategy
    summary = parse_strategy_summary((strategy_dir / "Top_agent.md").read_text(encoding="utf-8"))
    module = importlib.import_module(f"SKILL.{race}.{strategy}.strategy_tools")
    profile = getattr(module, "AUTOMATION_PROFILE")
    if not isinstance(profile, StrategyAutomationProfile):
        raise ValueError(f"Missing automation profile for {race}/{strategy}")
    m, g, mpm, gpm, used, cap, workers, ideal, army = scenario["economy"]
    army_advantage, predicted, own_power, enemy_power, enemy_air = scenario["combat"]
    observation = {
        "time": 720.0,
        "economy": {
            "minerals": m, "vespene": g, "minerals_per_min": mpm,
            "vespene_per_min": gpm, "supply_used": used, "supply_cap": cap,
            "supply_left": cap - used, "supply_workers": workers,
            "ideal_worker_count": ideal, "supply_army": army,
        },
        "own_forces": {
            "completed": scenario["completed"], "under_construction": {},
            "workers_en_route": {}, "active_queues": {},
        },
        "enemy": {
            "composition": scenario["enemy"], "last_observation_time": 720.0,
            "seconds_since_last_seen": 0.0,
        },
        "combat": {
            "army_advantage": army_advantage, "advantage_predicted": predicted,
            "income_advantage": "OverwhelmingAdvantage", "our_army_power": own_power,
            "enemy_army_power": enemy_power, "enemy_air": enemy_air,
        },
        "memory_flags": {"enemy_cloak_threat": "BANSHEE" in scenario["enemy"]},
    }
    obs_text = (
        f"[Time] 12:00 (720.0s).\n[Economy] {m} minerals, {g} vespene; "
        f"income {mpm} mins/min, {gpm} gas/min. Supply: {used}/{cap} "
        f"(workers {workers}/{ideal} current/ideal, army {army}).\n"
        f"[Own Forces & Infrastructure]\n  Completed: {scenario['completed']}.\n"
        f"  Under Construction: none.\n  Workers En Route: none.\n  Active Queues: none.\n"
        f"[Enemy Intelligence] {scenario['enemy']}.\n"
        f"[Combat Analysis] army advantage = {army_advantage}, income advantage = "
        f"OverwhelmingAdvantage, predicted = {predicted}. Power: {own_power} vs {enemy_power}.\n"
        f"[Threat Flags] {'enemy cloak threat' if observation['memory_flags']['enemy_cloak_threat'] else 'none'}."
    )
    ledger = {"facts": {}}
    planner_state = {}
    prompt_arguments = dict(
        race=race,
        enemy_race=scenario["enemy_race"],
        strategy_summary=summary,
        strategy_automation_context=profile.render(),
        obs_text=obs_text,
        unfinished_canonical_names=[],
        canonical_unit_names=race_unit_names(race),
        canonical_upgrade_names=race_upgrade_names(race),
        race_context=race_prompt_context(race),
        decision_cycle=12,
        trigger_reason="directed_resource_combat_probe",
        game_time_seconds=720.0,
        decision_interval_seconds=60.0,
    )
    context = build_knowledge_decision_context(
        **prompt_arguments,
        observation_structured=observation,
        planner_state=planner_state,
        knowledge_ledger=ledger,
    )
    if decision_agent_mode in {"data-v2.2-v2", "data-v2.2-v2-no-knowledge"}:
        selected_run_decision = (
            run_no_knowledge_decision
            if decision_agent_mode == "data-v2.2-v2-no-knowledge"
            else run_decision
        )
        result = selected_run_decision(
            system_prompt=context["system_prompt"],
            decision_event=context["decision_event"],
            provider=model_key,
            subagent_provider=model_key,
            enable_reasoning=False,
            log_dir=output_root / race,
            decision_metadata=context["metadata"],
            planning_snapshot=context["planning_snapshot"],
            planner_state=planner_state,
            knowledge_ledger=ledger,
        )
        decision = result["decision"]
        sessions = result["subagent_sessions"]
        trace_path = result["log_path"]
        main_round_count = len(result["main_decisions"])
    elif decision_agent_mode == "data-v2.2":
        v1_context = build_v1_decision_context(**prompt_arguments)
        result = run_v1_decision(
            system_prompt=v1_context["system_prompt"],
            decision_event=v1_context["decision_event"],
            provider=model_key,
            subagent_provider=model_key,
            enable_reasoning=False,
            log_dir=output_root / race,
            decision_metadata=v1_context["metadata"],
        )
        decision = result["decision"]
        sessions = result["subagent_sessions"]
        trace_path = result["log_path"]
        main_round_count = len(result["main_decisions"])
    else:
        messages = build_decision_messages(**prompt_arguments)
        raw = call_openai_detailed(
            messages=messages, model_key=model_key, is_reasoning=False
        )
        if raw.get("error"):
            raise RuntimeError(raw["error"])
        parsed = parse_decision_response(str(raw.get("content") or ""))
        if parsed is None:
            raise RuntimeError("Naive decision response did not match the JSON contract.")
        decision = {"reason": parsed.reason, "ordered_names": parsed.ordered_names}
        sessions = []
        trace_path = None
        main_round_count = 1

    queue_audit = build_queue_audit(
        list(decision.get("ordered_names") or []), context["planning_snapshot"]
    )
    validation = queue_audit["resource_and_strength_conversion"]["validation"]
    return {
        "race": race,
        "strategy": strategy,
        "decision_agent_mode": decision_agent_mode,
        "decision": decision,
        "main_round_count": main_round_count,
        "query_types": [session.get("query_type") for session in sessions],
        "selected_tools": [session.get("selected_tools") for session in sessions],
        "planning_targets": context["planning_snapshot"]["resource_conversion_targets"],
        "task_decomposition": context["planning_snapshot"]["task_decomposition"],
        "attack_layer_profile": context["planning_snapshot"]["attack_layer_profile"],
        "queue_audit": queue_audit,
        "queue_conversion": queue_audit["resource_and_strength_conversion"],
        "remaining_validation": validation,
        "trace_path": trace_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-key", default="DeepSeek-V4-flash")
    parser.add_argument(
        "--decision-agent-mode",
        choices=("data-v2.2-v2-no-knowledge", "data-v2.2-v2", "data-v2.2", "naive"),
        default="data-v2.2-v2",
    )
    parser.add_argument("--output-root", default="")
    parser.add_argument("--races", nargs="+", choices=tuple(SCENARIOS), default=list(SCENARIOS))
    args = parser.parse_args()
    output_root = Path(args.output_root) if args.output_root else (
        ROOT / "game_records" / "prompt_probes"
        / f"resource_combat_{args.decision_agent_mode}_{datetime.now():%Y%m%d_%H%M%S}"
    )
    output_root.mkdir(parents=True, exist_ok=True)
    rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                run_probe, race, args.model_key, output_root, args.decision_agent_mode
            ): race
            for race in args.races
        }
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    rows.sort(key=lambda row: row["race"])
    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
