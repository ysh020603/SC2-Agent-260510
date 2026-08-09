"""Summarize paired readable-skill SC2 experiment artifacts."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
METHOD_NAMES = ("full", "single_trace", "flat_adaptive", "positive_only")
OUTCOME_SCORE = {"Victory": 1.0, "Tie": 0.5, "Defeat": 0.0}


def mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 4) if values else math.nan


def read_rows(prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method in METHOD_NAMES:
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
            model_calls = [item for item in calls if item not in watchdog_events]
            metrics = metadata.get("macro_metrics") or {}
            rows.append(
                {
                    "method": method,
                    "skill_method": first.get("skill_method"),
                    "skill_id": first.get("skill_id"),
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
                }
            )
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for method in METHOD_NAMES:
        all_group = [row for row in rows if row["method"] == method]
        group = [row for row in all_group if not row["watchdog_recovery"]]
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


def paired(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_method = {
        method: {
            row["skill_id"]: row
            for row in rows
            if row["method"] == method and not row["watchdog_recovery"]
        }
        for method in METHOD_NAMES
    }
    comparisons: dict[str, Any] = {}
    full = by_method["full"]
    for method in METHOD_NAMES[1:]:
        keys = sorted(set(full) & set(by_method[method]))
        comparisons[method] = {
            "paired_n": len(keys),
            "full_minus_ablation_outcome": mean(
                [full[key]["outcome_score"] - by_method[method][key]["outcome_score"] for key in keys]
            ),
            "full_minus_ablation_consume": mean(
                [full[key]["rur_consume_per_min"] - by_method[method][key]["rur_consume_per_min"] for key in keys]
            ),
            "ablation_minus_full_bank": mean(
                [by_method[method][key]["rur_float_avg_bank"] - full[key]["rur_float_avg_bank"] for key in keys]
            ),
            "full_better_outcome": sum(
                full[key]["outcome_score"] > by_method[method][key]["outcome_score"] for key in keys
            ),
            "same_outcome": sum(
                full[key]["outcome_score"] == by_method[method][key]["outcome_score"] for key in keys
            ),
            "ablation_better_outcome": sum(
                full[key]["outcome_score"] < by_method[method][key]["outcome_score"] for key in keys
            ),
        }
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-prefix", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    rows = read_rows(args.batch_prefix)
    report = {"batch_prefix": args.batch_prefix, "rows": rows, "aggregate": aggregate(rows), "paired": paired(rows)}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
