"""BO list safe_tvt_raven with Kimi-k2.5 executor (no thinking)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_vs_ai


def short_match_id(**kwargs):
    return f"{kwargs['timestamp']}_safe_raven_kimi"


def main() -> None:
    os.environ.setdefault("SC2_GAME_TIME_LIMIT", "1200")
    run_vs_ai.build_match_id = short_match_id
    run_vs_ai.play_vs_ai(
        bo_list="safe_tvt_raven",
        executor_model="Kimi-k2.5",
        enemy_race="terran",
        enemy_difficulty="medium",
        enemy_build="random",
        batch_name="bo_safe_tvt_raven_kimi",
        skip_version_update=True,
    )


if __name__ == "__main__":
    main()
