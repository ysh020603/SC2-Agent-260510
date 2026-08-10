"""Probe SunTzu, HIMA, and CoS orchestration without launching SC2."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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
from tools.probe_structural_baselines import INITIAL_OBSERVATION


def _implementation(mode: str):
    if mode == "suntzu":
        from SC2_Agent.baseline_suntzu import (
            build_decision_context,
            run_decision,
        )

        return build_decision_context, run_decision, "suntzu_traces"
    if mode == "hima":
        from SC2_Agent.baseline_hima import (
            build_decision_context,
            run_decision,
        )

        return build_decision_context, run_decision, "hima_traces"
    if mode == "cos":
        from SC2_Agent.baseline_cos import (
            CoSState,
            build_decision_context,
            run_decision,
        )

        return build_decision_context, run_decision, "cos_traces", CoSState
    raise ValueError(f"Unsupported mode: {mode}")


def _prompt_arguments(
    *,
    race: str,
    enemy_race: str,
    strategy: str,
    cycle: int,
) -> Dict[str, Any]:
    strategy_dir = ROOT / "SKILL" / race / strategy
    summary = parse_strategy_summary(
        (strategy_dir / "Top_agent.md").read_text(encoding="utf-8")
    )
    module = importlib.import_module(f"SKILL.{race}.{strategy}.strategy_tools")
    profile = getattr(module, "AUTOMATION_PROFILE", None)
    if not isinstance(profile, StrategyAutomationProfile):
        raise ValueError(f"Missing automation profile for {race}/{strategy}")
    return {
        "race": race,
        "enemy_race": enemy_race,
        "strategy_summary": summary,
        "strategy_automation_context": profile.render(),
        "obs_text": INITIAL_OBSERVATION[race],
        "unfinished_canonical_names": [],
        "canonical_unit_names": race_unit_names(race),
        "canonical_upgrade_names": race_upgrade_names(race),
        "race_context": race_prompt_context(race),
        "decision_cycle": cycle,
        "trigger_reason": "initial_decision" if cycle == 1 else "interval_elapsed",
        "game_time_seconds": (cycle - 1) * 60,
        "decision_interval_seconds": 60,
    }


def _validate_names(race: str, names: List[str]) -> Dict[str, List[str]]:
    accepted: List[str] = []
    unknown: List[str] = []
    unmapped: List[str] = []
    for name in names:
        canonical = canonical_race_entity_name(race, name)
        if canonical is None:
            unknown.append(name)
        elif not action_candidates_for_entity(race, canonical):
            unmapped.append(canonical)
        else:
            accepted.append(canonical)
    return {
        "accepted_ordered_names": accepted,
        "unknown_names": unknown,
        "unmapped_names": unmapped,
    }


def _probe_one(
    *,
    mode: str,
    model_key: str,
    race: str,
    enemy_race: str,
    strategy: str,
    output_root: Path,
    cos_cycles: int,
) -> Dict[str, Any]:
    implementation = _implementation(mode)
    build_decision_context, run_decision, trace_name = implementation[:3]
    state = implementation[3]() if mode == "cos" else None
    cycle_results: List[Dict[str, Any]] = []
    cycles = cos_cycles if mode == "cos" else 1

    for cycle in range(1, cycles + 1):
        context = build_decision_context(
            **_prompt_arguments(
                race=race,
                enemy_race=enemy_race,
                strategy=strategy,
                cycle=cycle,
            )
        )
        kwargs = {
            "system_prompt": context["system_prompt"],
            "decision_event": context["decision_event"],
            "provider": model_key,
            "log_dir": str(output_root / trace_name),
            "decision_metadata": context["metadata"],
        }
        if state is not None:
            kwargs["cos_state"] = state
        result = run_decision(**kwargs)
        decision = result.get("decision") or {}
        names = list(decision.get("ordered_names") or [])
        cycle_results.append(
            {
                "cycle": cycle,
                "status": result.get("status"),
                "stop_reason": result.get("stop_reason"),
                "model_call_count": result.get("model_call_count"),
                "roles": [
                    call.get("role") for call in (result.get("llm_calls") or [])
                ],
                "provider_errors": [
                    call.get("error")
                    for call in (result.get("llm_calls") or [])
                    if call.get("error")
                ],
                "is_reasoning_flags": [
                    call.get("is_reasoning")
                    for call in (result.get("llm_calls") or [])
                ],
                "reason": decision.get("reason"),
                "ordered_names": names,
                "history_size": result.get("history_size"),
                "trace_path": result.get("log_path"),
                **_validate_names(race, names),
            }
        )

    return {
        "mode": mode,
        "race": race,
        "strategy": strategy,
        "enemy_race": enemy_race,
        "model_key": model_key,
        "cycles": cycle_results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--decision-agent-mode",
        choices=("suntzu", "hima", "cos"),
        required=True,
    )
    parser.add_argument("--model-key", default="qwen3-32b")
    parser.add_argument("--enemy-race", default="terran")
    parser.add_argument("--races", default="terran,protoss,zerg")
    parser.add_argument(
        "--cos-cycles",
        type=int,
        default=6,
        help="Consecutive cycles per race for CoS history validation.",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)

    races = [item.strip().lower() for item in args.races.split(",") if item.strip()]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = (
        Path(args.output)
        if args.output
        else ROOT
        / "game_records"
        / "prompt_probes"
        / f"sc2_structural_{args.decision_agent_mode}_{args.model_key}_{stamp}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    trace_root = output.parent / f"{args.decision_agent_mode}_{stamp}"

    rows = []
    for race in races:
        strategy = enabled_strategy_names(race)[0]
        print(
            f"[probe] mode={args.decision_agent_mode} race={race} "
            f"strategy={strategy} model={args.model_key}"
        )
        rows.append(
            _probe_one(
                mode=args.decision_agent_mode,
                model_key=args.model_key,
                race=race,
                enemy_race=args.enemy_race,
                strategy=strategy,
                output_root=trace_root,
                cos_cycles=max(6, args.cos_cycles),
            )
        )

    payload = {
        "decision_agent_mode": args.decision_agent_mode,
        "model_key": args.model_key,
        "results": rows,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {output}")

    failures = []
    for row in rows:
        for cycle in row["cycles"]:
            if (
                cycle["status"] != "completed"
                or cycle["provider_errors"]
                or cycle["unknown_names"]
                or cycle["unmapped_names"]
                or any(cycle["is_reasoning_flags"])
            ):
                failures.append((row["race"], cycle["cycle"]))
        if args.decision_agent_mode == "cos":
            sizes = [cycle["history_size"] for cycle in row["cycles"]]
            expected = [min(index, 5) for index in range(1, len(sizes) + 1)]
            if sizes != expected:
                failures.append((row["race"], "history"))

    if failures:
        print(f"FAIL: {failures}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
