"""Run one pinned readable-skill agent against built-in SC2 AI."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime
from typing import Optional, Sequence

from sc2_runtime import ensure_bundled_python_sc2

ensure_bundled_python_sc2()

from bot_loader import BotDefinitions, GameStarter
from SC2_Agent.human_skill_common.variants import VARIANTS
from sc2.protocol import SC2MatchFatalError
from version import update_version_txt

DEFAULT_MODEL = "DeepSeek-V4-flash"
MATCH_FATAL_EXIT_CODE = 70


def _safe(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(value))


def _match_id(args: argparse.Namespace) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    identity = "|".join(
        str(value)
        for value in (
            stamp,
            args.bot_race,
            args.enemy_race,
            args.map_name,
            args.human_skill_agent,
            args.force_human_skill,
            args.decision_model,
            args.run_index,
        )
    )
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10]
    return f"{stamp}_{_safe(args.human_skill_agent)[:22]}_{digest}"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a hierarchical human-skill SC2 macro agent.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--human-skill-agent", choices=sorted(VARIANTS), default="human-skill-full")
    parser.add_argument("--force-human-skill", required=True)
    parser.add_argument("--human-skill-root", default="")
    parser.add_argument("--human-skill-api-config", default="")
    parser.add_argument("--decision-model", default=DEFAULT_MODEL)
    parser.add_argument("--decision-interval", type=float, default=60.0)
    parser.add_argument("--bot-race", choices=("protoss", "terran", "zerg"), default="protoss")
    parser.add_argument("--enemy-race", choices=("protoss", "terran", "zerg"), default="protoss")
    parser.add_argument("--enemy-difficulty", default="medium")
    parser.add_argument("--enemy-build", default="random")
    parser.add_argument("--map-name", default="Equilibrium513AIE")
    parser.add_argument("--real-time", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--output-base-dir", default="./game_records")
    parser.add_argument("--batch-name", default="human_skill")
    parser.add_argument("--run-index", type=int, default=None)
    parser.add_argument("--skip-version-update", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    if args.decision_interval <= 0:
        raise ValueError("decision interval must be positive")
    if "think" in args.decision_model.lower():
        raise ValueError("thinking model keys are forbidden for human-skill experiments")
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)
    if not args.skip_version_update:
        update_version_txt()
    match_id = _match_id(args)
    record_dir = os.path.abspath(os.path.join(args.output_base_dir, _safe(args.batch_name), match_id))
    os.makedirs(record_dir, exist_ok=True)
    sys.argv = [
        "run_custom.py",
        "-m",
        args.map_name,
        "-p1",
        f"universal_llm_human_skill.{args.bot_race}",
        "-p2",
        f"ai.{args.enemy_race}.{args.enemy_difficulty}.{args.enemy_build}",
        "--record-dir",
        record_dir,
        "--match-id",
        match_id,
        "--decision-model",
        args.decision_model,
        "--decision-agent-mode",
        "naive",
        "--decision-interval",
        str(args.decision_interval),
        "--human-skill-agent",
        args.human_skill_agent,
        "--force-human-skill",
        args.force_human_skill,
        "--human-skill-root",
        args.human_skill_root,
        "--human-skill-api-config",
        args.human_skill_api_config,
    ]
    if args.real_time:
        sys.argv.append("-rt")
    print("==================================================")
    print(f" Human Skill Agent: {args.human_skill_agent}")
    print(f" Skill ID / method: {args.force_human_skill} / {VARIANTS[args.human_skill_agent].method}")
    print(f" Model: {args.decision_model} (non-reasoning required)")
    print(f" Matchup: {args.bot_race} vs {args.enemy_race}")
    print(f" Records: {record_dir}")
    print("==================================================")
    try:
        GameStarter(BotDefinitions(os.path.join(root_dir, "Bots"))).play()
    except SC2MatchFatalError as exc:
        # asyncio.run() has already unwound the match-scoped SC2 context here.
        # Convert the non-business BaseException into an explicit retryable
        # child-process failure instead of allowing a manager to continue with
        # a dead transport or leaving the runner waiting indefinitely.
        print(f"FATAL_SC2_MATCH_TRANSPORT: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(MATCH_FATAL_EXIT_CODE) from exc


if __name__ == "__main__":
    main()
