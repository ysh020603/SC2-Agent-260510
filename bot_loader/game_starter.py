import glob
import os
import random
import argparse
from configparser import ConfigParser
from datetime import datetime
from typing import List, Optional, Dict

from bot_loader.bot_definitions import BotDefinitions, races, builds, difficulty
from config import get_config
import sc2
from bot_loader.runner import MatchRunner
from sc2 import maps
from sc2.data import Result
from sc2.paths import Paths
from sc2.player import AbstractPlayer, Bot, Human
from sharpy.knowledges import KnowledgeBot
from sharpy.tools import LoggingUtility

new_line = "\n"


def _is_human_player_spec(player_spec: str) -> bool:
    """Return whether a dotted player specification selects the real Human player.

    Bot identifiers are free-form and may legitimately contain the word
    ``human`` (for example ``universal_llm_human_skill.protoss``), so a
    substring test incorrectly turns those bot matches into realtime games.
    Only the registered top-level ``human`` player key denotes a person.
    """
    return player_spec.split(".", 1)[0].strip().lower() == "human"


def artifact_file_name(
    record_dir: Optional[str],
    match_id: Optional[str],
    fallback: str,
) -> str:
    """Choose a bounded artifact stem while preserving match uniqueness."""

    if record_dir:
        return "match"
    return match_id or fallback


# Used for random map selection
known_melee_maps = (
    "AbyssalReefLE",
    "AcolyteLE",
    "(2)RedshiftLE",
    "(2)DreamcatcherLE",
    "(2)LostandFoundLE",
    "AutomatonLE",
    "BlueshiftLE",
    "CeruleanFallLE",
    "DarknessSanctuaryLE",
    "KairosJunctionLE",
    "ParaSiteLE",
    "PortAleksanderLE",
    # "StasisLE", # Bugged map for bots
    "CyberForestLE",
    "KingsCoveLE",
    "NewRepugnancyLE",
    # Season 3 2019
    "AcropolisLE",
    "DiscoBloodbathLE",
    "EphemeronLE",
    "ThunderbirdLE",
    "TritonLE",
    "WintersGateLE",
    "WorldofSleepersLE",
    # Season 1 2020
    "SImulacrumLE",
    "ZenLE",
    "NightshadeLE",
)


