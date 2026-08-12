"""Summarize paired readable-skill SC2 experiment artifacts."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
METHOD_NAMES = (
    "full",
    "full_v2",
    "full_v3",
    "full_v4",
    "full_v5",
    "full_v6",
    "full_v7",
    "full_v8",
    "full_v9",
    "full_v10",
    "full_v11",
    "full_v12",
    "full_v13",
    "full_v14",
    "full_v15",
    "full_v16",
    "full_v17",
    "full_v18",
    "single_trace",
    "static_population",
    "flat_adaptive",
    "positive_only",
    "frequency_only",
)
OUTCOME_SCORE = {"Victory": 1.0, "Tie": 0.5, "Defeat": 0.0}


def mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 4) if values else math.nan


def exact_two_sided_sign_p(baseline_better: int, method_better: int) -> float:
    """Exact two-sided sign test over outcome-discordant paired matches."""

    n = int(baseline_better) + int(method_better)
    if n <= 0:
        return math.nan
    tail = sum(math.comb(n, i) for i in range(min(baseline_better, method_better) + 1)) / (2**n)
    return round(min(1.0, 2.0 * tail), 6)


def read_rows(prefix: str, methods: tuple[str, ...] = METHOD_NAMES) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method in methods:
        batch_dir = ROOT / "game_records" / f"{prefix}_{method}"
        for match_path in sorted(batch_dir.glob("*/match.json")):
            try:
                match = json.loads(match_path.read_text(encoding="utf-8"))
                metadata = match["metadata"]
                first = match["interactions"][0]
                trace_path = next(match_path.parent.glob("*.human_skill.json"))
                trace = json.loads(trace_path.read_text(encoding="utf-8"))
                reads_path = next(match_path.parent.glob("*.skill_reads.json"))
                reads = json.loads(reads_path.read_text(encoding="utf-8"))
                llm = json.loads((match_path.parent / "match.llm_calls.json").read_text(encoding="utf-8"))
            except (OSError, ValueError, KeyError, StopIteration, TypeError):
                continue
            decisions = trace.get("decisions") or []
            rounds = [item for decision in decisions for item in decision.get("agent_rounds") or []]
            calls = llm.get("calls") or []
            watchdog_events = [
                item
                for item in calls
                if item.get("event") == "sc2_protocol_watchdog_recovery"
            ]
            try:
                match_log = (match_path.parent / "match.log").read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                match_log = ""
            if (
                not watchdog_events
                and (
                    "SC2 protocol response timed out" in match_log
                    or "Recovered stalled SC2 protocol request" in match_log
                    or "SC2 client process exited" in match_log
                    or "AI iteration timed out" in match_log
                )
            ):
                watchdog_events.append(
                    {"event": "sc2_protocol_watchdog_recovery", "source": "match.log"}
                )
            model_calls = [item for item in calls if item not in watchdog_events]
            run_match = re.search(r"_run(\d+)$", match_path.parent.name)
            run_index = int(run_match.group(1)) if run_match else None
            metrics = metadata.get("macro_metrics") or {}
            rows.append(
                {
                    "method": method,
                    "skill_method": first.get("skill_method"),
                    "skill_id": first.get("skill_id"),
                    "run_index": run_index,
                    "matchup": metadata.get("matchup"),
                    "opponent_id": metadata.get("opponent_id"),
                    "result": metadata.get("result"),
                    "outcome_score": OUTCOME_SCORE.get(metadata.get("result"), math.nan),
                    "duration": metadata.get("game_duration_seconds"),
                    "rur_consume_per_min": metrics.get("rur_consume_per_min"),
                    "rur_float_avg_bank": metrics.get("rur_float_avg_bank"),
                    "apu_ratio": metrics.get("apu_ratio"),
                    "decision_count": len(decisions),
                    "invalid_rounds": sum(item.get("type") == "invalid" for item in rounds),
                    "decision_errors": sum(bool(item.get("error")) for item in decisions),
                    "visited_nodes": list(reads.get("visited_node_ids") or []),
                    "llm_calls": len(model_calls),
                    "reasoning_present": sum(bool(item.get("reasoning_present")) for item in model_calls),
                    "is_reasoning_not_false": sum(item.get("is_reasoning") is not False for item in model_calls),
                    "api_errors": sum(bool(item.get("error")) for item in model_calls),
                    "watchdog_recovery": bool(watchdog_events),
                    "watchdog_events": watchdog_events,
                    "record_dir": str(match_path.parent),
                    "valid_artifact": bool(
                        run_index is not None
                        and metadata.get("result") in OUTCOME_SCORE
                        and not watchdog_events
                        and model_calls
                        and not any(item.get("error") for item in model_calls)
                        and all(item.get("is_reasoning") is False for item in model_calls)
                        and not any(item.get("reasoning_present") for item in model_calls)
                    ),
                }
            )
    return rows


def aggregate(rows: list[dict[str, Any]], methods: tuple[str, ...] = METHOD_NAMES) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for method in methods:
        all_group = [row for row in rows if row["method"] == method]
        group = [row for row in all_group if row["valid_artifact"]]
        result[method] = {
            "n": len(group),
            "watchdog_recovery_count": sum(row["watchdog_recovery"] for row in all_group),
            "results": dict(Counter(row["result"] for row in group)),
            "outcome_score": mean([float(row["outcome_score"]) for row in group]),
            "mean_duration": mean([float(row["duration"]) for row in group]),
            "mean_rur_consume_per_min": mean([float(row["rur_consume_per_min"]) for row in group]),
            "mean_rur_float_avg_bank": mean([float(row["rur_float_avg_bank"]) for row in group]),
            "mean_apu_ratio": mean([float(row["apu_ratio"]) for row in group]),
            "mean_invalid_rounds": mean([float(row["invalid_rounds"]) for row in group]),
            "decision_error_matches": sum(row["decision_errors"] > 0 for row in group),
            "reasoning_present": sum(row["reasoning_present"] for row in group),
            "is_reasoning_not_false": sum(row["is_reasoning_not_false"] for row in group),
            "api_errors": sum(row["api_errors"] for row in group),
        }
    return result


def aggregate_by_bot_race(
    rows: list[dict[str, Any]], methods: tuple[str, ...] = METHOD_NAMES
) -> dict[str, dict[str, Any]]:
    race_name = {"P": "protoss", "T": "terran", "Z": "zerg"}
    result: dict[str, dict[str, Any]] = {}
    for method in methods:
        result[method] = {}
        for prefix, race in race_name.items():
            group = [
                row
                for row in rows
                if row["method"] == method
                and row["valid_artifact"]
                and str(row.get("skill_id") or "").startswith(prefix)
            ]
            result[method][race] = {
                "n": len(group),
                "results": dict(Counter(row["result"] for row in group)),
                "outcome_score": mean([float(row["outcome_score"]) for row in group]),
                "mean_rur_consume_per_min": mean(
                    [float(row["rur_consume_per_min"]) for row in group]
                ),
                "mean_rur_float_avg_bank": mean(
                    [float(row["rur_float_avg_bank"]) for row in group]
                ),
            }
    return result


def paired(
    rows: list[dict[str, Any]],
    methods: tuple[str, ...] = METHOD_NAMES,
    baseline: str = "full",
) -> dict[str, Any]:
    by_method = {
        method: {
            (row["skill_id"], row["run_index"]): row
            for row in rows
            if row["method"] == method and row["valid_artifact"]
        }
        for method in methods
    }
    comparisons: dict[str, Any] = {}
    full = by_method[baseline]
    for method in methods:
        if method == baseline:
            continue
        keys = sorted(set(full) & set(by_method[method]))
        baseline_better = sum(
            full[key]["outcome_score"] > by_method[method][key]["outcome_score"] for key in keys
        )
        method_better = sum(
            full[key]["outcome_score"] < by_method[method][key]["outcome_score"] for key in keys
        )
        comparisons[method] = {
            "paired_n": len(keys),
            "baseline_minus_method_outcome": mean(
                [full[key]["outcome_score"] - by_method[method][key]["outcome_score"] for key in keys]
            ),
            "method_minus_baseline_outcome": mean(
                [by_method[method][key]["outcome_score"] - full[key]["outcome_score"] for key in keys]
            ),
            "baseline_minus_method_consume": mean(
                [full[key]["rur_consume_per_min"] - by_method[method][key]["rur_consume_per_min"] for key in keys]
            ),
            "method_minus_baseline_bank": mean(
                [by_method[method][key]["rur_float_avg_bank"] - full[key]["rur_float_avg_bank"] for key in keys]
            ),
            "baseline_better_outcome": baseline_better,
            "same_outcome": sum(
                full[key]["outcome_score"] == by_method[method][key]["outcome_score"] for key in keys
            ),
            "method_better_outcome": method_better,
            "outcome_sign_test_p_two_sided": exact_two_sided_sign_p(
                baseline_better, method_better
            ),
        }
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-prefix", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--methods", default=",".join(METHOD_NAMES))
    parser.add_argument("--baseline", default="full")
    args = parser.parse_args()
    methods = tuple(item.strip() for item in args.methods.split(",") if item.strip())
    unknown = set(methods) - set(METHOD_NAMES)
    if not methods or unknown:
        raise ValueError(f"unknown/empty methods selection: {sorted(unknown)}")
    if args.baseline not in methods:
        raise ValueError("baseline must be included in --methods")
    rows = read_rows(args.batch_prefix, methods)
    report = {
        "batch_prefix": args.batch_prefix,
        "methods": list(methods),
        "baseline": args.baseline,
        "rows": rows,
        "aggregate": aggregate(rows, methods),
        "aggregate_by_bot_race": aggregate_by_bot_race(rows, methods),
        "paired": paired(rows, methods, args.baseline),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
