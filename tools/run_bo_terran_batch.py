"""Run all registered Terran BO-list strategies sequentially (Kimi-k2.5 executor)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_vs_ai

STRATEGIES = [
    "banshees",
    "battle_cruisers",
    "bio",
    "cyclones",
    "marine_rush",
    "one_base_turtle",
    "rusty",
    "terran_silver_bio",
    "two_base_tanks",
]

BATCH_NAME = "bo_terran_sweep"
_CURRENT_SLUG = "run"


def short_match_id(**kwargs):
    run_index = kwargs.get("run_index")
    suffix = f"_r{run_index}" if run_index is not None else ""
    return f"{kwargs['timestamp']}_{_CURRENT_SLUG}{suffix}"


def main() -> None:
    os.environ.setdefault("SC2_GAME_TIME_LIMIT", "1200")
    run_vs_ai.build_match_id = short_match_id

    total = len(STRATEGIES)
    for idx, name in enumerate(STRATEGIES, start=1):
        global _CURRENT_SLUG
        _CURRENT_SLUG = name.replace("_", "")[:16]
        print(f"\n{'=' * 60}")
        print(f"[{idx}/{total}] Starting BO list: {name}")
        print(f"{'=' * 60}\n")
        run_vs_ai.play_vs_ai(
            bo_list=name,
            executor_model="Kimi-k2.5",
            enemy_race="terran",
            enemy_difficulty="medium",
            enemy_build="random",
            batch_name=BATCH_NAME,
            run_index=idx,
            skip_version_update=True,
        )


if __name__ == "__main__":
    main()
