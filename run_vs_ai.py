"""Run the summary-guided SC2 macro agent against the built-in AI."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime
from typing import List, Optional, Sequence

from sc2_runtime import ensure_bundled_python_sc2

ensure_bundled_python_sc2()

from bot_loader import BotDefinitions, GameStarter
from version import update_version_txt

OUTPUT_BASE_DIR = "./game_records"

DEFAULT_MY_BOT_NAME = "universal_llm"
DEFAULT_BOT_RACE = "terran"
DEFAULT_MAP_NAME = "KairosJunctionLE"
DEFAULT_REAL_TIME = False

DEFAULT_ENEMY_RACE = "terran"
DEFAULT_ENEMY_DIFFICULTY = "medium"
DEFAULT_ENEMY_BUILD = "random"

DEFAULT_DECISION_MODEL = "DeepSeek-V4-flash"
DEFAULT_DECISION_INTERVAL = 60.0
DEFAULT_FORCE_STRATEGY = "marine_rush"
DEFAULT_SKIP_VERSION_UPDATE = False


def _safe_match_part(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in ("-", "_") else "_"
        for char in str(value)
    )


def build_match_id(
    *,
    timestamp: str,
    my_bot_name: str,
    enemy_race: str,
    enemy_difficulty: str,
    enemy_build: str,
    map_name: str,
    bot_race: str,
    decision_model: str,
    decision_interval: float,
    run_index: Optional[int],
) -> str:
    # The directory remains human-readable while a digest keeps every omitted
    # parameter part of the identity.  A bounded id is essential on Windows:
    # the record directory and artifact filename used to repeat the same long
    # id and could exceed MAX_PATH before SC2 started.
    identity = "|".join(
        str(value)
        for value in (
            timestamp,
            my_bot_name,
            bot_race,
            enemy_race,
            enemy_difficulty,
            enemy_build,
            map_name,
            decision_model,
            float(decision_interval),
            run_index,
        )
    )
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10]
    matchup = (
        f"{_safe_match_part(bot_race)[:1].lower()}"
        f"v{_safe_match_part(enemy_race)[:1].lower()}"
    )
    value = "_".join(
        (
            _safe_match_part(timestamp)[:15],
            matchup,
            _safe_match_part(map_name)[:12],
            _safe_match_part(enemy_difficulty)[:6],
            digest,
        )
    )
    return f"{value}_run{run_index}" if run_index is not None else value


def play_vs_ai(
    *,
    my_bot_name: str = DEFAULT_MY_BOT_NAME,
    map_name: str = DEFAULT_MAP_NAME,
    real_time: bool = DEFAULT_REAL_TIME,
    enemy_race: str = DEFAULT_ENEMY_RACE,
    enemy_difficulty: str = DEFAULT_ENEMY_DIFFICULTY,
    enemy_build: str = DEFAULT_ENEMY_BUILD,
    bot_race: str = DEFAULT_BOT_RACE,
    decision_model: str = DEFAULT_DECISION_MODEL,
    decision_interval: float = DEFAULT_DECISION_INTERVAL,
    batch_name: Optional[str] = None,
    run_index: Optional[int] = None,
    output_base_dir: str = OUTPUT_BASE_DIR,
    skip_version_update: bool = DEFAULT_SKIP_VERSION_UPDATE,
    force_strategy: Optional[str] = None,
) -> None:
    strategy = (force_strategy or DEFAULT_FORCE_STRATEGY).strip()
    if not strategy or strategy.lower() == "none":
        raise ValueError("A fixed strategy folder is required.")
    if float(decision_interval) <= 0:
        raise ValueError("decision_interval must be greater than zero.")

    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)
    if not skip_version_update:
        update_version_txt()

    player_two = f"ai.{enemy_race}.{enemy_difficulty}.{enemy_build}"
    player_one = (
        f"{my_bot_name}.{bot_race}"
        if my_bot_name == "universal_llm"
        else my_bot_name
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    match_id = build_match_id(
        timestamp=timestamp,
        my_bot_name=my_bot_name,
        enemy_race=enemy_race,
        enemy_difficulty=enemy_difficulty,
        enemy_build=enemy_build,
        map_name=map_name,
        bot_race=bot_race,
        decision_model=decision_model,
        decision_interval=decision_interval,
        run_index=run_index,
    )
    base = os.path.abspath(output_base_dir)
    record_dir = (
        os.path.join(base, _safe_match_part(batch_name), match_id)
        if batch_name
        else os.path.join(base, match_id)
    )
    os.makedirs(record_dir, exist_ok=True)

    args: List[str] = [
        "run_custom.py",
        "-m",
        map_name,
        "-p1",
        player_one,
        "-p2",
        player_two,
        "--record-dir",
        record_dir,
        "--match-id",
        match_id,
        "--decision-model",
        decision_model,
        "--decision-interval",
        str(float(decision_interval)),
        "--force-strategy",
        strategy,
    ]
    if real_time:
        args.append("-rt")
    sys.argv = args

    print("==================================================")
    print(" 正在启动 SC2 Agent 对战...")
    print(f" ▷ 我方阵营 : {my_bot_name} ({bot_race})")
    print(
        f" ▷ 对手 AI  : {enemy_race.upper()} | "
        f"难度: {enemy_difficulty} | 风格: {enemy_build}"
    )
    print(f" ▷ 比赛地图 : {map_name}")
    print(f" ▷ 决策模型 : {decision_model}")
    print(f" ▷ 决策周期 : {float(decision_interval):g} 游戏秒")
    print(f" ▷ 固定策略 : {strategy}")
    print(f" ▷ 记录目录 : {record_dir}")
    print("==================================================")

    definitions = BotDefinitions(os.path.join(root_dir, "Bots"))
    GameStarter(definitions).play()


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the summary-guided SC2 macro agent.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--my-bot-name", default=DEFAULT_MY_BOT_NAME)
    parser.add_argument("--map-name", default=DEFAULT_MAP_NAME)
    parser.add_argument(
        "--real-time",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_REAL_TIME,
    )
    parser.add_argument("--enemy-race", default=DEFAULT_ENEMY_RACE)
    parser.add_argument("--enemy-difficulty", default=DEFAULT_ENEMY_DIFFICULTY)
    parser.add_argument("--enemy-build", default=DEFAULT_ENEMY_BUILD)
    parser.add_argument("--bot-race", default=DEFAULT_BOT_RACE)
    parser.add_argument("--decision-model", default=DEFAULT_DECISION_MODEL)
    parser.add_argument(
        "--decision-interval",
        type=float,
        default=DEFAULT_DECISION_INTERVAL,
        help="Macro replanning interval in in-game seconds.",
    )
    parser.add_argument("--force-strategy", default=DEFAULT_FORCE_STRATEGY)
    parser.add_argument("--batch-name", default="")
    parser.add_argument("--run-index", type=int, default=None)
    parser.add_argument("--output-base-dir", default=OUTPUT_BASE_DIR)
    parser.add_argument(
        "--skip-version-update",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_SKIP_VERSION_UPDATE,
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    play_vs_ai(
        my_bot_name=args.my_bot_name,
        map_name=args.map_name,
        real_time=args.real_time,
        enemy_race=args.enemy_race,
        enemy_difficulty=args.enemy_difficulty,
        enemy_build=args.enemy_build,
        bot_race=args.bot_race,
        decision_model=args.decision_model,
        decision_interval=args.decision_interval,
        batch_name=args.batch_name or None,
        run_index=args.run_index,
        output_base_dir=args.output_base_dir,
        skip_version_update=args.skip_version_update,
        force_strategy=args.force_strategy,
    )


if __name__ == "__main__":
    main()
