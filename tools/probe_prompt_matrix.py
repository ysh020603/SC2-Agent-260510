"""Probe the current macro prompt for all enabled strategies without launching SC2."""

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
from SC2_Agent.data_tools import (
    action_candidates_for_entity,
    canonical_race_entity_name,
    race_prompt_context,
    race_unit_names,
    race_upgrade_names,
)
from SC2_Agent.decision_agent import build_decision_messages, parse_decision_response
from SC2_Agent.knowledge_v2_2 import build_knowledge_decision_context, run_decision
from SC2_Agent.prompt_context import StrategyAutomationProfile
from SC2_Agent.strategy_registry import enabled_strategy_names
from SC2_Agent.top_agent import parse_strategy_summary


INITIAL_OBSERVATION = {
    "terran": (
        "[Time] 00:00 (0.0s).\n"
        "[Economy] 50 minerals, 0 vespene; income 720 mins/min, 0 gas/min. "
        "Supply: 12/15 (workers 12/16 current/ideal, army 0).\n"
        "[Own Forces & Infrastructure]\n  Completed: 12 SCV, 1 COMMANDCENTER.\n"
        "  Under Construction: none.\n  Workers En Route: none.\n"
        "  Active Queues: none.\n[Enemy Intelligence] nothing scouted yet.\n"
        "[Combat Analysis] army advantage = Even. Power: 0 vs 0."
    ),
    "protoss": (
        "[Time] 00:00 (0.0s).\n"
        "[Economy] 50 minerals, 0 vespene; income 720 mins/min, 0 gas/min. "
        "Supply: 12/15 (workers 12/16 current/ideal, army 0).\n"
        "[Own Forces & Infrastructure]\n  Completed: 12 PROBE, 1 NEXUS.\n"
        "  Under Construction: none.\n  Workers En Route: none.\n"
        "  Active Queues: none.\n[Enemy Intelligence] nothing scouted yet.\n"
        "[Combat Analysis] army advantage = Even. Power: 0 vs 0."
    ),
    "zerg": (
        "[Time] 00:00 (0.0s).\n"
        "[Economy] 50 minerals, 0 vespene; income 720 mins/min, 0 gas/min. "
        "Supply: 12/14 (workers 12/16 current/ideal, army 0).\n"
        "[Own Forces & Infrastructure]\n"
        "  Completed: 12 DRONE, 1 HATCHERY, 1 OVERLORD; Larva: 3.\n"
        "  Under Construction: none.\n  Workers En Route: none.\n"
        "  Active Queues: none.\n[Enemy Intelligence] nothing scouted yet.\n"
        "[Combat Analysis] army advantage = Even. Power: 0 vs 0."
    ),
}


