"""Hierarchical readable-skill macro bot with match-scoped explicit read memory."""

from __future__ import annotations

import logging
import os
import time as _wall_time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from SC2_Agent.data_tools import (
    ActionCandidate,
    canonical_race_entity_name,
    race_prompt_context,
    race_unit_names,
    race_upgrade_names,
)
from SC2_Agent.human_skill_common.skill_loader import (
    ReadableSkillLoader,
    resolve_readable_skill_root,
)
from SC2_Agent.human_skill_common.trace_recorder import HumanSkillTraceRecorder
from SC2_Agent.human_skill_common.validation import resolve_api_config
from SC2_Agent.human_skill_common.variants import load_variant_package
from SC2_Agent.prompt_context import (
    protoss_automation_profile,
    terran_automation_profile,
    zerg_automation_profile,
)
from dummies.generic.universal_llm_bot import UniversalLLMBot

logger = logging.getLogger("UniversalLLMHumanSkillBot")

DEFAULT_HUMAN_SKILL_AGENT = "human-skill-full"
DEFAULT_HUMAN_SKILL_ID = "PvP_O01"
DEFAULT_DECISION_MODEL = "DeepSeek-V4-flash"


class UniversalLLMHumanSkillBot(UniversalLLMBot):
    """Preserves observation, scheduler, mapping and atomic queue semantics."""

    def __init__(
        self,
        race_name: str = "protoss",
        record_dir: str = "",
        *,
        decision_model_key: str = DEFAULT_DECISION_MODEL,
        human_skill_agent: str = DEFAULT_HUMAN_SKILL_AGENT,
        force_human_skill: str = DEFAULT_HUMAN_SKILL_ID,
        human_skill_root: str = "",
        api_config_path: str = "",
        decision_interval_seconds: float = UniversalLLMBot.DEFAULT_DECISION_INTERVAL_SECONDS,
    ):
        super().__init__(
            race_name=race_name,
            record_dir=record_dir,
            decision_model_key=decision_model_key,
            data_subagent_model_key=decision_model_key,
            decision_agent_mode="naive",
            decision_interval_seconds=decision_interval_seconds,
            force_strategy=force_human_skill,
        )
        self.human_skill_agent = human_skill_agent
        self.force_human_skill = force_human_skill
        self.human_skill_root = human_skill_root
        self.api_config_path = api_config_path
        self._human_agent = None
        self._human_trace: Optional[HumanSkillTraceRecorder] = None

    def _apply_forced_strategy(self, name: str) -> None:
        """Parent lifecycle hook, repurposed for a pinned readable opening."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
        skill_id = str(self.force_human_skill or name or "").strip()
        if not skill_id:
            raise ValueError("UniversalLLMHumanSkillBot requires --force-human-skill")
        spec, package, agent_class = load_variant_package(self.human_skill_agent)
        root = resolve_readable_skill_root(repo_root, self.human_skill_root)
        api_config = resolve_api_config(repo_root, self.api_config_path)
        enemy_race = self._strategy_enemy_race_name()
        matchup = f"{self.race_name[0].upper()}v{enemy_race[0].upper()}"
        loader = ReadableSkillLoader(root)
        skill = loader.load(
            method=spec.method,
            race=self.race_name,
            matchup=matchup,
            skill_id=skill_id,
            allowed_node_types=package.ALLOWED_NODE_TYPES,
            allow_graph_navigation=package.ALLOW_GRAPH_NAVIGATION,
        )
        match_id = os.path.basename(os.path.abspath(self.record_dir)) if self.record_dir else "match"
        self._human_trace = HumanSkillTraceRecorder(self.record_dir, match_id)
        self._human_agent = agent_class(
            loader=loader,
            skill=skill,
            model_key=self.decision_model_key,
            api_config_path=api_config,
            trace_recorder=self._human_trace,
        )
        self.selected_strategy = skill_id
        self.strategy_summary = skill.root_markdown
        self.strategy_enemy_race = enemy_race
        self.strategy_automation_context = self._generic_automation_profile().render()
        self._llm_infer_emit(
            f">>> HUMAN SKILL: agent={self.human_skill_agent} method={spec.method} " f"skill={skill_id} root={root}"
        )
        self._record_llm_interaction(
            {
                "schema_version": 5,
                "game_time": 0.0,
                "trigger_reason": "forced_human_skill",
                "agent_version": self._human_agent.agent_version,
                "skill_method": spec.method,
                "skill_id": skill_id,
                "matchup": matchup,
                "readable_skill_root": root,
                "automation_profile": self.strategy_automation_context,
            }
        )

    def _generic_automation_profile(self):
        strategy = "race_generic_human_skill"
        if self.race_name == "protoss":
            return protoss_automation_profile(strategy=strategy, attack_threshold=16)
        if self.race_name == "terran":
            return terran_automation_profile(strategy=strategy, attack_threshold=18)
        if self.race_name == "zerg":
            return zerg_automation_profile(strategy=strategy, attack_threshold=16)
        raise ValueError(f"unsupported race: {self.race_name}")

    def _load_strategy_tools(self):
        """One race-generic tactical profile shared by all six variants."""
        if self.race_name == "protoss":
            from SKILL.protoss.common_tools import make_protoss_strategy_tools

            return make_protoss_strategy_tools(attack_value=16)
        if self.race_name == "terran":
            from SC2_Agent.human_skill_common.automation import make_terran_generic_tools

            return make_terran_generic_tools(attack_value=18)
        if self.race_name == "zerg":
            from SKILL.zerg.common_tools import make_zerg_strategy_tools

            return make_zerg_strategy_tools(attack_value=16)
        raise ValueError(f"unsupported race: {self.race_name}")

    async def on_end(self, game_result):
        if self._human_agent is not None and self._human_trace is not None:
            try:
                self._human_trace.flush(self._human_agent.memory)
            except Exception as exc:
                logger.warning("failed to flush human-skill trace: %s", exc)
        await super().on_end(game_result)

    def _run_decision_pipeline_blocking(self, *, trigger_reason: str) -> None:
        assert self.scheduler is not None
        if self._human_agent is None:
            raise RuntimeError("human-skill agent was not initialized")
        game_time = float(self.time)
        started = _wall_time.monotonic()
        self._decision_cycle_count += 1
        old_names = self.scheduler.uncommitted_canonical_names()
        record: Dict[str, Any] = {
            "schema_version": 5,
            "agent_version": self._human_agent.agent_version,
            "skill_method": self._human_agent.skill_method,
            "skill_id": self._human_agent.skill.skill_id,
            "cycle": self._decision_cycle_count,
            "game_time": round(game_time, 2),
            "trigger_reason": trigger_reason,
            "old_uncommitted_canonical_names": list(old_names),
        }
        try:
            obs_text, obs_snapshot = self._capture_observation_bundle()
            record["observation_at_this_moment"] = obs_text
            record["observation_structured"] = obs_snapshot
            result = self._human_agent.decide(
                race=self.race_name,
                enemy_race=self.strategy_enemy_race,
                obs_text=obs_text,
                unfinished_canonical_names=old_names,
                canonical_unit_names=race_unit_names(self.race_name),
                canonical_upgrade_names=race_upgrade_names(self.race_name),
                race_context=race_prompt_context(self.race_name),
                automation_context=self.strategy_automation_context,
                decision_cycle=self._decision_cycle_count,
                trigger_reason=trigger_reason,
                game_time_seconds=game_time,
                decision_interval_seconds=self.decision_interval_seconds,
            )
            record.update(
                {
                    "skill_memory_before": result.skill_memory_before,
                    "skill_reads_this_cycle": result.skill_reads_this_cycle,
                    "skill_memory_after": result.skill_memory_after,
                    "agent_rounds": [asdict(item) for item in result.rounds],
                    "llm_call_count": len(result.llm_calls),
                }
            )
            for call in result.llm_calls:
                self._llm_call_seq += 1
                self._llm_call_records.append(
                    {
                        "seq": self._llm_call_seq,
                        "game_time": round(game_time, 2),
                        "decision_cycle": self._decision_cycle_count,
                        "agent": "human_skill_macro_decision",
                        **call,
                    }
                )
            if result.decision is None:
                record["error"] = result.error or "invalid_response_keep_old_queue"
                return

            valid_names: List[str] = []
            dropped_unknown: List[str] = []
            for name in result.decision.ordered_names:
                canonical = canonical_race_entity_name(self.race_name, name)
                if canonical is None:
                    dropped_unknown.append(name)
                else:
                    valid_names.append(canonical)
            mapped: List[Tuple[str, ActionCandidate, Tuple[ActionCandidate, ...]]] = []
            dropped_unmapped: List[str] = []
            for name in valid_names:
                candidates = self._action_candidates_for_entity(name)
                if candidates:
                    mapped.append((name, candidates[0], tuple(candidates[1:])))
                else:
                    dropped_unmapped.append(name)
            if result.decision.ordered_names and not mapped:
                record["error"] = "no_valid_mapped_tasks_keep_old_queue"
                record["decision"] = {
                    "reason": result.decision.reason,
                    "ordered_names": result.decision.ordered_names,
                    "dropped_unknown_names": dropped_unknown,
                    "dropped_unmapped_names": dropped_unmapped,
                }
                return
            self._accepted_queue_count += 1
            queue_id = self._accepted_queue_count
            replaced = self.scheduler.replace_uncommitted_queue(mapped, queue_id=queue_id)
            new_names = [name for name, _action, _alternatives in mapped]
            carried, discarded, introduced = self._queue_transition(replaced, new_names)
            self._queue_had_work_since_decision = bool(new_names)
            record["queue_id"] = queue_id
            record["decision"] = {
                "reason": result.decision.reason,
                "ordered_names": result.decision.ordered_names,
                "accepted_ordered_names": new_names,
                "dropped_unknown_names": dropped_unknown,
                "dropped_unmapped_names": dropped_unmapped,
            }
            record["queue_transition"] = {
                "carried_forward_names": carried,
                "discarded_old_names": discarded,
                "newly_introduced_names": introduced,
            }
            record["committed_work_untouched"] = True
        except Exception as exc:
            record["error"] = repr(exc)
            logger.warning("human-skill decision pipeline failed: %s", exc)
        finally:
            record["wall_elapsed_seconds"] = round(_wall_time.monotonic() - started, 3)
            self._record_llm_interaction(record)


__all__ = ["UniversalLLMHumanSkillBot"]
