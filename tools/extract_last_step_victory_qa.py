#!/usr/bin/env python3
"""Extract paired last-step Naming/Ordering Q&A from v7 terran sweep game records.

Only includes:
  - Victory games
  - macro cycles where strategy_step.is_last is True
  - cycles with BOTH naming and ordering LLM calls (mismatched cycles excluded)

Output: JSONL + companion markdown under game_records/.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
GAME_RECORDS = ROOT / "game_records"

BATCHES: List[Tuple[str, str]] = [
    ("qwen32b_think_nothink_exec_v7_r3", "Qwen3-32b_think planning + Qwen3-32b execution"),
    ("qwen4b_think_27b_exec_v7_r3", "Qwen3-4b_think planning + Qwen35-27b execution"),
    ("qwen14b_think_27b_exec_v7_r3", "Qwen3-14b_think planning + Qwen35-27b execution"),
]

STRATEGY_ABBR = {
    "bio": "bio",
    "safetvtrav": "safe_tvt_raven",
    "tankthorme": "tank_thor_mech",
    "threeraxst": "three_rax_stim",
    "twobasetan": "two_base_tanks",
    "battlecrui": "battle_cruisers",
}

DEFAULT_STEM = "qwen_think_hybrid_v7_terran_sweep_last_step_victory_qa"


def _parse_opponent(opponent_id: str) -> Dict[str, str]:
    match = re.search(r"\.(protoss|terran|zerg)\.(easy|medium|mediumhard)\.", opponent_id or "")
    if not match:
        return {"enemy_race": "", "difficulty": ""}
    return {"enemy_race": match.group(1), "difficulty": match.group(2)}


def _parse_strategy(match_id: str) -> str:
    match = re.match(r"\d{8}_\d{6}_([^_]+)_", match_id)
    if not match:
        return ""
    return STRATEGY_ABBR.get(match.group(1), match.group(1))


def _load_last_step_cycles(game_json: Path) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    data = json.loads(game_json.read_text(encoding="utf-8"))
    meta = data.get("metadata") or {}
    cycle_info: Dict[int, Dict[str, Any]] = {}
    for item in data.get("interactions") or []:
        if not isinstance(item, dict):
            continue
        step = item.get("strategy_step") or {}
        if not step.get("is_last"):
            continue
        cycle = item.get("cycle")
        if cycle is None:
            continue
        cycle_info[int(cycle)] = {
            "game_time": item.get("game_time"),
            "trigger_reason": item.get("trigger_reason"),
            "strategy_step_number": step.get("number"),
            "strategy_step_index": step.get("index"),
            "strategy_step_text": item.get("strategy_step_text") or step.get("text"),
            "error": item.get("error"),
            "named_items": item.get("named_items"),
            "ordered_actions": item.get("ordered_actions"),
        }
    return meta, cycle_info


def _index_llm_calls(llm_calls_json: Path) -> Dict[Tuple[int, str], Dict[str, Any]]:
    payload = json.loads(llm_calls_json.read_text(encoding="utf-8"))
    indexed: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for call in payload.get("calls") or []:
        cycle = call.get("macro_cycle")
        agent = call.get("agent")
        if cycle is None or agent not in ("naming", "ordering"):
            continue
        indexed[(int(cycle), agent)] = call
    return indexed


def _build_record(
    *,
    batch_key: str,
    batch_label: str,
    match_id: str,
    match_dir: Path,
    game_json: Path,
    llm_calls_json: Path,
    meta: Dict[str, Any],
    cycle: int,
    cycle_meta: Dict[str, Any],
    last_step_ordinal: int,
    agent: str,
    call: Dict[str, Any],
    pair_id: str,
    pair_partner_agent: str,
    pair_partner_seq: Optional[int],
) -> Dict[str, Any]:
    opp = _parse_opponent(str(meta.get("opponent_id") or ""))
    rel_match_dir = match_dir.relative_to(ROOT).as_posix()
    rel_game_json = game_json.relative_to(ROOT).as_posix()
    rel_llm_calls_json = llm_calls_json.relative_to(ROOT).as_posix()
    return {
        "record_id": f"{batch_key}/{match_id}/cycle_{cycle}/{agent}",
        "pair_id": pair_id,
        "pair_partner_agent": pair_partner_agent,
        "pair_partner_llm_call_seq": pair_partner_seq,
        "batch": batch_key,
        "batch_label": batch_label,
        "match_id": match_id,
        "match_dir": rel_match_dir,
        "source_game_json": rel_game_json,
        "source_llm_calls_json": rel_llm_calls_json,
        "game_result": meta.get("result"),
        "opponent_id": meta.get("opponent_id"),
        "strategy": _parse_strategy(match_id),
        "map_name": meta.get("map_name"),
        "enemy_race": opp["enemy_race"],
        "difficulty": opp["difficulty"],
        "macro_cycle": cycle,
        "last_step_cycle_ordinal": last_step_ordinal,
        "game_time": cycle_meta.get("game_time"),
        "trigger_reason": cycle_meta.get("trigger_reason"),
        "strategy_step_number": cycle_meta.get("strategy_step_number"),
        "strategy_step_index": cycle_meta.get("strategy_step_index"),
        "strategy_step_text": cycle_meta.get("strategy_step_text"),
        "agent": agent,
        "llm_call_seq": call.get("seq"),
        "model_key": call.get("model_key"),
        "model": call.get("model"),
        "is_reasoning": call.get("is_reasoning"),
        "reasoning_source": call.get("reasoning_source"),
        "reasoning_extract_mode": call.get("reasoning_extract_mode"),
        "prompt": call.get("prompt") or [],
        "cot": call.get("reasoning") or "",
        "answer": call.get("output") or "",
        "raw_content": call.get("raw_content") or "",
        "llm_error": call.get("error") or "",
        "pipeline_named_items": cycle_meta.get("named_items"),
        "pipeline_ordered_actions": cycle_meta.get("ordered_actions"),
        "pipeline_error": cycle_meta.get("error"),
    }


def extract_records() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {
        "games_scanned": 0,
        "victory_games": 0,
        "victory_reached_last_step": 0,
        "last_step_cycles_total": 0,
        "excluded_unpaired_cycles": 0,
        "excluded_unpaired_games": set(),
        "paired_cycles": 0,
        "records_total": 0,
        "naming_records": 0,
        "ordering_records": 0,
        "by_batch": defaultdict(lambda: defaultdict(int)),
    }

    for batch_key, batch_label in BATCHES:
        batch_dir = GAME_RECORDS / batch_key
        if not batch_dir.is_dir():
            continue
        for game_json in sorted(batch_dir.glob("*/*.json")):
            if game_json.name.endswith(".llm_calls.json"):
                continue
            stats["games_scanned"] += 1
            llm_calls_json = game_json.with_suffix(".llm_calls.json")
            if not llm_calls_json.is_file():
                continue

            meta, cycle_info = _load_last_step_cycles(game_json)
            is_victory = meta.get("result") == "Victory"
            if is_victory:
                stats["victory_games"] += 1
            if not is_victory or not cycle_info:
                continue

            stats["victory_reached_last_step"] += 1
            match_id = game_json.stem
            match_dir = game_json.parent
            calls = _index_llm_calls(llm_calls_json)

            sorted_cycles = sorted(cycle_info)
            stats["last_step_cycles_total"] += len(sorted_cycles)

            for ordinal, cycle in enumerate(sorted_cycles, start=1):
                naming = calls.get((cycle, "naming"))
                ordering = calls.get((cycle, "ordering"))
                if naming is None or ordering is None:
                    stats["excluded_unpaired_cycles"] += 1
                    stats["excluded_unpaired_games"].add(f"{batch_key}/{match_id}")
                    continue

                stats["paired_cycles"] += 1
                pair_id = f"{batch_key}/{match_id}/cycle_{cycle}"
                cycle_meta = cycle_info[cycle]

                for agent, call, partner_agent, partner_call in (
                    ("naming", naming, "ordering", ordering),
                    ("ordering", ordering, "naming", naming),
                ):
                    rec = _build_record(
                        batch_key=batch_key,
                        batch_label=batch_label,
                        match_id=match_id,
                        match_dir=match_dir,
                        game_json=game_json,
                        llm_calls_json=llm_calls_json,
                        meta=meta,
                        cycle=cycle,
                        cycle_meta=cycle_meta,
                        last_step_ordinal=ordinal,
                        agent=agent,
                        call=call,
                        pair_id=pair_id,
                        pair_partner_agent=partner_agent,
                        pair_partner_seq=partner_call.get("seq"),
                    )
                    records.append(rec)
                    stats["records_total"] += 1
                    stats["naming_records" if agent == "naming" else "ordering_records"] += 1
                    stats["by_batch"][batch_key][f"{agent}_records"] += 1
                    if agent == "naming":
                        stats["by_batch"][batch_key]["paired_cycles"] += 1

    for batch_key, _ in BATCHES:
        batch_pairs = {r["match_id"] for r in records if r["batch"] == batch_key}
        stats["by_batch"][batch_key]["victory_games_with_pairs"] = len(batch_pairs)

    stats["excluded_unpaired_games"] = sorted(stats["excluded_unpaired_games"])
    stats["excluded_unpaired_game_count"] = len(stats["excluded_unpaired_games"])
    return records, stats


def write_jsonl(records: Iterable[Dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_markdown(records: List[Dict[str, Any]], stats: Dict[str, Any], stem: str, jsonl_path: Path) -> Path:
    md_path = jsonl_path.with_suffix(".md")
    rel_jsonl = jsonl_path.relative_to(ROOT).as_posix()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    by_batch = stats["by_batch"]
    excluded = stats["excluded_unpaired_games"]

    lines = [
        f"# {stem.replace('_', ' ').title()}",
        "",
        f"**Project root:** `SC2-Agent-260510/`  ",
        f"**Data file:** `{rel_jsonl}`  ",
        f"**Extractor:** `tools/extract_last_step_victory_qa.py`  ",
        f"**Generated:** {now}",
        "",
        "Companion documentation for the extracted last-step Naming/Ordering Q&A dataset derived from the v7 terran sweep batches documented in `qwen_think_hybrid_v7_terran_sweep_results.md`.",
        "",
        "---",
        "",
        "## Inclusion Criteria",
        "",
        "Each JSONL row is one LLM decision (Naming or Ordering) that satisfies **all** of:",
        "",
        "1. Game result is `Victory` (`metadata.result` in the source `*.json`).",
        "2. The macro cycle is a **last strategy step** cycle (`strategy_step.is_last=True` in `interactions[]`).",
        "3. The cycle has **paired** Naming and Ordering calls in `*.llm_calls.json` (same `macro_cycle`).",
        "4. Cycles where Naming ran but Ordering did not (pipeline stopped at `naming_empty` / `mapping_empty`) are **excluded**.",
        "",
        "Executor calls are **not** included — only Naming and Ordering thinking agents.",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Games scanned | {stats['games_scanned']} |",
        f"| Victory games | {stats['victory_games']} |",
        f"| Victory + reached last step | {stats['victory_reached_last_step']} |",
        f"| Last-step cycles (before pairing filter) | {stats['last_step_cycles_total']} |",
        f"| Excluded unpaired last-step cycles | {stats['excluded_unpaired_cycles']} |",
        f"| Paired last-step cycles kept | {stats['paired_cycles']} |",
        f"| JSONL records (Naming + Ordering) | {stats['records_total']} |",
        f"| Naming records | {stats['naming_records']} |",
        f"| Ordering records | {stats['ordering_records']} |",
        "",
        "### By batch",
        "",
        "| Batch | Victory games w/ ≥1 paired cycle | Paired cycles | Naming | Ordering |",
        "|---|---:|---:|---:|---:|",
    ]

    for batch_key, batch_label in BATCHES:
        b = by_batch.get(batch_key, {})
        lines.append(
            f"| `{batch_key}` | {b.get('victory_games_with_pairs', 0)} | "
            f"{b.get('paired_cycles', 0)} | {b.get('naming_records', 0)} | {b.get('ordering_records', 0)} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Excluded Unpaired Cycles",
        "",
        f"**{stats['excluded_unpaired_cycles']}** last-step cycles across **{stats['excluded_unpaired_game_count']}** games were dropped because Naming and Ordering did not both exist for the same `macro_cycle`.",
        "",
        "Typical cause: Naming LLM returned non-canonical entity names or empty output → `naming_empty` → pipeline returned before Ordering.",
        "",
    ])

    if excluded:
        lines.append("| Batch / Match ID |")
        lines.append("|---|")
        for item in excluded:
            lines.append(f"| `{item}` |")
    else:
        lines.append("_None._")

    lines.extend([
        "",
        "---",
        "",
        "## JSONL Schema",
        "",
        "Each line is one JSON object. Core fields:",
        "",
        "| Field | Description |",
        "|---|---|",
        "| `record_id` | Unique id: `{batch}/{match_id}/cycle_{N}/{agent}` |",
        "| `pair_id` | Links Naming + Ordering from the same last-step cycle |",
        "| `pair_partner_agent` / `pair_partner_llm_call_seq` | Cross-reference to the paired call |",
        "| `batch`, `batch_label` | Sweep batch identity |",
        "| `match_id`, `match_dir` | Game folder under `game_records/` |",
        "| `source_game_json`, `source_llm_calls_json` | Relative paths for full backtrace |",
        "| `strategy`, `enemy_race`, `difficulty`, `opponent_id` | Match context |",
        "| `macro_cycle`, `last_step_cycle_ordinal`, `game_time` | Position inside the game |",
        "| `strategy_step_number`, `strategy_step_index`, `strategy_step_text` | Last-step strategy text used as plan |",
        "| `agent` | `naming` or `ordering` |",
        "| `llm_call_seq` | Index inside `calls[]` of the source `*.llm_calls.json` |",
        "| `model_key`, `is_reasoning`, `reasoning_source` | Model / thinking metadata |",
        "| `prompt` | Full Q: list of `{role, content}` messages |",
        "| `cot` | Chain-of-thought / reasoning text (`reasoning` field from llm_calls) |",
        "| `answer` | Final parsed answer (`output` field from llm_calls) |",
        "| `raw_content` | Original assistant message before extraction |",
        "| `pipeline_named_items`, `pipeline_ordered_actions`, `pipeline_error` | Post-pipeline outcomes from `*.json` interactions |",
        "",
        "---",
        "",
        "## Backtrace Procedure",
        "",
        "To locate the original source for any record:",
        "",
        "1. Open `source_llm_calls_json` → find `calls[llm_call_seq - 1]` (seq is 1-based).",
        "2. Open `source_game_json` → search `interactions[]` where `cycle == macro_cycle` for pipeline context.",
        "3. Open `match_dir/` for `.log` replay and `.SC2Replay` if needed.",
        "",
        "Pair lookup: filter JSONL by shared `pair_id` to get both Naming and Ordering for one last-step decision cycle.",
        "",
        "---",
        "",
        "## Source Batches",
        "",
        "| Batch dir | Label |",
        "|---|---|",
    ])
    for batch_key, batch_label in BATCHES:
        lines.append(f"| `game_records/{batch_key}/` | {batch_label} |")

    lines.extend([
        "",
        "---",
        "",
        "## Related",
        "",
        "- Sweep results overview: `game_records/qwen_think_hybrid_v7_terran_sweep_results.md`",
        "- Architecture (last-step loop): `docs/system-architecture.md`",
        "",
    ])

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stem",
        default=DEFAULT_STEM,
        help="Output file stem under game_records/ (writes <stem>.jsonl and <stem>.md)",
    )
    args = parser.parse_args()

    records, stats = extract_records()
    jsonl_path = GAME_RECORDS / f"{args.stem}.jsonl"
    write_jsonl(records, jsonl_path)
    md_path = write_markdown(records, stats, args.stem, jsonl_path)

    print(f"Wrote {len(records)} records -> {jsonl_path}")
    print(f"Wrote documentation -> {md_path}")
    print(
        f"paired_cycles={stats['paired_cycles']} "
        f"excluded_unpaired_cycles={stats['excluded_unpaired_cycles']} "
        f"naming={stats['naming_records']} ordering={stats['ordering_records']}"
    )


if __name__ == "__main__":
    main()
