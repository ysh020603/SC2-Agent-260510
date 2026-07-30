"""Summary-guided, periodically replanned StarCraft II macro bot.

One LLM call produces a public reason and a complete ordered list of canonical
names.  Each accepted response atomically replaces local work that has not yet
been committed to the SC2 simulation.  Producer/worker selection is entirely
deterministic and owned by the execution layer.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import time as _wall_time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from sc2.data import Race

from sharpy.interfaces import IZoneManager
from sharpy.knowledges import KnowledgeBot
from sharpy.managers.core import ManagerBase
from sharpy.managers.extensions.build_detector import BuildDetector
from sharpy.plans import BuildOrder, SequentialList
from sharpy.plans.acts import ActBase

from API_Tools.llm_caller import call_openai_detailed
from SC2_Agent.data_tools import (
    ActionCandidate,
    action_candidates_for_entity,
    canonical_race_entity_name,
    normalize_race,
    race_prompt_context,
    race_unit_names,
    race_upgrade_names,
)
from SC2_Agent.decision_agent import (
    MacroDecision,
    build_decision_messages,
    parse_decision_response,
)
from SC2_Agent.execution.scheduler import ExecutionScheduler
from SC2_Agent.prompt_context import StrategyAutomationProfile
from SC2_Agent.strategy_registry import require_enabled_strategy
from SC2_Agent.top_agent import parse_strategy_summary

logger = logging.getLogger("UniversalLLMBot")

class UniversalLLMBot(KnowledgeBot):
    """Single-decision-agent macro runtime."""

    DEFAULT_DECISION_INTERVAL_SECONDS: float = 60.0
    MIN_RETRIGGER_SECONDS: float = 5.0
    WAIT_ABANDON_SECONDS: float = 60.0

    zone_manager: IZoneManager

    def __init__(
        self,
        race_name: str = "terran",
        record_dir: str = "",
        *,
        decision_model_key: str = "",
        decision_interval_seconds: float = DEFAULT_DECISION_INTERVAL_SECONDS,
        force_strategy: Optional[str] = None,
    ):
        super().__init__("Universal LLM Bot")
        self.race_name = normalize_race(race_name)
        self.record_dir = record_dir.strip()
        self.decision_model_key = decision_model_key.strip()
        self.decision_interval_seconds = max(1.0, float(decision_interval_seconds))
        force = (force_strategy or "").strip()
        self.force_strategy = force if force and force.lower() != "none" else None

        self.selected_strategy: Optional[str] = None
        self.strategy_summary: str = ""
        self.strategy_automation_context: str = ""
        self.strategy_enemy_race: str = ""

        self.scheduler: Optional[ExecutionScheduler] = None
        self._last_decision_time = -self.decision_interval_seconds
        self._decision_cycle_count = 0
        self._accepted_queue_count = 0
        self._queue_had_work_since_decision = False
        self._last_drained_state = True

        self._llm_call_records: List[Dict[str, Any]] = []
        self._llm_call_seq = 0
        if self.record_dir:
            self.llm_observation_recorder.output_folder = self.record_dir

    @property
    def _skill_root(self) -> str:
        return os.path.normpath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                os.pardir,
                os.pardir,
                "SKILL",
            )
        )

    @property
    def _skill_race_dir(self) -> str:
        return os.path.join(self._skill_root, self.race_name)

    def configure_managers(self) -> Optional[List[ManagerBase]]:
        return [BuildDetector()]

    async def on_start(self):
        if not self.force_strategy:
            raise ValueError("UniversalLLMBot requires --force-strategy.")
        self.decision_interval_seconds = max(1.0, float(self.decision_interval_seconds))
        self._last_decision_time = -self.decision_interval_seconds
        self._apply_forced_strategy(self.force_strategy)
        await super().on_start()
        self.zone_manager = self.knowledge.get_required_manager(IZoneManager)
        self.llm_observation_recorder.interval_seconds = self.decision_interval_seconds
        if self.record_dir:
            self.llm_observation_recorder.output_folder = self.record_dir

    async def on_end(self, game_result):
        try:
            await super().on_end(game_result)
        finally:
            self._flush_llm_call_log()

    async def pre_step_execute(self):
        if self.scheduler is None:
            return

        now = float(self.time)
        drained = self.scheduler.is_drained()
        trigger_reason = self._decision_trigger(now=now, drained=drained)

        if trigger_reason is None:
            self._last_drained_state = drained
            return

        self._last_decision_time = now
        self._run_decision_pipeline_blocking(trigger_reason=trigger_reason)
        self._last_drained_state = self.scheduler.is_drained()

    def _decision_trigger(self, *, now: float, drained: bool) -> Optional[str]:
        since = now - self._last_decision_time
        if self._decision_cycle_count == 0:
            return "initial_decision"
        if since >= self.decision_interval_seconds:
            return "interval_elapsed"
        if (
            self._queue_had_work_since_decision
            and drained
            and not self._last_drained_state
            and since >= self.MIN_RETRIGGER_SECONDS
        ):
            return "queue_drained"
        return None

    def _strategy_enemy_race_name(self) -> str:
        race = getattr(self, "enemy_race", None)
        if race is None:
            race = getattr(getattr(self, "ai", None), "enemy_race", None)
        if isinstance(race, Race):
            if race in (Race.Terran, Race.Protoss, Race.Zerg):
                return race.name.lower()
            raise ValueError(f"Unsupported enemy race: {race.name}")
        race_name = str(race or "").split(".")[-1].strip().lower()
        if race_name not in {"terran", "protoss", "zerg"}:
            raise ValueError(f"Unsupported enemy race: {race!r}")
        return race_name

    def _apply_forced_strategy(self, name: str) -> None:
        name = require_enabled_strategy(self.race_name, name)
        target_dir = os.path.join(self._skill_race_dir, name)
        enemy_race = self._strategy_enemy_race_name()
        filename = "Top_agent.md"
        path = os.path.join(target_dir, filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Strategy summary file not found: {path}")
        with open(path, "r", encoding="utf-8") as handle:
            summary = parse_strategy_summary(handle.read())
        if not summary:
            raise ValueError(f"Strategy summary is empty: {path}")
        module_path = f"SKILL.{self.race_name}.{name}.strategy_tools"
        module = importlib.import_module(module_path)
        profile = getattr(module, "AUTOMATION_PROFILE", None)
        if not isinstance(profile, StrategyAutomationProfile):
            raise ValueError(
                f"Enabled strategy must export AUTOMATION_PROFILE: {module_path}"
            )
        if profile.race != self.race_name or profile.strategy != name:
            raise ValueError(
                f"Automation profile identity mismatch in {module_path}: "
                f"{profile.race}/{profile.strategy}"
            )
        self.selected_strategy = name
        self.strategy_summary = summary
        self.strategy_automation_context = profile.render()
        self.strategy_enemy_race = enemy_race
        self._llm_infer_emit(
            f">>> STRATEGY: forced '{name}' vs {enemy_race} from {filename} "
            f"(summary={len(summary)} chars)"
        )
        self._record_llm_interaction(
            {
                "schema_version": 2,
                "game_time": 0.0,
                "trigger_reason": "forced_strategy",
                "strategy": {
                    "race": self.race_name,
                    "enemy_race": enemy_race,
                    "selected_strategy": name,
                    "strategy_file": filename,
                    "strategy_summary": summary,
                    "automation_profile": self.strategy_automation_context,
                },
            }
        )

    def _run_decision_pipeline_blocking(self, *, trigger_reason: str) -> None:
        assert self.scheduler is not None
        game_time = float(self.time)
        started = _wall_time.monotonic()
        self._decision_cycle_count += 1
        old_names = self.scheduler.uncommitted_canonical_names()
        obs_text = ""
        obs_snapshot: Optional[Dict[str, Any]] = None
        raw_response = ""
        api_result: Dict[str, Any] = {}
        parsed: Optional[MacroDecision] = None

        record: Dict[str, Any] = {
            "schema_version": 2,
            "cycle": self._decision_cycle_count,
            "game_time": round(game_time, 2),
            "trigger_reason": trigger_reason,
            "decision_interval_seconds": self.decision_interval_seconds,
            "strategy": {
                "name": self.selected_strategy,
                "summary": self.strategy_summary,
            },
            "old_uncommitted_canonical_names": list(old_names),
        }
        self._llm_infer_emit(
            f">>> DECISION START cycle={self._decision_cycle_count} "
            f"trigger={trigger_reason} game_time={game_time:.1f}s"
        )
        self._llm_infer_emit(
            "    OLD UNCOMMITTED CANONICAL NAMES: "
            + json.dumps(old_names, ensure_ascii=False)
        )

        try:
            obs_text, obs_snapshot = self._capture_observation_bundle()
            record["observation_at_this_moment"] = obs_text
            record["observation_structured"] = obs_snapshot
            messages = build_decision_messages(
                race=self.race_name,
                strategy_summary=self.strategy_summary,
                obs_text=obs_text,
                unfinished_canonical_names=old_names,
                canonical_unit_names=race_unit_names(self.race_name),
                canonical_upgrade_names=race_upgrade_names(self.race_name),
                race_context=race_prompt_context(self.race_name),
                strategy_automation_context=self.strategy_automation_context,
                decision_cycle=self._decision_cycle_count,
                trigger_reason=trigger_reason,
                game_time_seconds=game_time,
                decision_interval_seconds=self.decision_interval_seconds,
                enemy_race=self.strategy_enemy_race,
            )
            api_result = call_openai_detailed(
                messages=messages,
                model_key=self.decision_model_key,
            )
            raw_response = str(api_result.get("content") or "")
            parsed = parse_decision_response(raw_response)
            if parsed is None:
                record["error"] = "invalid_decision_response_keep_old_queue"
                self._llm_infer_emit(
                    "    DECISION INVALID: old uncommitted queue remains active"
                )
                return

            valid_names: List[str] = []
            dropped_unknown: List[str] = []
            for name in parsed.ordered_names:
                canonical_name = canonical_race_entity_name(self.race_name, name)
                if canonical_name is None:
                    dropped_unknown.append(name)
                else:
                    valid_names.append(canonical_name)

            mapped: List[Tuple[str, ActionCandidate, Tuple[ActionCandidate, ...]]] = []
            dropped_unmapped: List[str] = []
            for name in valid_names:
                candidates = self._action_candidates_for_entity(name)
                if candidates:
                    mapped.append((name, candidates[0], tuple(candidates[1:])))
                else:
                    dropped_unmapped.append(name)

            if parsed.ordered_names and not mapped:
                record["error"] = "no_valid_mapped_tasks_keep_old_queue"
                record["decision"] = {
                    "reason": parsed.reason,
                    "raw_response": raw_response,
                    "ordered_names": parsed.ordered_names,
                    "dropped_unknown_names": dropped_unknown,
                    "dropped_unmapped_names": dropped_unmapped,
                }
                self._llm_infer_emit(
                    "    DECISION MAPPING EMPTY: old uncommitted queue remains active"
                )
                return

            self._accepted_queue_count += 1
            queue_id = self._accepted_queue_count
            replaced_names = self.scheduler.replace_uncommitted_queue(
                mapped,
                queue_id=queue_id,
            )
            new_names = [name for name, _action, _alternatives in mapped]
            carried, discarded, introduced = self._queue_transition(
                replaced_names,
                new_names,
            )
            self._queue_had_work_since_decision = bool(new_names)
            record["queue_id"] = queue_id
            record["decision"] = {
                "reason": parsed.reason,
                "raw_response": raw_response,
                "ordered_names": parsed.ordered_names,
                "accepted_ordered_names": new_names,
                "dropped_unknown_names": dropped_unknown,
                "dropped_unmapped_names": dropped_unmapped,
                "mapped_actions": [
                    {
                        "canonical_name": name,
                        "action": action.ability_name,
                        "execution_mode": action.execution_mode,
                        "alternative_actions": [
                            alternative.ability_name for alternative in alternatives
                        ],
                    }
                    for name, action, alternatives in mapped
                ],
            }
            record["queue_transition"] = {
                "new_queue_id": queue_id,
                "carried_forward_names": carried,
                "discarded_old_names": discarded,
                "newly_introduced_names": introduced,
            }
            record["new_queue"] = {
                "queue_id": queue_id,
                "canonical_names": new_names,
            }
            record["all_uncommitted_canonical_names_after"] = (
                self.scheduler.uncommitted_canonical_names()
            )
            record["committed_work_untouched"] = True
            self._llm_infer_emit(f"    DECISION REASON: {parsed.reason}")
            self._llm_infer_emit(
                "    NEW QUEUE: " + json.dumps(new_names, ensure_ascii=False)
            )
            self._llm_infer_emit(
                "    DISCARDED OLD: " + json.dumps(discarded, ensure_ascii=False)
            )
        except Exception as exc:
            record["error"] = repr(exc)
            logger.warning("[UniversalLLMBot] decision pipeline failed: %s", exc)
            self._llm_infer_emit(
                f"    DECISION EXCEPTION: {exc!r}; old uncommitted queue remains active"
            )
        finally:
            if "messages" in locals():
                self._record_llm_call(
                    messages=messages,
                    output=raw_response,
                    llm_result=api_result,
                    decision=parsed,
                )
            record["wall_elapsed_seconds"] = round(
                _wall_time.monotonic() - started,
                3,
            )
            self._record_llm_interaction(record)
            self._llm_infer_emit(
                f"<<< DECISION END elapsed={record['wall_elapsed_seconds']:.2f}s"
            )

    @staticmethod
    def _queue_transition(
        old_names: List[str],
        new_names: List[str],
    ) -> Tuple[List[str], List[str], List[str]]:
        new_remaining = Counter(new_names)
        carried: List[str] = []
        discarded: List[str] = []
        for name in old_names:
            if new_remaining[name] > 0:
                carried.append(name)
                new_remaining[name] -= 1
            else:
                discarded.append(name)

        old_remaining = Counter(old_names)
        introduced: List[str] = []
        for name in new_names:
            if old_remaining[name] > 0:
                old_remaining[name] -= 1
            else:
                introduced.append(name)
        return carried, discarded, introduced

    def _action_candidates_for_entity(self, entity_name: str) -> List[ActionCandidate]:
        try:
            return action_candidates_for_entity(self.race_name, entity_name)
        except Exception as exc:
            logger.debug("action candidate lookup failed for %s: %s", entity_name, exc)
            return []

    def _capture_observation_bundle(self) -> Tuple[str, Optional[Dict[str, Any]]]:
        recorder = getattr(self, "llm_observation_recorder", None)
        if recorder is None:
            return "(LLMObservationRecorder unavailable)", None
        try:
            snapshot = recorder._build_snapshot()
            return recorder._generate_english_text_obs(snapshot), snapshot
        except Exception as exc:
            logger.warning("[UniversalLLMBot] failed to build observation: %s", exc)
            return "(observation unavailable)", None

    def _record_llm_call(
        self,
        *,
        messages: List[Dict[str, str]],
        output: str,
        llm_result: Dict[str, Any],
        decision: Optional[MacroDecision],
    ) -> None:
        self._llm_call_seq += 1
        self._llm_call_records.append(
            {
                "seq": self._llm_call_seq,
                "game_time": round(float(getattr(self, "time", 0.0)), 2),
                "decision_cycle": self._decision_cycle_count,
                "agent": "macro_decision",
                "model_key": self.decision_model_key,
                "model": llm_result.get("model", ""),
                "is_reasoning": llm_result.get("is_reasoning"),
                "prompt": list(messages),
                "output": output,
                "decision_reason": decision.reason if decision else "",
                "ordered_names": decision.ordered_names if decision else [],
                "provider_reasoning": llm_result.get("reasoning", "") or "",
                "reasoning_source": llm_result.get("reasoning_source", "none") or "none",
                "reasoning_extract_mode": llm_result.get(
                    "reasoning_extract_mode",
                    "none",
                ),
                "raw_content": llm_result.get("raw_content", "") or "",
                "error": llm_result.get("error", "") or "",
            }
        )
        self._flush_llm_call_log()

    def _llm_call_log_path(self) -> Optional[str]:
        recorder = getattr(self, "llm_observation_recorder", None)
        if recorder is None:
            return None
        try:
            base = recorder._resolve_output_path()
        except Exception:
            return None
        root, _ext = os.path.splitext(base)
        return root + ".llm_calls.json"

    def _flush_llm_call_log(self) -> None:
        path = self._llm_call_log_path()
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "match": os.path.basename(path)[: -len(".llm_calls.json")],
                        "llm_call_count": len(self._llm_call_records),
                        "calls": self._llm_call_records,
                    },
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as exc:
            logger.debug("failed to flush llm_calls log: %s", exc)

    def _record_llm_interaction(self, record: Dict[str, Any]) -> None:
        recorder = getattr(self, "llm_observation_recorder", None)
        append = getattr(recorder, "record_llm_interaction", None)
        if append is None:
            return
        try:
            append(record)
        except Exception as exc:
            logger.warning("failed to record LLM interaction: %s", exc)

    def _llm_infer_emit(self, message: str) -> None:
        line = f"[UniversalLLMBot][LLM-INFER] {message}"
        try:
            self.knowledge.print(line, stats=False)
            return
        except Exception:
            pass
        try:
            from sc2.main import logger as loguru_logger

            loguru_logger.patch(
                lambda record: record.update(name="sharpy.universal_llm_bot")
            ).opt(depth=1).info(line)
        except Exception:
            logger.info("%s", line)

    async def create_plan(self) -> BuildOrder:
        self.scheduler = ExecutionScheduler(
            wait_abandon_sec=self.WAIT_ABANDON_SECONDS,
        )
        return BuildOrder(
            [
                self.scheduler,
                self._load_strategy_tools(),
            ]
        )

    def _load_strategy_tools(self) -> BuildOrder:
        if not self.selected_strategy:
            raise RuntimeError("Strategy tools requested before strategy selection.")
        module_path = f"SKILL.{self.race_name}.{self.selected_strategy}.strategy_tools"
        tactics = self._instantiate_tactics_from_module(module_path)
        if tactics is None:
            raise RuntimeError(
                f"Enabled strategy tools failed to load: {module_path}"
            )
        self._llm_infer_emit(f"    [StrategyTools] loaded from {module_path}")
        return tactics

    @staticmethod
    def _instantiate_tactics_from_module(module_path: str) -> Optional[BuildOrder]:
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            return None
        except Exception as exc:
            logger.warning("Error importing tactics module %s: %s", module_path, exc)
            return None
        factory = getattr(module, "create_strategy_tools", None)
        if callable(factory):
            try:
                result = factory()
                if isinstance(result, BuildOrder):
                    return result
            except Exception as exc:
                logger.warning("Failed to call strategy tools factory in %s: %s", module_path, exc)
                return None
        for name in dir(module):
            value = getattr(module, name)
            if not isinstance(value, type):
                continue
            if not (
                (issubclass(value, BuildOrder) and value is not BuildOrder)
                or (issubclass(value, SequentialList) and value is not SequentialList)
            ):
                continue
            try:
                return value()
            except TypeError:
                try:
                    return value(20)
                except Exception as exc:
                    logger.warning("Failed to instantiate %s: %s", name, exc)
        return None


class LadderBot(UniversalLLMBot):
    def my_race(self):
        return {
            "terran": Race.Terran,
            "zerg": Race.Zerg,
            "protoss": Race.Protoss,
            "random": Race.Random,
        }.get(self.race_name, Race.Terran)
