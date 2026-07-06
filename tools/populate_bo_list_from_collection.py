"""Populate BO_list/terran from a Terran BO collection run.

For each strategy folder in the collection dataset:
1. Pick the winning match at the highest difficulty (tie-break: longest order_list).
2. Resolve the sequence JSON by filename pattern (not results.json sequence_file).
3. Copy strategy_tools.py from SKILL/terran/<name>/.
4. Write order_list to BO_list/terran/<name>/BO.json.
5. Update BO_list/terran/registry.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

DIFFICULTY_RANK: Dict[str, int] = {
    "veryeasy": 0,
    "easy": 1,
    "medium": 2,
    "mediumhard": 3,
    "hard": 4,
    "harder": 5,
    "veryhard": 6,
}


@dataclass
class SelectedMatch:
    strategy: str
    bot_key: str
    opponent: str
    difficulty: str
    sequence_file: str
    order_list_len: int
    meta_result: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_skill_strategies(skill_root: Path) -> List[str]:
    registry_path = skill_root / "registry.json"
    if not registry_path.is_file():
        raise FileNotFoundError(f"SKILL registry not found: {registry_path}")
    registry = load_json(registry_path)
    strategies = registry.get("registered_strategies", [])
    if not strategies:
        raise RuntimeError(f"No registered_strategies in {registry_path}")
    return list(strategies)


def discover_collection_strategies(collection_root: Path) -> List[str]:
    strategies: List[str] = []
    for child in sorted(collection_root.iterdir()):
        if not child.is_dir():
            continue
        if (child / "results.json").is_file():
            strategies.append(child.name)
    return strategies


def resolve_sequence_candidates(
    sequences_dir: Path,
    bot_key: str,
    opponent: str,
    map_name: Optional[str] = None,
) -> List[Path]:
    pattern = f"{bot_key}-{opponent}_*.json"
    candidates = sorted(sequences_dir.glob(pattern))
    if map_name:
        needle = f"_{map_name}_"
        candidates = [path for path in candidates if needle in path.name]
    return candidates


def load_sequence(path: Path) -> Tuple[List[str], str]:
    data = load_json(path)
    order_list = data.get("order_list")
    if not isinstance(order_list, list) or not all(isinstance(x, str) for x in order_list):
        raise RuntimeError(f"{path} missing a valid order_list string array")
    meta = data.get("meta") or {}
    result = str(meta.get("result", ""))
    return order_list, result


def pick_best_sequence_file(
    sequences_dir: Path,
    bot_key: str,
    opponent: str,
    require_victory: bool,
    map_name: Optional[str] = None,
) -> Tuple[Path, List[str], str]:
    candidates = resolve_sequence_candidates(sequences_dir, bot_key, opponent, map_name=map_name)
    if not candidates:
        raise FileNotFoundError(
            f"No sequence JSON for {bot_key}-{opponent}_* under {sequences_dir}"
        )

    scored: List[Tuple[int, Path, List[str], str]] = []
    for path in candidates:
        order_list, result = load_sequence(path)
        if require_victory and result != "Victory":
            continue
        scored.append((len(order_list), path, order_list, result))

    if not scored and require_victory:
        for path in candidates:
            order_list, result = load_sequence(path)
            scored.append((len(order_list), path, order_list, result))

    if not scored:
        raise RuntimeError(f"Could not load any sequence for {bot_key}-{opponent}")

    scored.sort(key=lambda item: item[0], reverse=True)
    _, path, order_list, result = scored[0]
    return path, order_list, result


def select_match_for_strategy(
    strategy: str,
    collection_root: Path,
    enemy_race: Optional[str] = None,
    map_name: Optional[str] = None,
) -> SelectedMatch:
    results_path = collection_root / strategy / "results.json"
    if not results_path.is_file():
        raise FileNotFoundError(f"Missing results.json for strategy '{strategy}'")

    results = load_json(results_path)
    matches = results.get("matches", [])
    wins = [
        m for m in matches
        if m.get("victory") is True and m.get("status") == "ok"
    ]
    if enemy_race:
        wins = [m for m in wins if m.get("enemy_race") == enemy_race]
    if map_name:
        wins = [m for m in wins if m.get("map") == map_name]
    if not wins:
        raise RuntimeError(f"No winning matches for strategy '{strategy}'")

    max_rank = max(DIFFICULTY_RANK.get(m["difficulty"], -1) for m in wins)
    top_difficulty = [m for m in wins if DIFFICULTY_RANK.get(m["difficulty"], -1) == max_rank]

    sequences_dir = collection_root / strategy / "sequences"
    best: Optional[SelectedMatch] = None

    for match in top_difficulty:
        bot_key = match["bot_key"]
        opponent = match["opponent"]
        seq_path, order_list, meta_result = pick_best_sequence_file(
            sequences_dir,
            bot_key,
            opponent,
            require_victory=True,
            map_name=map_name,
        )
        selected = SelectedMatch(
            strategy=strategy,
            bot_key=bot_key,
            opponent=opponent,
            difficulty=match["difficulty"],
            sequence_file=str(seq_path),
            order_list_len=len(order_list),
            meta_result=meta_result,
        )
        if best is None or selected.order_list_len > best.order_list_len:
            best = selected

    if best is None:
        raise RuntimeError(f"Failed to select a match for strategy '{strategy}'")

    return best


def load_selected_order_list(selected: SelectedMatch) -> List[str]:
    order_list, _ = load_sequence(Path(selected.sequence_file))
    return order_list


def populate_strategy(
    strategy: str,
    collection_root: Path,
    bo_list_root: Path,
    skill_root: Path,
    dry_run: bool,
    enemy_race: Optional[str] = None,
    map_name: Optional[str] = None,
    skip_tools_copy: bool = False,
) -> SelectedMatch:
    selected = select_match_for_strategy(
        strategy,
        collection_root,
        enemy_race=enemy_race,
        map_name=map_name,
    )
    order_list = load_selected_order_list(selected)

    target_dir = bo_list_root / strategy
    bo_path = target_dir / "BO.json"
    tools_src = skill_root / strategy / "strategy_tools.py"
    tools_dst = target_dir / "strategy_tools.py"

    if not tools_src.is_file():
        raise FileNotFoundError(f"Missing strategy_tools.py: {tools_src}")

    print(
        f"{strategy:18} difficulty={selected.difficulty:10} "
        f"opponent={selected.opponent:25} "
        f"len={selected.order_list_len:4} "
        f"file={Path(selected.sequence_file).name}"
    )

    if dry_run:
        return selected

    target_dir.mkdir(parents=True, exist_ok=True)
    write_json(bo_path, order_list)
    if not skip_tools_copy or not tools_dst.is_file():
        shutil.copy2(tools_src, tools_dst)
    return selected


def update_registry(
    bo_list_root: Path,
    strategies: Sequence[str],
    dry_run: bool,
    append: bool = False,
) -> None:
    registry_path = bo_list_root / "registry.json"
    existing: List[str] = []
    if append and registry_path.is_file():
        registry = load_json(registry_path)
        existing = list(registry.get("registered_strategies", []))
    merged = existing[:]
    for strategy in strategies:
        if strategy not in merged:
            merged.append(strategy)
    registry = {
        "_comment": (
            "Terran BO-list strategies for --bo-list runs. Keep this list in sync "
            "with BO_list/terran/<strategy>/ directories. Each registered folder "
            "must contain BO.json and strategy_tools.py."
        ),
        "registered_strategies": list(merged if append else strategies),
    }
    if dry_run:
        print(f"[dry-run] would update registry with {len(strategies)} strategies")
        return
    write_json(registry_path, registry)


def write_manifest(bo_list_root: Path, selections: Sequence[SelectedMatch], dry_run: bool) -> None:
    manifest_path = bo_list_root / "populate_manifest.json"
    payload = {
        "selections": [asdict(item) for item in selections],
    }
    if dry_run:
        print(f"[dry-run] would write manifest to {manifest_path}")
        return
    write_json(manifest_path, payload)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    root = repo_root()
    default_collection = Path(r"C:\code\SC2_bot_data\bo_collection_runs\2026-06-16_terran_bo_commitfix_v5")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collection-root",
        type=Path,
        default=default_collection,
        help="Terran BO collection run root directory",
    )
    parser.add_argument(
        "--bo-list-root",
        type=Path,
        default=root / "BO_list" / "terran",
        help="Target BO_list/terran directory",
    )
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=root / "SKILL" / "terran",
        help="Source SKILL/terran directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print selections without writing files",
    )
    parser.add_argument(
        "--map",
        default=None,
        help="Only use matches/sequences from this map id (e.g. KairosJunctionLE).",
    )
    parser.add_argument(
        "--enemy-race",
        default=None,
        help="Only use winning matches against this opponent race (e.g. terran).",
    )
    parser.add_argument(
        "--strategies",
        nargs="*",
        default=None,
        help="Explicit strategy folder names to populate (overrides SKILL registry intersection).",
    )
    parser.add_argument(
        "--append-registry",
        action="store_true",
        help="Append new strategies to registry.json instead of replacing it.",
    )
    parser.add_argument(
        "--skip-tools-copy",
        action="store_true",
        help="Do not overwrite strategy_tools.py when it already exists.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    collection_root: Path = args.collection_root
    if args.map:
        collection_root = collection_root / args.map
    bo_list_root: Path = args.bo_list_root
    skill_root: Path = args.skill_root

    if not collection_root.is_dir():
        print(f"Collection root not found: {collection_root}", file=sys.stderr)
        return 1

    if args.strategies:
        strategies = list(args.strategies)
    else:
        skill_strategies = load_skill_strategies(skill_root)
        collection_strategies = discover_collection_strategies(collection_root)
        missing_in_collection = sorted(set(skill_strategies) - set(collection_strategies))
        if missing_in_collection:
            print(
                "Warning: SKILL strategies missing from collection: "
                + ", ".join(missing_in_collection),
                file=sys.stderr,
            )
        strategies = [s for s in skill_strategies if s in collection_strategies]
    if not strategies:
        print("No strategies selected for population.", file=sys.stderr)
        return 1

    print(f"Processing {len(strategies)} strategies from {collection_root}")
    if args.enemy_race:
        print(f"Opponent race filter: {args.enemy_race}")
    if args.map:
        print(f"Map filter: {args.map}")
    selections: List[SelectedMatch] = []
    for strategy in strategies:
        selections.append(
            populate_strategy(
                strategy=strategy,
                collection_root=collection_root,
                bo_list_root=bo_list_root,
                skill_root=skill_root,
                dry_run=args.dry_run,
                enemy_race=args.enemy_race,
                map_name=args.map,
                skip_tools_copy=args.skip_tools_copy,
            )
        )

    update_registry(bo_list_root, strategies, dry_run=args.dry_run, append=args.append_registry)
    write_manifest(bo_list_root, selections, dry_run=args.dry_run)

    if args.dry_run:
        print("[dry-run] complete; no files written")
    else:
        print(f"Done. Wrote BO_list entries under {bo_list_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
