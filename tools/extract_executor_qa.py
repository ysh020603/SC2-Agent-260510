#!/usr/bin/env python3
"""Extract executor-layer Q&A from game_records llm_calls.json files."""

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

STRATEGY_ABBR = {
    "bio": "bio",
    "safetvtrav": "safe_tvt_raven",
    "tankthorme": "tank_thor_mech",
    "threeraxst": "three_rax_stim",
    "twobasetan": "two_base_tanks",
    "battlecrui": "battle_cruisers",
}

DEFAULT_STRATEGIES = sorted(STRATEGY_ABBR.values())

ABILITY_RE = re.compile(r"\[Ability to execute\]\s*(\S+)")


def _parse_opponent(opponent_id: str) -> Dict[str, str]:
    match = re.search(r"\.(protoss|terran|zerg)\.(easy|medium|mediumhard|veryeasy|hard)\.", opponent_id or "")
    if not match:
        return {"enemy_race": "", "difficulty": ""}
    return {"enemy_race": match.group(1), "difficulty": match.group(2)}


def _parse_strategy_from_match_id(match_id: str) -> str:
    match = re.match(r"\d{8}_\d{6}_([^_]+)_", match_id)
    if not match:
        return ""
    return STRATEGY_ABBR.get(match.group(1), match.group(1))


def _split_prompt(prompt: List[Dict[str, str]]) -> Tuple[str, str]:
    system = ""
    user = ""
    for msg in prompt or []:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            system = content
        elif role == "user":
            user = content
    return system, user


def _parse_ability(system: str) -> str:
    match = ABILITY_RE.search(system or "")
    return match.group(1) if match else ""


def _load_cycle_info(game_json: Path) -> Dict[int, Dict[str, Any]]:
    data = json.loads(game_json.read_text(encoding="utf-8"))
    cycle_info: Dict[int, Dict[str, Any]] = {}
    for item in data.get("interactions") or []:
        cycle = item.get("cycle")
        if cycle is None:
            continue
        step = item.get("strategy_step") or {}
        cycle_info[int(cycle)] = {
            "trigger_reason": item.get("trigger_reason"),
            "strategy_step_number": step.get("number"),
            "strategy_step_index": step.get("index"),
            "strategy_step_is_last": step.get("is_last"),
            "strategy_step_text": item.get("strategy_step_text") or step.get("text"),
            "observation_at_this_moment": item.get("observation_at_this_moment"),
            "ordered_actions": item.get("ordered_actions"),
        }
    return cycle_info


def _load_game_meta(game_json: Path) -> Dict[str, Any]:
    data = json.loads(game_json.read_text(encoding="utf-8"))
    meta = data.get("metadata") or {}
    strategy = ""
    for item in data.get("interactions") or []:
        if item.get("top_agent_strategy"):
            strategy = str(item["top_agent_strategy"])
            break
        selected = (item.get("strategy") or {}).get("selected_strategy")
        if selected:
            strategy = str(selected)
            break
    return {
        "result": meta.get("result"),
        "map_name": meta.get("map_name"),
        "matchup": meta.get("matchup"),
        "opponent_id": meta.get("opponent_id"),
        "strategy": strategy,
    }


def _build_record(
    *,
    batch_key: str,
    match_id: str,
    match_dir: Path,
    game_json: Path,
    llm_calls_json: Path,
    meta: Dict[str, Any],
    cycle_meta: Dict[str, Any],
    call: Dict[str, Any],
) -> Dict[str, Any]:
    opp = _parse_opponent(str(meta.get("opponent_id") or ""))
    rel_match_dir = match_dir.relative_to(ROOT).as_posix()
    rel_game_json = game_json.relative_to(ROOT).as_posix()
    rel_llm_calls_json = llm_calls_json.relative_to(ROOT).as_posix()
    prompt = call.get("prompt") or []
    system, user = _split_prompt(prompt)
    seq = call.get("seq")
    macro_cycle = call.get("macro_cycle")
    return {
        "record_id": f"{batch_key}/{match_id}/seq_{seq}/executor",
        "batch": batch_key,
        "match_id": match_id,
        "match_dir": rel_match_dir,
        "source_game_json": rel_game_json,
        "source_llm_calls_json": rel_llm_calls_json,
        "strategy": meta.get("strategy") or _parse_strategy_from_match_id(match_id),
        "game_result": meta.get("result"),
        "map_name": meta.get("map_name"),
        "matchup": meta.get("matchup"),
        "opponent_id": meta.get("opponent_id"),
        "enemy_race": opp["enemy_race"],
        "difficulty": opp["difficulty"],
        "macro_cycle": macro_cycle,
        "game_time": call.get("game_time"),
        "agent": "executor",
        "llm_call_seq": seq,
        "model_key": call.get("model_key"),
        "model": call.get("model"),
        "is_reasoning": call.get("is_reasoning"),
        "reasoning_source": call.get("reasoning_source"),
        "reasoning_extract_mode": call.get("reasoning_extract_mode"),
        "trigger_reason": cycle_meta.get("trigger_reason"),
        "strategy_step_number": cycle_meta.get("strategy_step_number"),
        "strategy_step_index": cycle_meta.get("strategy_step_index"),
        "strategy_step_is_last": cycle_meta.get("strategy_step_is_last"),
        "strategy_step_text": cycle_meta.get("strategy_step_text"),
        "observation_at_this_moment": cycle_meta.get("observation_at_this_moment"),
        "ability_to_execute": _parse_ability(system),
        "prompt": prompt,
        "system": system,
        "user": user,
        "cot": call.get("reasoning") or "",
        "answer": call.get("output") or "",
        "raw_content": call.get("raw_content") or "",
        "llm_error": call.get("error") or "",
        "pipeline_ordered_actions": cycle_meta.get("ordered_actions"),
    }