def _probe_one(
    model: str,
    subagent_model: str,
    decision_agent_mode: str,
    enemy_race: str,
    race: str,
    strategy: str,
) -> dict:
    strategy_dir = ROOT / "SKILL" / race / strategy
    summary = parse_strategy_summary(
        (strategy_dir / "Top_agent.md").read_text(encoding="utf-8")
    )
    module = importlib.import_module(f"SKILL.{race}.{strategy}.strategy_tools")
    profile = getattr(module, "AUTOMATION_PROFILE", None)
    if not isinstance(profile, StrategyAutomationProfile):
        raise ValueError(f"Missing automation profile for {race}/{strategy}")
    prompt_arguments = dict(
        race=race,
        enemy_race=enemy_race,
        strategy_summary=summary,
        strategy_automation_context=profile.render(),
        obs_text=INITIAL_OBSERVATION[race],
        unfinished_canonical_names=[],
        canonical_unit_names=race_unit_names(race),
        canonical_upgrade_names=race_upgrade_names(race),
        race_context=race_prompt_context(race),
        decision_cycle=1,
        trigger_reason="initial_decision",
        game_time_seconds=0,
        decision_interval_seconds=60,
    )
    knowledge_result = None
    if decision_agent_mode in {
        "data-v2.2",
        "data-v2.2-v2",
        "data-v2.2-v2-no-knowledge",
    }:
        run_kwargs = {}
        if decision_agent_mode in {"data-v2.2-v2", "data-v2.2-v2-no-knowledge"}:
            if decision_agent_mode == "data-v2.2-v2-no-knowledge":
                from SC2_Agent.knowledge_v2_2_v2_no_knowledge import (
                    build_knowledge_decision_context as build_v2_context,
                    run_decision as run_v2_decision,
                )
                trace_name = "knowledge_v2_2_v2_no_knowledge_traces"
            else:
                from SC2_Agent.knowledge_v2_2_v2 import (
                    build_knowledge_decision_context as build_v2_context,
                    run_decision as run_v2_decision,
                )
                trace_name = "knowledge_v2_2_v2_traces"
            structured = {
                "time": 0.0,
                "economy": {
                    "minerals": 50,
                    "vespene": 0,
                    "minerals_per_min": 720,
                    "vespene_per_min": 0,
                    "supply_used": 12,
                    "supply_cap": 15,
                    "supply_left": 3,
                    "supply_workers": 12,
                    "ideal_worker_count": 16,
                },
                "own_forces": {
                    "completed": {
                        {"terran": "SCV", "protoss": "PROBE", "zerg": "DRONE"}[race]: 12,
                        {"terran": "COMMANDCENTER", "protoss": "NEXUS", "zerg": "HATCHERY"}[race]: 1,
                    },
                    "under_construction": {},
                    "workers_en_route": {},
                    "active_queues": {},
                },
            }
            ledger = {"facts": {}}
            planner_state = {}
            context = build_v2_context(
                **prompt_arguments,
                observation_structured=structured,
                planner_state=planner_state,
                knowledge_ledger=ledger,
            )
            selected_run_decision = run_v2_decision
            run_kwargs = {
                "planning_snapshot": context["planning_snapshot"],
                "planner_state": planner_state,
                "knowledge_ledger": ledger,
            }
        else:
            context = build_knowledge_decision_context(**prompt_arguments)
            selected_run_decision = run_decision
            trace_name = "knowledge_v2_2_traces"
        knowledge_result = selected_run_decision(
            system_prompt=context["system_prompt"],
            decision_event=context["decision_event"],
            provider=model,
            subagent_provider=subagent_model,
            enable_reasoning=False,
            log_dir=ROOT / "game_records" / "prompt_probes" / trace_name,
            decision_metadata=context["metadata"],
            **run_kwargs,
        )
        payload = knowledge_result["decision"]
        raw = json.dumps(payload, ensure_ascii=False)
        parsed = parse_decision_response(raw)
        result = (knowledge_result.get("reasoning_trace") or [{}])[-1]
    else:
        messages = build_decision_messages(**prompt_arguments)
        result = call_openai_detailed(messages=messages, model_key=model)
        raw = str(result.get("content") or "")
        parsed = parse_decision_response(raw)
    unknown = []
    unmapped = []
    if parsed is not None:
        for name in parsed.ordered_names:
            canonical = canonical_race_entity_name(race, name)
            if canonical is None:
                unknown.append(name)
            elif not action_candidates_for_entity(race, canonical):
                unmapped.append(name)
    return {
        "race": race,
        "strategy": strategy,
        "model_key": model,
        "data_subagent_model_key": subagent_model,
        "decision_agent_mode": decision_agent_mode,
        "parsed": parsed is not None,
        "reason": parsed.reason if parsed else "",
        "ordered_names": parsed.ordered_names if parsed else [],
        "unknown_names": unknown,
        "unmapped_names": unmapped,
        "provider_error": result.get("error", "") or "",
        "is_reasoning": result.get("is_reasoning"),
        "reasoning_source": result.get("reasoning_source", "none"),
        "raw_response": raw,
        "knowledge_trace_path": (
            knowledge_result.get("log_path") if knowledge_result else None
        ),
        "main_round_count": len(knowledge_result.get("main_decisions") or []) if knowledge_result else 0,
        "subagent_session_count": len(knowledge_result.get("subagent_sessions") or []) if knowledge_result else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--subagent-model-key", default="Kimi-k2.5")
    parser.add_argument(
        "--decision-agent-mode",
        choices=("data-v2.2-v2-no-knowledge", "data-v2.2-v2", "data-v2.2", "naive"),
        default="data-v2.2",
    )
    parser.add_argument("--enemy-race", default="terran")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    jobs = [
        (race, strategy)
        for race in ("terran", "protoss", "zerg")
        for strategy in enabled_strategy_names(race)
    ]
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {
            pool.submit(
                _probe_one,
                args.model_key,
                args.subagent_model_key,
                args.decision_agent_mode,
                args.enemy_race,
                race,
                strategy,
            ): (race, strategy)
            for race, strategy in jobs
        }
        for future in as_completed(futures):
            race, strategy = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {
                    "race": race,
                    "strategy": strategy,
                    "model_key": args.model_key,
                    "data_subagent_model_key": args.subagent_model_key,
                    "decision_agent_mode": args.decision_agent_mode,
                    "parsed": False,
                    "provider_error": repr(exc),
                    "unknown_names": [],
                    "unmapped_names": [],
                }
            rows.append(row)
            print(
                f"{race}/{strategy}: parsed={row.get('parsed')} "
                f"unknown={row.get('unknown_names')} "
                f"unmapped={row.get('unmapped_names')} "
                f"error={row.get('provider_error')!r}",
                flush=True,
            )

    rows.sort(key=lambda row: (row["race"], row["strategy"]))
    output = Path(args.output) if args.output else (
        ROOT
        / "game_records"
        / "prompt_probes"
        / f"{datetime.now():%Y%m%d_%H%M%S}_{args.decision_agent_mode}_{args.model_key}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "model_key": args.model_key,
                "data_subagent_model_key": args.subagent_model_key,
                "decision_agent_mode": args.decision_agent_mode,
                "enemy_race": args.enemy_race,
                "count": len(rows),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    failures = [
        row
        for row in rows
        if not row.get("parsed")
        or row.get("provider_error")
        or row.get("unknown_names")
        or row.get("unmapped_names")
    ]
    print(f"wrote={output} failures={len(failures)}/{len(rows)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
