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

NAIVE_DECISION_AGENT_MODE = "naive"
KNOWLEDGE_V22_DECISION_AGENT_MODE = "data-v2.2"
KNOWLEDGE_V22_V2_DECISION_AGENT_MODE = "data-v2.2-v2"
KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE = "data-v2.2-v2-no-knowledge"
KNOWLEDGE_V23_DECISION_AGENT_MODE = "data-v2.3"
KNOWLEDGE_V23_NO_KNOWLEDGE_DECISION_AGENT_MODE = "data-v2.3-no-knowledge"
PLAN_EXECUTE_DECISION_AGENT_MODE = "plan-execute"
SELF_REFINE_DECISION_AGENT_MODE = "self-refine"
SUNTZU_DECISION_AGENT_MODE = "suntzu"
HIMA_DECISION_AGENT_MODE = "hima"
COS_DECISION_AGENT_MODE = "cos"
SUPPORTED_DECISION_AGENT_MODES = {
    NAIVE_DECISION_AGENT_MODE,
    KNOWLEDGE_V22_DECISION_AGENT_MODE,
    KNOWLEDGE_V22_V2_DECISION_AGENT_MODE,
    KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE,
    KNOWLEDGE_V23_DECISION_AGENT_MODE,
    KNOWLEDGE_V23_NO_KNOWLEDGE_DECISION_AGENT_MODE,
    PLAN_EXECUTE_DECISION_AGENT_MODE,
    SELF_REFINE_DECISION_AGENT_MODE,
    SUNTZU_DECISION_AGENT_MODE,
    HIMA_DECISION_AGENT_MODE,
    COS_DECISION_AGENT_MODE,
}
STRUCTURAL_BASELINE_DECISION_AGENT_MODES = {
    PLAN_EXECUTE_DECISION_AGENT_MODE,
    SELF_REFINE_DECISION_AGENT_MODE,
    SUNTZU_DECISION_AGENT_MODE,
    HIMA_DECISION_AGENT_MODE,
    COS_DECISION_AGENT_MODE,
}
DEFAULT_KNOWLEDGE_MODEL_KEY = "Kimi-k2.5"

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
        decision_model_key: str = DEFAULT_KNOWLEDGE_MODEL_KEY,
        data_subagent_model_key: str = DEFAULT_KNOWLEDGE_MODEL_KEY,
        decision_agent_mode: str = KNOWLEDGE_V22_DECISION_AGENT_MODE,
        decision_interval_seconds: float = DEFAULT_DECISION_INTERVAL_SECONDS,
        force_strategy: Optional[str] = None,
    ):
        super().__init__("Universal LLM Bot")
        self.race_name = normalize_race(race_name)
        self.record_dir = record_dir.strip()
        self.decision_model_key = decision_model_key.strip()
        self.data_subagent_model_key = data_subagent_model_key.strip()
        self.decision_agent_mode = str(decision_agent_mode).strip().lower()
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
        self._knowledge_v2_2_v2_planner_state: Dict[str, Any] = {}
        self._knowledge_v2_2_v2_ledger: Dict[str, Any] = {"facts": {}}
        self._knowledge_v2_2_v2_no_knowledge_planner_state: Dict[str, Any] = {}
        self._knowledge_v2_2_v2_no_knowledge_ledger: Dict[str, Any] = {"facts": {}}
        self._knowledge_v2_3_planner_state: Dict[str, Any] = {}
        self._knowledge_v2_3_ledger: Dict[str, Any] = {"facts": {}}
        self._knowledge_v2_3_no_knowledge_planner_state: Dict[str, Any] = {}
        self._knowledge_v2_3_no_knowledge_ledger: Dict[str, Any] = {"facts": {}}
        self._cos_state = None

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
        if self.decision_agent_mode not in SUPPORTED_DECISION_AGENT_MODES:
            raise ValueError(
                f"Unsupported decision agent mode {self.decision_agent_mode!r}; "
                f"expected one of {sorted(SUPPORTED_DECISION_AGENT_MODES)}."
            )
        self.decision_interval_seconds = max(1.0, float(self.decision_interval_seconds))
        self._last_decision_time = -self.decision_interval_seconds
        if self.decision_agent_mode == COS_DECISION_AGENT_MODE:
            from SC2_Agent.baseline_cos import CoSState

            self._cos_state = CoSState()
        else:
            self._cos_state = None
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
            "schema_version": (
                5
                if self.decision_agent_mode in STRUCTURAL_BASELINE_DECISION_AGENT_MODES
                else 4
                if self.decision_agent_mode in {
                    KNOWLEDGE_V22_V2_DECISION_AGENT_MODE,
                    KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE,
                    KNOWLEDGE_V23_DECISION_AGENT_MODE,
                    KNOWLEDGE_V23_NO_KNOWLEDGE_DECISION_AGENT_MODE,
                }
                else 3
                if self.decision_agent_mode == KNOWLEDGE_V22_DECISION_AGENT_MODE
                else 2
            ),
            "decision_agent_mode": self.decision_agent_mode,
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
            prompt_arguments = dict(
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
            structural_baseline_result: Optional[Dict[str, Any]] = None
            if self.decision_agent_mode in STRUCTURAL_BASELINE_DECISION_AGENT_MODES:
                if self.decision_agent_mode == PLAN_EXECUTE_DECISION_AGENT_MODE:
                    from SC2_Agent.baseline_plan_execute import (
                        build_decision_context,
                        run_decision,
                    )

                    trace_folder = "pe_traces"
                    record_key = "baseline_plan_execute"
                elif self.decision_agent_mode == SELF_REFINE_DECISION_AGENT_MODE:
                    from SC2_Agent.baseline_self_refine import (
                        build_decision_context,
                        run_decision,
                    )

                    trace_folder = "sr_traces"
                    record_key = "baseline_self_refine"
                elif self.decision_agent_mode == SUNTZU_DECISION_AGENT_MODE:
                    from SC2_Agent.baseline_suntzu import (
                        build_decision_context,
                        run_decision,
                    )

                    trace_folder = "suntzu_traces"
                    record_key = "baseline_suntzu"
                elif self.decision_agent_mode == HIMA_DECISION_AGENT_MODE:
                    from SC2_Agent.baseline_hima import (
                        build_decision_context,
                        run_decision,
                    )

                    trace_folder = "hima_traces"
                    record_key = "baseline_hima"
                else:
                    from SC2_Agent.baseline_cos import (
                        build_decision_context,
                        run_decision,
                    )

                    trace_folder = "cos_traces"
                    record_key = "baseline_cos"
                    if self._cos_state is None:
                        from SC2_Agent.baseline_cos import CoSState

                        self._cos_state = CoSState()
                structural_context = build_decision_context(**prompt_arguments)
                messages = [
                    {"role": "system", "content": structural_context["system_prompt"]},
                    {"role": "user", "content": structural_context["decision_event"]},
                ]
                trace_dir = (
                    os.path.join(self.record_dir, trace_folder)
                    if self.record_dir
                    else None
                )
                run_kwargs = dict(
                    system_prompt=structural_context["system_prompt"],
                    decision_event=structural_context["decision_event"],
                    provider=self.decision_model_key,
                    log_dir=trace_dir,
                    decision_metadata=structural_context["metadata"],
                )
                if self.decision_agent_mode == COS_DECISION_AGENT_MODE:
                    run_kwargs["cos_state"] = self._cos_state
                structural_baseline_result = run_decision(**run_kwargs)
                decision_payload = structural_baseline_result.get("decision")
                if isinstance(decision_payload, dict):
                    raw_response = json.dumps(decision_payload, ensure_ascii=False)
                    parsed = MacroDecision(
                        reason=str(decision_payload["reason"]),
                        ordered_names=list(decision_payload["ordered_names"]),
                    )
                else:
                    raw_response = ""
                    parsed = None
                llm_calls = structural_baseline_result.get("llm_calls") or []
                final_call = llm_calls[-1] if llm_calls else {}
                api_result = {
                    "content": raw_response,
                    "model_key": final_call.get("model_key", self.decision_model_key),
                    "model": final_call.get("model", ""),
                    "is_reasoning": final_call.get("is_reasoning"),
                    "reasoning": final_call.get("provider_reasoning", "") or "",
                    "reasoning_source": final_call.get("reasoning_source", "none")
                    or "none",
                    "reasoning_extract_mode": final_call.get(
                        "reasoning_extract_mode", "none"
                    )
                    or "none",
                    "raw_content": final_call.get("raw_content", "") or raw_response,
                    "error": "",
                    "structural_baseline_result": structural_baseline_result,
                }
                orchestration = structural_baseline_result.get("orchestration") or {}
                record[record_key] = {
                    "run_id": structural_baseline_result.get("run_id"),
                    "trace_path": structural_baseline_result.get("log_path"),
                    "model_call_count": structural_baseline_result.get(
                        "model_call_count"
                    ),
                    "status": structural_baseline_result.get("status"),
                    "orchestration": orchestration,
                    "plan_step_count": len(
                        (structural_baseline_result.get("plan") or {}).get("steps")
                        or (structural_baseline_result.get("plan") or {}).get("commands")
                        or []
                    ),
                    "executor_step_count": len(
                        structural_baseline_result.get("executor_steps")
                        or structural_baseline_result.get("executor_rounds")
                        or []
                    ),
                    "stop_reason": structural_baseline_result.get("stop_reason"),
                    "refine_round_count": len(
                        structural_baseline_result.get("rounds")
                        or structural_baseline_result.get("plan_rounds")
                        or []
                    ),
                    "valid_advisor_count": structural_baseline_result.get(
                        "valid_advisor_count"
                    ),
                    "history_size": structural_baseline_result.get("history_size"),
                    "configured_model_key": self.decision_model_key,
                }
            elif self.decision_agent_mode in {
                KNOWLEDGE_V22_DECISION_AGENT_MODE,
                KNOWLEDGE_V22_V2_DECISION_AGENT_MODE,
                KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE,
                KNOWLEDGE_V23_DECISION_AGENT_MODE,
                KNOWLEDGE_V23_NO_KNOWLEDGE_DECISION_AGENT_MODE,
            }:
                if self.decision_agent_mode in {
                    KNOWLEDGE_V22_V2_DECISION_AGENT_MODE,
                    KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE,
                    KNOWLEDGE_V23_DECISION_AGENT_MODE,
                    KNOWLEDGE_V23_NO_KNOWLEDGE_DECISION_AGENT_MODE,
                }:
                    if self.decision_agent_mode == KNOWLEDGE_V23_DECISION_AGENT_MODE:
                        from SC2_Agent.knowledge_v2_3 import (
                            build_knowledge_decision_context,
                            run_decision,
                        )

                        planner_state = self._knowledge_v2_3_planner_state
                        answer_ledger = self._knowledge_v2_3_ledger
                        trace_folder = "kv2_3_traces"
                        record_key = "knowledge_v2_3"
                    elif (
                        self.decision_agent_mode
                        == KNOWLEDGE_V23_NO_KNOWLEDGE_DECISION_AGENT_MODE
                    ):
                        from SC2_Agent.knowledge_v2_3_no_knowledge import (
                            build_knowledge_decision_context,
                            run_decision,
                        )

                        planner_state = self._knowledge_v2_3_no_knowledge_planner_state
                        answer_ledger = self._knowledge_v2_3_no_knowledge_ledger
                        trace_folder = "kv2_3_no_knowledge_traces"
                        record_key = "knowledge_v2_3_no_knowledge"
                    elif (
                        self.decision_agent_mode
                        == KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE
                    ):
                        from SC2_Agent.knowledge_v2_2_v2_no_knowledge import (
                            build_knowledge_decision_context,
                            run_decision,
                        )

                        planner_state = self._knowledge_v2_2_v2_no_knowledge_planner_state
                        answer_ledger = self._knowledge_v2_2_v2_no_knowledge_ledger
                        trace_folder = "kv2_no_knowledge_traces"
                        record_key = "knowledge_v2_2_v2_no_knowledge"
                    else:
                        from SC2_Agent.knowledge_v2_2_v2 import (
                            build_knowledge_decision_context,
                            run_decision,
                        )

                        planner_state = self._knowledge_v2_2_v2_planner_state
                        answer_ledger = self._knowledge_v2_2_v2_ledger
                        trace_folder = "kv2_traces"
                        record_key = "knowledge_v2_2_v2"
                    knowledge_context = build_knowledge_decision_context(
                        **prompt_arguments,
                        observation_structured=obs_snapshot,
                        planner_state=planner_state,
                        knowledge_ledger=answer_ledger,
                    )
                else:
                    from SC2_Agent.knowledge_v2_2 import (
                        build_knowledge_decision_context,
                        run_decision,
                    )
                    knowledge_context = build_knowledge_decision_context(**prompt_arguments)
                    trace_folder = "knowledge_v2_2_traces"
                    record_key = "knowledge_v2_2"
                messages = [
                    {"role": "system", "content": knowledge_context["system_prompt"]},
                    {"role": "user", "content": knowledge_context["decision_event"]},
                ]
                trace_dir = (
                    os.path.join(self.record_dir, trace_folder)
                    if self.record_dir
                    else None
                )
                run_arguments = dict(
                    system_prompt=knowledge_context["system_prompt"],
                    decision_event=knowledge_context["decision_event"],
                    provider=self.decision_model_key,
                    subagent_provider=self.data_subagent_model_key,
                    log_dir=trace_dir,
                    decision_metadata=knowledge_context["metadata"],
                )
                if self.decision_agent_mode in {
                    KNOWLEDGE_V22_V2_DECISION_AGENT_MODE,
                    KNOWLEDGE_V22_V2_NO_KNOWLEDGE_DECISION_AGENT_MODE,
                    KNOWLEDGE_V23_DECISION_AGENT_MODE,
                    KNOWLEDGE_V23_NO_KNOWLEDGE_DECISION_AGENT_MODE,
                }:
                    run_arguments.update(
                        planning_snapshot=knowledge_context["planning_snapshot"],
                        planner_state=planner_state,
                        knowledge_ledger=answer_ledger,
                    )
                knowledge_result = run_decision(**run_arguments)
                decision_payload = knowledge_result["decision"]
                raw_response = json.dumps(decision_payload, ensure_ascii=False)
                parsed = MacroDecision(
                    reason=str(decision_payload["reason"]),
                    ordered_names=list(decision_payload["ordered_names"]),
                )
                reasoning_trace = knowledge_result.get("reasoning_trace") or []
                main_calls = [
                    call
                    for call in reasoning_trace
                    if call.get("agent_role") == "main_agent"
                ]
                final_call = (main_calls or reasoning_trace or [{}])[-1]
                api_result = {
                    "content": raw_response,
                    "model_key": final_call.get("model_key", self.decision_model_key),
                    "model": final_call.get("model", ""),
                    "is_reasoning": final_call.get("is_reasoning"),
                    "reasoning": final_call.get("reasoning", "") or "",
                    "reasoning_source": final_call.get("reasoning_source", "none")
                    or "none",
                    "reasoning_extract_mode": final_call.get(
                        "reasoning_extract_mode", "none"
                    )
                    or "none",
                    "raw_content": final_call.get("raw_content", "") or raw_response,
                    "error": "",
                    "knowledge_result": knowledge_result,
                }
                actual_main_model_keys = sorted({
                    str(call.get("model_key") or "")
                    for call in main_calls
                    if call.get("model_key")
                })
                actual_subagent_model_keys = sorted({
                    str(call.get("model_key") or "")
                    for call in reasoning_trace
                    if call.get("agent_role") != "main_agent" and call.get("model_key")
                })
                record[record_key] = {
                    "run_id": knowledge_result.get("run_id"),
                    "trace_path": knowledge_result.get("log_path"),
                    "main_round_count": len(knowledge_result.get("main_decisions") or []),
                    "subagent_session_count": len(knowledge_result.get("subagent_sessions") or []),
                    "model_call_count": len(knowledge_result.get("reasoning_trace") or []),
                    "mainagent_model_key": (
                        actual_main_model_keys[-1] if actual_main_model_keys else None
                    ),
                    "data_subagent_model_key": (
                        actual_subagent_model_keys[-1]
                        if actual_subagent_model_keys
                        else None
                    ),
                    "configured_mainagent_model_key": self.decision_model_key,
                    "configured_data_subagent_model_key": self.data_subagent_model_key,
                    "actual_mainagent_model_keys": actual_main_model_keys,
                    "actual_data_subagent_model_keys": actual_subagent_model_keys,
                    "reasoning_policy": knowledge_result.get("reasoning_policy"),
                    "mainagent_reasoning_enabled": knowledge_result.get(
                        "mainagent_reasoning_enabled"
                    ),
                    "data_subagent_reasoning_enabled": knowledge_result.get(
                        "data_subagent_reasoning_enabled"
                    ),
                    "knowledge_query_used": bool(
                        (knowledge_result.get("routing") or {}).get("knowledge_query_used")
                    ),
                    "knowledge_cache_hit": bool(
                        (knowledge_result.get("routing") or {}).get("knowledge_cache_hit")
                    ),
                    "queue_audit": knowledge_result.get("queue_audit"),
                    "knowledge_application": knowledge_result.get("knowledge_application"),
                    "knowledge_effect": knowledge_result.get("knowledge_effect"),
                    "dataset": knowledge_result.get("dataset"),
                }
            else:
                messages = build_decision_messages(**prompt_arguments)
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
            if "structural_baseline_result" in locals() and structural_baseline_result:
                self._record_structural_baseline_llm_calls(
                    structural_baseline_result.get("llm_calls") or [],
                    decision=parsed,
                )
            elif "messages" in locals():
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

    def _record_structural_baseline_llm_calls(
        self,
        llm_calls: List[Dict[str, Any]],
        *,
        decision: Optional[MacroDecision],
    ) -> None:
        """Append every structural-baseline subcall to *.llm_calls.json."""
        for call in llm_calls:
            self._llm_call_seq += 1
            self._llm_call_records.append(
                {
                    "seq": self._llm_call_seq,
                    "game_time": round(float(getattr(self, "time", 0.0)), 2),
                    "decision_cycle": self._decision_cycle_count,
                    "agent": call.get("agent") or call.get("role") or "structural_baseline",
                    "role": call.get("role"),
                    "decision_agent_mode": self.decision_agent_mode,
                    "model_key": call.get("model_key") or self.decision_model_key,
                    "configured_model_key": call.get("configured_model_key")
                    or self.decision_model_key,
                    "configured_data_subagent_model_key": self.data_subagent_model_key,
                    "model": call.get("model", ""),
                    "is_reasoning": call.get("is_reasoning"),
                    "prompt": list(call.get("messages") or []),
                    "output": call.get("content", "") or "",
                    "decision_reason": decision.reason if decision else "",
                    "ordered_names": decision.ordered_names if decision else [],
                    "provider_reasoning": call.get("provider_reasoning", "") or "",
                    "reasoning_source": call.get("reasoning_source", "none") or "none",
                    "reasoning_extract_mode": call.get(
                        "reasoning_extract_mode",
                        "none",
                    ),
                    "raw_content": call.get("raw_content", "") or "",
                    "error": call.get("error", "") or "",
                    "wall_elapsed_seconds": call.get("wall_elapsed_seconds"),
                    "prompt_chars": call.get("prompt_chars"),
                    "output_chars": call.get("output_chars"),
                    "knowledge_v2_2": None,
                }
            )
        self._flush_llm_call_log()

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
                "decision_agent_mode": self.decision_agent_mode,
                "model_key": llm_result.get("model_key") or self.decision_model_key,
                "configured_model_key": self.decision_model_key,
                "configured_data_subagent_model_key": self.data_subagent_model_key,
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
                "knowledge_v2_2": self._knowledge_call_summary(llm_result),
            }
        )
        self._flush_llm_call_log()

    @staticmethod
    def _knowledge_call_summary(llm_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        result = llm_result.get("knowledge_result")
        if not isinstance(result, dict):
            return None
        sessions = []
        for session in result.get("subagent_sessions") or []:
            sessions.append({
                "session_id": session.get("session_id"),
                "main_round": session.get("main_round"),
                "question": session.get("question"),
                "query_type": session.get("query_type"),
                "targets": list(session.get("targets") or []),
                "requested_fields": list(session.get("requested_fields") or []),
                "selected_tools": list(session.get("selected_tools") or []),
                "reply": session.get("reply"),
                "observation_count": len(session.get("observations") or []),
                "cache_hit": bool(session.get("cache_hit")),
            })
        calls = []
        for call in result.get("reasoning_trace") or []:
            calls.append({
                "phase": call.get("phase"),
                "agent_role": call.get("agent_role"),
                "provider": call.get("provider"),
                "configured_model_key": call.get("configured_model_key"),
                "model_key": call.get("model_key"),
                "model": call.get("model"),
                "profile_reasoning_mode": call.get("profile_reasoning_mode"),
                "reasoning_override": call.get("reasoning_override"),
                "reasoning_requested": call.get("reasoning_requested"),
                "is_reasoning": call.get("is_reasoning"),
                "reasoning_available": call.get("reasoning_available"),
                "reasoning_source": call.get("reasoning_source"),
                "finish_reason": call.get("finish_reason"),
                "latency_seconds": call.get("latency_seconds"),
                "rate_limit_wait_seconds": call.get("rate_limit_wait_seconds"),
                "error": call.get("error", ""),
            })
        return {
            "agent_version": result.get("agent_version"),
            "run_id": result.get("run_id"),
            "trace_path": result.get("log_path"),
            "dataset": result.get("dataset"),
            "mainagent_provider": result.get("mainagent_provider"),
            "data_subagent_provider": result.get("data_subagent_provider"),
            "configured_mainagent_model_key": result.get("mainagent_provider"),
            "configured_data_subagent_model_key": result.get(
                "data_subagent_provider"
            ),
            "reasoning_policy": result.get("reasoning_policy"),
            "mainagent_reasoning_enabled": result.get("mainagent_reasoning_enabled"),
            "data_subagent_reasoning_enabled": result.get(
                "data_subagent_reasoning_enabled"
            ),
            "knowledge_query_used": bool((result.get("routing") or {}).get("knowledge_query_used")),
            "knowledge_cache_hit": bool((result.get("routing") or {}).get("knowledge_cache_hit")),
            "planning_snapshot": result.get("planning_snapshot"),
            "queue_audit": result.get("queue_audit"),
            "knowledge_application": result.get("knowledge_application"),
            "query_skip_reason": result.get("query_skip_reason"),
            "knowledge_not_used_reason": result.get("knowledge_not_used_reason"),
            "main_decisions": result.get("main_decisions"),
            "subagent_sessions": sessions,
            "model_calls": calls,
        }

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
