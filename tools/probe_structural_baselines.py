"""Probe plan-execute / self-refine orchestration without launching SC2."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from SC2_Agent.data_tools import (
    action_candidates_for_entity,
    canonical_race_entity_name,
    race_prompt_context,
    race_unit_names,
    race_upgrade_names,
)
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
    *,
    model: str,
    decision_agent_mode: str,
    enemy_race: str,
    race: str,
    strategy: str,
    output_root: Path,
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

    if decision_agent_mode == "plan-execute":
        from SC2_Agent.baseline_plan_execute import (
            build_decision_context,
            run_decision,
        )

        trace_name = "pe_traces"
    elif decision_agent_mode == "self-refine":
        from SC2_Agent.baseline_self_refine import (
            build_decision_context,
            run_decision,
        )

        trace_name = "sr_traces"
    else:
        raise ValueError(f"Unsupported structural mode: {decision_agent_mode}")

    ctx = build_decision_context(**prompt_arguments)
    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider=model,
        log_dir=str(output_root / trace_name),
        decision_metadata=ctx["metadata"],
    )
    decision = result.get("decision") or {}
    ordered = list(decision.get("ordered_names") or [])
    unknown = []
    unmapped = []
    accepted = []
    for name in ordered:
        canonical = canonical_race_entity_name(race, name)
        if canonical is None:
            unknown.append(name)
            continue
        if not action_candidates_for_entity(race, canonical):
            unmapped.append(canonical)
            continue
        accepted.append(canonical)

    return {
        "race": race,
        "strategy": strategy,
        "enemy_race": enemy_race,
        "decision_agent_mode": decision_agent_mode,
        "model_key": model,
        "status": result.get("status"),
        "stop_reason": result.get("stop_reason"),
        "model_call_count": result.get("model_call_count"),
        "reason": decision.get("reason"),
        "ordered_names": ordered,
        "accepted_ordered_names": accepted,
        "unknown_names": unknown,
        "unmapped_names": unmapped,
        "provider_errors": [
            call.get("error")
            for call in (result.get("llm_calls") or [])
            if call.get("error")
        ],
        "roles": [call.get("role") for call in (result.get("llm_calls") or [])],
        "trace_path": result.get("log_path"),
        "is_reasoning_flags": [
            call.get("is_reasoning") for call in (result.get("llm_calls") or [])
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe structural harness baselines without SC2."
    )
    parser.add_argument(
        "--decision-agent-mode",
        choices=("plan-execute", "self-refine"),
        required=True,
    )
    parser.add_argument("--model-key", default="qwen3-32b")
    parser.add_argument("--enemy-race", default="terran")
    parser.add_argument(
        "--strategies",
        default="",
        help="Comma-separated strategies; default one enabled strategy per race.",
    )
    parser.add_argument(
        "--races",
        default="terran,protoss,zerg",
        help="Comma-separated bot races.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output JSON path under game_records/prompt_probes/.",
    )
    args = parser.parse_args(argv)

    races = [item.strip().lower() for item in args.races.split(",") if item.strip()]
    selected = {
        item.strip() for item in args.strategies.split(",") if item.strip()
    }
    rows = []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = (
        Path(args.output)
        if args.output
        else ROOT
        / "game_records"
        / "prompt_probes"
        / f"structural_{args.decision_agent_mode}_{args.model_key}_{stamp}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    for race in races:
        strategies = enabled_strategy_names(race)
        if selected:
            strategies = [name for name in strategies if name in selected]
        if not strategies:
            raise SystemExit(f"No enabled strategies for race={race}")
        strategy = strategies[0]
        print(
            f"[probe] mode={args.decision_agent_mode} race={race} "
            f"strategy={strategy} model={args.model_key}"
        )
        row = _probe_one(
            model=args.model_key,
            decision_agent_mode=args.decision_agent_mode,
            enemy_race=args.enemy_race,
            race=race,
            strategy=strategy,
            output_root=output.parent / f"{args.decision_agent_mode}_{stamp}",
        )
        rows.append(row)
        print(
            f"  status={row['status']} calls={row['model_call_count']} "
            f"names={row['accepted_ordered_names']}"
        )

    payload = {
        "decision_agent_mode": args.decision_agent_mode,
        "model_key": args.model_key,
        "enemy_race": args.enemy_race,
        "results": rows,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output}")

    failures = [
        row
        for row in rows
        if row["status"] != "completed"
        or row["provider_errors"]
        or row["unknown_names"]
        or row["unmapped_names"]
        or any(flag for flag in row["is_reasoning_flags"])
    ]
    if failures:
        print(f"FAIL: {len(failures)} probe(s) failed")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