class GameStarter:
    def __init__(self, definitions: BotDefinitions) -> None:
        self.config: ConfigParser = get_config()

        self.definitions = definitions
        self.players = definitions.playable
        self.random_bots = definitions.random_bots

        self.maps = GameStarter.installed_maps()
        self.random_maps = [x for x in known_melee_maps if x in self.maps]

    @staticmethod
    def installed_maps() -> List[str]:
        maps_folder = Paths.MAPS
        map_file_paths = glob.glob(f"{maps_folder}/**/*.SC2Map", recursive=True)

        def get_file_name(path) -> str:
            filename_w_ext = os.path.basename(path)
            filename, file_ext = os.path.splitext(filename_w_ext)
            return filename

        # Use a set to remove duplicate names (same map in multiple folders)
        map_file_names = set(map(get_file_name, map_file_paths))

        map_list = []
        for file_name in sorted(map_file_names):
            map_list.append(file_name)
        return map_list

    def play(self):
        # noinspection PyTypeChecker
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description="Run a game with custom parameters.",
            epilog=f"""\
Installed maps:
{new_line.join(sorted(self.maps))}

Bots:
{new_line.join(sorted(self.players.keys()))}


For ingame ai, use ai.race.difficulty.build where all arguments are optional
ingame ai defaults to ai.random.veryhard.random

Races:
{new_line.join(races.keys())}

Difficulties:
{new_line.join(difficulty.keys())}

Builds:
{new_line.join(builds.keys())}
                """,
        )

        parser.add_argument(
            "-m",
            "--map",
            help="Name of the map. Defaults to random. The script works with any map present in Starcraft 2 Maps directory.",
            default="random",
        )
        parser.add_argument(
            "-p1", "--player1", help="Name of player 1 bot or human. Defaults to random.", default="random"
        )
        parser.add_argument("-p2", "--player2", help="Name of player 2 bot. Defaults to random.", default="random")
        parser.add_argument("-rt", "--real-time", help="Use real-time mode.", action="store_true")
        parser.add_argument(
            "-r", "--release", help="Use only release config and ignore config local.", action="store_true"
        )
        parser.add_argument("-raw", "--raw_selection", help="Raw affects selection.", action="store_true")
        parser.add_argument(
            "--port", help="starting port to use, i.e. 10 would result in ports 10-17 being used to play."
        )

        parser.add_argument(
            "--requirewin", help="Requires victory for the specified player number (1 or 2) or raise exception."
        )
        parser.add_argument(
            "--record-dir",
            help="Directory where the log, replay, and LLM JSON for this match are written.",
        )
        parser.add_argument(
            "--match-id",
            help="File prefix for this match's log, replay, and LLM JSON.",
        )
        parser.add_argument(
            "--decision-model",
            help="Model key from config.json for the macro decision agent.",
            default="Kimi-k2.5",
        )
        parser.add_argument(
            "--data-subagent-model",
            help="Independent model key from config.json for DataSubAgent.",
            default="Kimi-k2.5",
        )
        parser.add_argument(
            "--decision-agent-mode",
            choices=("data-v2.3", "data-v2.3-no-knowledge", "data-v2.2-v2-no-knowledge", "data-v2.2-v2", "data-v2.2", "naive"),
            help="Macro decision orchestration mode.",
            default="data-v2.2",
        )
        parser.add_argument(
            "--decision-interval",
            type=float,
            help="Macro replanning interval in in-game seconds.",
            default=60.0,
        )
        parser.add_argument(
            "--force-strategy",
            help="Strategy folder name under SKILL/<race>/ for UniversalLLMBot.",
            default="",
        )
        parser.add_argument(
            "--human-skill-agent",
            choices=(
                "human-skill-full-v2",
                "human-skill-full",
                "human-skill-single-trace",
                "human-skill-static-population",
                "human-skill-flat-adaptive",
                "human-skill-positive-only",
                "human-skill-frequency-only",
            ),
            default="human-skill-full",
        )
        parser.add_argument(
            "--force-human-skill",
            help="Pinned readable opening id, for example PvP_O01.",
            default="",
        )
        parser.add_argument(
            "--human-skill-root",
            help="Override the SKILL_MINING_V2_READABLE root.",
            default="",
        )
        parser.add_argument(
            "--human-skill-api-config",
            help="Override API_config/config.json (must define a non-reasoning model).",
            default="",
        )

        args = parser.parse_args()

        player1: str = args.player1

        if player1 == "random":
            player1 = random.choice(list(self.random_bots.keys()))
        elif _is_human_player_spec(player1):
            args.real_time = True
            args.release = True

        map_name = args.map
        if map_name == "random":
            map_name = random.choice(self.random_maps)

        if map_name not in self.maps:
            print(f"map not in Maps:{new_line}{new_line.join(self.maps)}")
            return

        player2: str = args.player2
        if player2 == "random":
            player2 = random.choice(list(self.random_bots.keys()))

        player2_split: List[str] = player2.split(".")
        player2_type: str = player2_split.pop(0)

        player1_split: List[str] = player1.split(".")
        player1_type: str = player1_split.pop(0)

        if player1_type not in self.definitions.player1:
            keys = list(self.definitions.player1.keys())
            print(f"Player1 type {player1} not found in:{new_line} {new_line.join(keys)}")
            return

        player2_bot: Optional[AbstractPlayer]

        if player2_type not in self.definitions.player2:
            keys = list(self.definitions.player2.keys())
            print(f"Enemy type {player2_type} not found in player types:{new_line}{new_line.join(keys)}")
            return
        else:
            player2_bot = self.players[player2_type](player2_split)

        player1_bot: AbstractPlayer = self.players[player1_type](player1_split)

        folder = os.path.abspath(args.record_dir) if args.record_dir else "game_records"
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)

        if not args.record_dir and not args.match_id:
            time = datetime.now().strftime("%Y-%m-%d %H_%M_%S")
            randomizer = random.randint(0, 999999)
            # Randomizer is to make it less likely that games started at the same time have same name
            fallback_file_name = f"{player2}_{map_name}_{time}_{randomizer}"
        else:
            fallback_file_name = "match"
        # The enclosing record directory already carries the unique match id.
        # Do not repeat it in every artifact filename: on Windows the doubled
        # path can exceed MAX_PATH even when each component is individually
        # valid.
        file_name = artifact_file_name(
            args.record_dir,
            args.match_id,
            fallback_file_name,
        )
        path = os.path.join(folder, f"{file_name}.log")

        if self.config.getboolean("general", "log_file"):
            LoggingUtility.set_logger_file(log_level=self.config["general"]["log_level"], path=path)
        else:
            LoggingUtility.set_logger(log_level=self.config["general"]["log_level"])

        GameStarter.setup_bot(player1_bot, player1, player2, args)
        GameStarter.setup_bot(player2_bot, player2, player1, args)

        print(f"Starting game in {map_name}.")
        print(f"{player1} vs {player2}")
        print(
            f"Match mode: realtime={args.real_time} "
            f"player1_spec={player1} human={_is_human_player_spec(player1)}"
        )

        replay_path = os.path.join(folder, f"{file_name}.SC2Replay")
        # Tell each bot's LLMObservationRecorder where the replay will land so
        # that the JSON observation file is written with the exact same prefix
        # in the exact same folder.
        GameStarter._set_recorder_replay_path(player1_bot, replay_path)
        GameStarter._set_recorder_replay_path(player2_bot, replay_path)

        runner = MatchRunner()
        # Game length cap in seconds. Default 30 game-minutes; override via the
        # SC2_GAME_TIME_LIMIT env var (useful for short smoke tests).
        try:
            _time_limit = int(float(os.environ.get("SC2_GAME_TIME_LIMIT", 30 * 60)))
        except (TypeError, ValueError):
            _time_limit = 30 * 60
        result = runner.run_game(
            maps.get(map_name),
            [player1_bot, player2_bot],
            player1_id=player1,
            realtime=args.real_time,
            game_time_limit=_time_limit,
            save_replay_as=replay_path,
            start_port=args.port,
        )

        if args.requirewin:
            if args.requirewin == "1" and result != Result.Victory:
                raise Exception("Player 1 needed to win the game!")
            if args.requirewin == "2" and result != Result.Defeat:
                raise Exception("Player 2 needed to win the game!")
        # release file handle
        sc2.main.logger.remove()

    @staticmethod
    def setup_bot(player: AbstractPlayer, bot_code, enemy_text: str, args):
        if isinstance(player, Human):
            player.fullscreen = True
        if isinstance(player, Bot) and hasattr(player.ai, "config"):
            my_bot: KnowledgeBot = player.ai
            my_bot.opponent_id = bot_code + "-" + enemy_text
            my_bot.run_custom = True
            my_bot.raw_affects_selection = args.raw_selection
            if getattr(args, "record_dir", None):
                record_dir = os.path.abspath(args.record_dir)
                if hasattr(my_bot, "record_dir"):
                    my_bot.record_dir = record_dir
                recorder = getattr(my_bot, "llm_observation_recorder", None)
                if recorder is not None:
                    recorder.output_folder = record_dir
            if getattr(args, "decision_model", None) and hasattr(my_bot, "decision_model_key"):
                my_bot.decision_model_key = args.decision_model
            if getattr(args, "data_subagent_model", None) and hasattr(my_bot, "data_subagent_model_key"):
                my_bot.data_subagent_model_key = args.data_subagent_model
            if hasattr(my_bot, "decision_agent_mode"):
                my_bot.decision_agent_mode = args.decision_agent_mode
            if getattr(args, "decision_interval", None) and hasattr(my_bot, "decision_interval_seconds"):
                my_bot.decision_interval_seconds = float(args.decision_interval)
            if hasattr(my_bot, "force_strategy"):
                fs = (getattr(args, "force_strategy", "") or "").strip()
                my_bot.force_strategy = fs if fs and fs.lower() != "none" else None
            if hasattr(my_bot, "human_skill_agent"):
                my_bot.human_skill_agent = args.human_skill_agent
            if hasattr(my_bot, "force_human_skill"):
                hs = (getattr(args, "force_human_skill", "") or "").strip()
                my_bot.force_human_skill = hs or None
                my_bot.force_strategy = hs or None
            if hasattr(my_bot, "human_skill_root"):
                my_bot.human_skill_root = (getattr(args, "human_skill_root", "") or "").strip()
            if hasattr(my_bot, "api_config_path"):
                my_bot.api_config_path = (
                    getattr(args, "human_skill_api_config", "") or ""
                ).strip()
            if args.release:
                my_bot.config = get_config(False)

    @staticmethod
    def _set_recorder_replay_path(player: AbstractPlayer, replay_path: str) -> None:
        """Forward the SC2Replay save path to the bot's LLM observation recorder.

        Done with ``hasattr`` so non-KnowledgeBot players (Human, ladder bots,
        in-game AI) are silently skipped.
        """
        if not isinstance(player, Bot):
            return
        recorder = getattr(player.ai, "llm_observation_recorder", None)
        if recorder is not None:
            recorder.replay_save_path = replay_path