def extract_executor_qa(
    batch_dir: Path,
    strategies: Iterable[str],
) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    batch_key = batch_dir.name
    strategy_set = set(strategies)
    by_strategy: Dict[str, List[Dict[str, Any]]] = {s: [] for s in sorted(strategy_set)}
    stats: Dict[str, Any] = {
        "games_scanned": 0,
        "games_matched_strategy": 0,
        "games_missing_llm_calls": 0,
        "records_total": 0,
        "by_strategy": defaultdict(lambda: {"games": 0, "executor": 0}),
        "by_result": defaultdict(int),
    }

    for game_json in sorted(batch_dir.glob("*/*.json")):
        if game_json.name.endswith(".llm_calls.json"):
            continue
        stats["games_scanned"] += 1
        match_id = game_json.stem
        strategy = _parse_strategy_from_match_id(match_id)
        if strategy not in strategy_set:
            continue

        llm_calls_json = game_json.with_suffix(".llm_calls.json")
        if not llm_calls_json.is_file():
            stats["games_missing_llm_calls"] += 1
            continue

        stats["games_matched_strategy"] += 1
        match_dir = game_json.parent
        meta = _load_game_meta(game_json)
        if not meta.get("strategy"):
            meta["strategy"] = strategy
        cycle_info = _load_cycle_info(game_json)
        result = meta.get("result")
        if result:
            stats["by_result"][result] += 1

        game_records: List[Dict[str, Any]] = []
        payload = json.loads(llm_calls_json.read_text(encoding="utf-8"))
        for call in payload.get("calls") or []:
            if call.get("agent") != "executor":
                continue
            macro_cycle = call.get("macro_cycle")
            cycle_meta = cycle_info.get(int(macro_cycle), {}) if macro_cycle is not None else {}
            record = _build_record(
                batch_key=batch_key,
                match_id=match_id,
                match_dir=match_dir,
                game_json=game_json,
                llm_calls_json=llm_calls_json,
                meta=meta,
                cycle_meta=cycle_meta,
                call=call,
            )
            game_records.append(record)

        if game_records:
            stats["by_strategy"][strategy]["games"] += 1
            stats["by_strategy"][strategy]["executor"] += len(game_records)
            by_strategy[strategy].extend(game_records)
            stats["records_total"] += len(game_records)

    stats["by_strategy"] = {k: dict(v) for k, v in sorted(stats["by_strategy"].items())}
    stats["by_result"] = dict(stats["by_result"])
    return stats, by_strategy


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract executor-layer Q&A from game records.")
    parser.add_argument(
        "--batch-dir",
        type=Path,
        default=GAME_RECORDS / "qwen17b_grpo_naming_27b_exec_10strat_macro_r5",
        help="Path to a game_records batch directory.",
    )
    parser.add_argument(
        "--strategies",
        nargs="*",
        default=DEFAULT_STRATEGIES,
        help="Strategies to include (default: the six macro strategies).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: <batch-dir>/executor_qa_extract.json).",
    )
    args = parser.parse_args()

    batch_dir = args.batch_dir.resolve()
    output = args.output or (batch_dir / "executor_qa_extract.json")
    stats, by_strategy = extract_executor_qa(batch_dir, args.strategies)

    payload = {
        "metadata": {
            "batch": batch_dir.name,
            "extractor": "tools/extract_executor_qa.py",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategies": sorted(set(args.strategies)),
            "agents": ["executor"],
            "description": "Executor-layer Q&A extracted from in-game LLM calls (prompt, cot, answer).",
        },
        "stats": stats,
        "by_strategy": by_strategy,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output} ({stats['records_total']} executor records)")


if __name__ == "__main__":
    main()
