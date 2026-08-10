"""Multi-round skill navigation without provider-native tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Callable, Dict, List, Optional

from API_Tools.llm_caller import call_openai_detailed
from SC2_Agent.data_tools import (
    action_candidates_for_entity,
    cost_for_action,
    race_mechanics,
)
from SC2_Agent.data_tools.sc2_data_common import build_entity_indexes, load_database

from .navigator import SkillNavigator
from .prompt_common import build_human_skill_messages
from .protocol import parse_agent_response
from .schema import AgentRound, FinalDecision
from .skill_loader import ReadableSkill, ReadableSkillLoader
from .skill_memory import MatchSkillMemory
from .trace_recorder import HumanSkillTraceRecorder
from .validation import require_non_reasoning_model

LLMCall = Callable[[List[Dict[str, str]], str, str], Dict[str, Any]]


@dataclass(frozen=True)
class HumanSkillRunResult:
    decision: Optional[FinalDecision]
    rounds: List[AgentRound]
    skill_memory_before: List[str]
    skill_reads_this_cycle: List[str]
    skill_memory_after: List[str]
    llm_calls: List[Dict[str, Any]]
    error: str = ""


class HumanSkillAgent:
    """Base orchestration shared by six separately configured packages."""

    MAX_SKILL_READS_PER_DECISION = 3
    MAX_AGENT_ROUNDS_PER_DECISION = 4
    GRAPH_PHASE_START_SECONDS = (0.0, 360.0, 720.0)

    def __init__(
        self,
        *,
        agent_version: str,
        skill_method: str,
        allowed_node_types: set[str],
        allow_graph_navigation: bool,
        variant_contract: str,
        loader: ReadableSkillLoader,
        skill: ReadableSkill,
        model_key: str,
        api_config_path: str,
        trace_recorder: Optional[HumanSkillTraceRecorder] = None,
        llm_call: Optional[LLMCall] = None,
    ):
        if skill.method != skill_method:
            raise ValueError(f"agent {agent_version} is pinned to {skill_method}, got {skill.method}")
        require_non_reasoning_model(model_key, api_config_path)
        self.agent_version = agent_version
        self.skill_method = skill_method
        self.allowed_node_types = set(allowed_node_types)
        self.allow_graph_navigation = bool(allow_graph_navigation)
        self.variant_contract = variant_contract
        self.loader = loader
        self.skill = skill
        self.navigator = SkillNavigator(loader, skill)
        self.model_key = model_key
        self.api_config_path = api_config_path
        self.memory = MatchSkillMemory(skill_id=skill.skill_id, method=skill.method)
        self.trace_recorder = trace_recorder or HumanSkillTraceRecorder()
        self._llm_call = llm_call or self._default_llm_call

    @staticmethod
    def _usage(result: Dict[str, Any]) -> Dict[str, Any]:
        raw = result.get("usage") or result.get("token_usage") or {}
        return dict(raw) if isinstance(raw, dict) else {}

    @staticmethod
    def _default_llm_call(messages: List[Dict[str, str]], model_key: str, api_config_path: str) -> Dict[str, Any]:
        return call_openai_detailed(
            messages=messages,
            model_key=model_key,
            config_path=api_config_path,
            response_format={"type": "json_object"},
        )

    def reset_match(self) -> None:
        self.memory = MatchSkillMemory(skill_id=self.skill.skill_id, method=self.skill.method)

    def _graph_phase_refresh_error(self, game_time_seconds: float) -> str:
        """Require graph-capable variants to actually navigate as the match evolves."""

        if not self.allow_graph_navigation or len(self.skill.nodes) < 2:
            return ""
        phase_start = max(
            threshold
            for threshold in self.GRAPH_PHASE_START_SECONDS
            if game_time_seconds >= threshold
        )
        if phase_start <= 0:
            return ""
        unread = [node_id for node_id in self.skill.nodes if node_id not in self.memory.visited_node_ids]
        if not unread:
            return ""
        refreshed = any(
            float(stats.get("first_read_game_time") or 0) >= phase_start
            for stats in self.memory.read_stats.values()
        )
        if refreshed:
            return ""
        phase_name = "midgame" if phase_start == 360.0 else "late-game"
        return (
            f"FINAL_DECISION rejected: the match entered {phase_name} at "
            f"{phase_start:g}s, but this graph agent has not refreshed its skill node for "
            "the new phase. Request READ_SKILL for one unread node whose trigger best "
            "matches the live economy, army, technology, and enemy cues, then decide from "
            "that node."
        )

    @staticmethod
    def _planned_gas_cost(race: str, ordered_names: List[str]) -> tuple[int, Optional[int]]:
        """Return total gas cost and the first gas-consuming queue position."""
        total = 0
        first: Optional[int] = None
        for index, name in enumerate(ordered_names):
            try:
                candidates = action_candidates_for_entity(race, name)
                info = cost_for_action(candidates[0].ability_name) if candidates else {}
                gas = int(((info.get("cost") or {}).get("gas") or 0))
            except Exception:
                gas = 0
            if gas > 0:
                total += gas
                if first is None:
                    first = index
        return total, first

    @classmethod
    def _queue_resource_error(
        cls,
        *,
        race: str,
        obs_text: str,
        ordered_names: List[str],
    ) -> str:
        """Reject an impossible gas queue so the LLM can repair its own decision."""
        planned_gas, first_gas_action = cls._planned_gas_cost(race, ordered_names)
        if not planned_gas or first_gas_action is None:
            return ""
        bank_match = re.search(r"\b([0-9]+)\s+vespene\b", obs_text, re.IGNORECASE)
        gas_income_match = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s+gas/min\b", obs_text, re.IGNORECASE)
        if bank_match is None or gas_income_match is None:
            return ""
        current_gas = int(bank_match.group(1)) if bank_match else 0
        gas_income = float(gas_income_match.group(1)) if gas_income_match else 0.0
        if current_gas >= planned_gas or gas_income > 0:
            return ""
        mechanics = race_mechanics(race)
        gas_structure = mechanics.gas_structure
        own_section = obs_text.split("[Enemy Intelligence]", 1)[0]
        own_has_gas_structure = gas_structure.upper() in own_section.upper()
        queued_positions = [
            index for index, name in enumerate(ordered_names) if name == gas_structure
        ]
        queued_before = bool(queued_positions and queued_positions[0] < first_gas_action)
        if own_has_gas_structure or queued_before:
            return ""
        return (
            "FINAL_DECISION rejected: the queue needs "
            f"{planned_gas} gas but current gas/income is {current_gas}/{gas_income:g} and "
            f"no own {gas_structure} is active. Include {gas_structure} before the first "
            "gas-consuming action, then return the complete replacement queue."
        )

    @staticmethod
    def _production_capacity_error(
        *,
        race: str,
        obs_text: str,
        ordered_names: List[str],
        canonical_unit_names: List[str],
    ) -> str:
        """Reject obvious idle-producer overbuilding and ask the LLM to re-plan."""
        if "[Own Forces & Infrastructure]" not in obs_text or "Active Queues:" not in obs_text:
            return ""
        mechanics = race_mechanics(race)
        own_section = obs_text.split("[Own Forces & Infrastructure]", 1)[1].split(
            "[Enemy Intelligence]", 1
        )[0]
        infrastructure, active_queues = own_section.split("Active Queues:", 1)
        counts: Dict[str, int] = {}
        for count, entity in re.findall(r"\b([0-9]+)\s+([A-Z][A-Z0-9_]*)\b", infrastructure):
            counts[entity] = counts.get(entity, 0) + int(count)
        active_army_training = sum(
            int(count)
            for count, entity in re.findall(
                r"\bTraining\s+([0-9]+)\s+([A-Z][A-Z0-9_]*)\b", active_queues
            )
            if entity != mechanics.worker.upper()
        )

        producer_names: set[str] = set()
        entity_candidates: Dict[str, list[Any]] = {}
        for entity_name in canonical_unit_names:
            try:
                candidates = list(action_candidates_for_entity(race, entity_name))
            except Exception:
                candidates = []
            entity_candidates[entity_name] = candidates
            for candidate in candidates:
                if candidate.execution_mode in {"train", "warp_in"}:
                    producer_names.update(candidate.executors)

        for planned_name in ordered_names:
            if planned_name not in producer_names:
                continue
            build_candidates = entity_candidates.get(planned_name)
            if build_candidates is None:
                try:
                    build_candidates = list(action_candidates_for_entity(race, planned_name))
                except Exception:
                    build_candidates = []
            if not any(candidate.execution_mode == "worker_build" for candidate in build_candidates):
                continue
            existing = counts.get(planned_name.upper(), 0)
            if existing <= 0:
                continue
            planned_demand = 0
            for entity_name in ordered_names:
                candidates = entity_candidates.get(entity_name)
                if candidates is None:
                    try:
                        candidates = list(action_candidates_for_entity(race, entity_name))
                    except Exception:
                        candidates = []
                if any(
                    candidate.execution_mode in {"train", "warp_in"}
                    and planned_name in candidate.executors
                    for candidate in candidates
                ):
                    planned_demand += 1
            if active_army_training + planned_demand <= existing * 2:
                return (
                    f"FINAL_DECISION rejected: {existing} own {planned_name} production "
                    f"structure(s) already exist or are in progress, but only "
                    f"{active_army_training} army unit(s) are actively training and the queue "
                    f"requests {planned_demand} compatible unit(s). Do not use {planned_name} "
                    "to mean 'keep producing'. Remove the extra structure and spend through "
                    "the existing capacity, unless you queue enough compatible units to "
                    "justify more throughput."
                )
        return ""

    @staticmethod
    def _queue_supply_error(
        *,
        race: str,
        obs_text: str,
        ordered_names: List[str],
    ) -> str:
        """Reject a sequential queue that blocks before reaching its supply provider."""

        supply_match = re.search(
            r"\bSupply:\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)",
            obs_text,
            re.IGNORECASE,
        )
        if supply_match is None:
            return ""
        projected_used = float(supply_match.group(1))
        projected_cap = float(supply_match.group(2))
        mechanics = race_mechanics(race)
        deltas: List[float] = []
        for entity_name in ordered_names:
            try:
                candidates = list(action_candidates_for_entity(race, entity_name))
                candidate = candidates[0] if candidates else None
                info = cost_for_action(candidate.ability_name) if candidate else {}
                delta = float(((info.get("cost") or {}).get("supply") or 0))
                # ``cost_for_action`` intentionally normalizes generic Morph
                # supply to zero for townhall morphs. Larva morphs are actual
                # unit production, so recover their raw result supply here.
                if (
                    candidate is not None
                    and candidate.target_kind in {"Morph", "MorphPlace"}
                    and "Larva" in candidate.executors
                ):
                    units, _ = build_entity_indexes(load_database())
                    raw_unit = units.get(candidate.target_result) or {}
                    delta = float(raw_unit.get("supply") or 0)
                if delta > 0 and candidate is not None:
                    delta *= max(1, int(candidate.output_count))
            except Exception:
                delta = 0.0
            deltas.append(delta)

        provider_gain = 8.0
        try:
            provider_candidates = list(action_candidates_for_entity(race, mechanics.supply_provider))
            provider_candidate = provider_candidates[0] if provider_candidates else None
            provider_info = cost_for_action(provider_candidate.ability_name) if provider_candidate else {}
            provider_delta = float(((provider_info.get("cost") or {}).get("supply") or 0))
            if (
                provider_candidate is not None
                and provider_candidate.target_kind in {"Morph", "MorphPlace"}
                and "Larva" in provider_candidate.executors
            ):
                units, _ = build_entity_indexes(load_database())
                provider_unit = units.get(provider_candidate.target_result) or {}
                provider_delta = float(provider_unit.get("supply") or 0)
            provider_gain = max(1.0, -provider_delta)
        except Exception:
            pass

        for index, (entity_name, delta) in enumerate(zip(ordered_names, deltas)):
            if delta < 0:
                projected_cap = min(200.0, projected_cap - delta)
                continue
            if delta <= 0:
                continue
            if projected_used + delta <= projected_cap + 1e-6:
                projected_used += delta
                continue
            if projected_cap >= 200.0 - 1e-6 and projected_used >= projected_cap - 1e-6:
                return (
                    "FINAL_DECISION rejected: the army is already at the maximum supply "
                    f"({projected_used:g}/{projected_cap:g}), so {entity_name} cannot start. "
                    "Return an empty ordered_names queue or only zero-supply upgrades and "
                    "morphs until combat losses create room; an additional supply provider "
                    "cannot raise the 200 cap."
                )
            remaining_demand = sum(max(0.0, item) for item in deltas[index:])
            free_supply = max(0.0, projected_cap - projected_used)
            max_extra_supply = max(0.0, 200.0 - projected_cap)
            if remaining_demand > free_supply + max_extra_supply + 1e-6:
                instruction = (
                    "Shorten the unit queue: even after raising the cap to 200, only "
                    f"{free_supply + max_extra_supply:g} more supply can fit"
                )
            else:
                providers_needed = max(
                    1,
                    int(math.ceil(max(0.0, remaining_demand - free_supply) / provider_gain)),
                )
                instruction = (
                    f"Place at least {providers_needed} additional {mechanics.supply_provider} "
                    f"entr{'y' if providers_needed == 1 else 'ies'} before {entity_name}, or "
                    "shorten the unit queue to fit"
                )
            return (
                "FINAL_DECISION rejected: the sequential queue reaches a supply block at "
                f"{entity_name} (projected {projected_used:g}/{projected_cap:g}). "
                f"{instruction}; actions after a blocked unit are never reached. Return the "
                "complete replacement queue in executable order."
            )
        return ""

    def decide(
        self,
        *,
        race: str,
        enemy_race: str,
        obs_text: str,
        unfinished_canonical_names: List[str],
        canonical_unit_names: List[str],
        canonical_upgrade_names: List[str],
        race_context: str,
        automation_context: str,
        decision_cycle: int,
        trigger_reason: str,
        game_time_seconds: float,
        decision_interval_seconds: float,
    ) -> HumanSkillRunResult:
        before = list(self.memory.visited_node_ids)
        self.memory.mark_cycle(decision_cycle)
        reads_this_cycle: List[str] = []
        rounds: List[AgentRound] = []
        llm_calls: List[Dict[str, Any]] = []
        feedback = ""
        decision: Optional[FinalDecision] = None
        force_final_next = False

        def run_round(round_number: int, force_final: bool) -> bool:
            nonlocal feedback, decision, force_final_next
            messages = build_human_skill_messages(
                race=race,
                enemy_race=enemy_race,
                variant_contract=self.variant_contract,
                skill=self.skill,
                memory=self.memory,
                available_nodes=self.navigator.available_summary(),
                obs_text=obs_text,
                unfinished_canonical_names=unfinished_canonical_names,
                canonical_unit_names=canonical_unit_names,
                canonical_upgrade_names=canonical_upgrade_names,
                race_context=race_context,
                automation_context=automation_context,
                decision_cycle=decision_cycle,
                trigger_reason=trigger_reason,
                game_time_seconds=game_time_seconds,
                decision_interval_seconds=decision_interval_seconds,
                protocol_feedback=feedback,
                force_final=force_final,
            )
            result = self._llm_call(messages, self.model_key, self.api_config_path) or {}
            content = str(result.get("content") or "")
            parsed = parse_agent_response(content)
            llm_calls.append(
                {
                    "round": round_number,
                    "force_final": force_final,
                    "model_key": result.get("model_key") or self.model_key,
                    "model": result.get("model") or "",
                    "is_reasoning": result.get("is_reasoning"),
                    "reasoning_present": bool(result.get("reasoning")),
                    "usage": self._usage(result),
                    "messages": messages,
                    "output": content,
                    "error": result.get("error") or "",
                }
            )
            if parsed.decision is not None:
                if not self.memory.visited_node_ids and self.skill.nodes:
                    feedback = (
                        "FINAL_DECISION rejected: before the first decision of this match, "
                        "request READ_SKILL for the single node whose trigger best matches "
                        "the live observation."
                    )
                    rounds.append(
                        AgentRound(
                            round=round_number,
                            type="invalid",
                            error=feedback,
                            model_key=self.model_key,
                            model=str(result.get("model") or ""),
                            token_usage=self._usage(result),
                        )
                    )
                    return False
                phase_refresh_error = self._graph_phase_refresh_error(game_time_seconds)
                if phase_refresh_error:
                    feedback = phase_refresh_error
                    rounds.append(
                        AgentRound(
                            round=round_number,
                            type="invalid",
                            error=feedback,
                            model_key=self.model_key,
                            model=str(result.get("model") or ""),
                            token_usage=self._usage(result),
                        )
                    )
                    return False
                resource_error = self._queue_resource_error(
                    race=race,
                    obs_text=obs_text,
                    ordered_names=parsed.decision.ordered_names,
                )
                if resource_error:
                    feedback = resource_error
                    rounds.append(
                        AgentRound(
                            round=round_number,
                            type="invalid",
                            error=feedback,
                            model_key=self.model_key,
                            model=str(result.get("model") or ""),
                            token_usage=self._usage(result),
                        )
                    )
                    return False
                supply_error = self._queue_supply_error(
                    race=race,
                    obs_text=obs_text,
                    ordered_names=parsed.decision.ordered_names,
                )
                if supply_error:
                    feedback = supply_error
                    rounds.append(
                        AgentRound(
                            round=round_number,
                            type="invalid",
                            error=feedback,
                            model_key=self.model_key,
                            model=str(result.get("model") or ""),
                            token_usage=self._usage(result),
                        )
                    )
                    return False
                capacity_error = self._production_capacity_error(
                    race=race,
                    obs_text=obs_text,
                    ordered_names=parsed.decision.ordered_names,
                    canonical_unit_names=canonical_unit_names,
                )
                if capacity_error:
                    feedback = capacity_error
                    rounds.append(
                        AgentRound(
                            round=round_number,
                            type="invalid",
                            error=feedback,
                            model_key=self.model_key,
                            model=str(result.get("model") or ""),
                            token_usage=self._usage(result),
                        )
                    )
                    return False
                decision = parsed.decision
                rounds.append(
                    AgentRound(
                        round=round_number,
                        type="decision",
                        model_key=self.model_key,
                        model=str(result.get("model") or ""),
                        token_usage=self._usage(result),
                    )
                )
                return True
            if parsed.request is not None and not force_final:
                node_id = parsed.request.node_id
                if node_id in reads_this_cycle:
                    feedback = (
                        f"READ_SKILL rejected: {node_id} was already served in this "
                        "decision and is visible in Previously Read Skill Nodes. "
                        "The next response must be FINAL_DECISION."
                    )
                    force_final_next = True
                    rounds.append(
                        AgentRound(
                            round_number,
                            "read_skill",
                            node_id,
                            feedback,
                            self.model_key,
                            str(result.get("model") or ""),
                            self._usage(result),
                        )
                    )
                    return False
                if len(reads_this_cycle) >= self.MAX_SKILL_READS_PER_DECISION:
                    feedback = "READ_SKILL rejected: per-decision read limit reached."
                    rounds.append(
                        AgentRound(
                            round_number,
                            "read_skill",
                            node_id,
                            feedback,
                            self.model_key,
                            str(result.get("model") or ""),
                            self._usage(result),
                        )
                    )
                    return False
                try:
                    served_from_memory = node_id in self.memory.visited_node_contents
                    content = (
                        self.memory.visited_node_contents[node_id]
                        if served_from_memory
                        else self.navigator.read(node_id)
                    )
                except Exception as exc:
                    feedback = f"READ_SKILL rejected: {exc}"
                    rounds.append(
                        AgentRound(
                            round_number,
                            "read_skill",
                            node_id,
                            feedback,
                            self.model_key,
                            str(result.get("model") or ""),
                            self._usage(result),
                        )
                    )
                    return False
                self.memory.remember(
                    node_id,
                    content,
                    node_type=self.skill.nodes[node_id].node_type,
                    game_time=game_time_seconds,
                    decision_cycle=decision_cycle,
                )
                reads_this_cycle.append(node_id)
                source = "match memory" if served_from_memory else "validated node file"
                feedback = (
                    f"READ_SKILL accepted from {source}: {node_id} is already visible in "
                    "Previously Read Skill Nodes. Do not request it again in this decision."
                )
                rounds.append(
                    AgentRound(
                        round=round_number,
                        type="read_skill",
                        node_id=node_id,
                        model_key=self.model_key,
                        model=str(result.get("model") or ""),
                        token_usage=self._usage(result),
                    )
                )
                return False
            feedback = parsed.error or "A final decision is required."
            rounds.append(
                AgentRound(
                    round=round_number,
                    type="invalid",
                    error=feedback,
                    model_key=self.model_key,
                    model=str(result.get("model") or ""),
                    token_usage=self._usage(result),
                )
            )
            return False

        for round_number in range(1, self.MAX_AGENT_ROUNDS_PER_DECISION + 1):
            force_final = force_final_next
            force_final_next = False
            if run_round(round_number, force_final):
                break
        if decision is None:
            run_round(self.MAX_AGENT_ROUNDS_PER_DECISION + 1, True)

        error = "" if decision is not None else "invalid_response_keep_old_queue"
        result = HumanSkillRunResult(
            decision=decision,
            rounds=rounds,
            skill_memory_before=before,
            skill_reads_this_cycle=reads_this_cycle,
            skill_memory_after=list(self.memory.visited_node_ids),
            llm_calls=llm_calls,
            error=error,
        )
        self.trace_recorder.record_decision(
            {
                "schema_version": 5,
                "agent_version": self.agent_version,
                "skill_method": self.skill_method,
                "skill_id": self.skill.skill_id,
                "cycle": decision_cycle,
                "game_time": round(float(game_time_seconds), 2),
                "skill_memory_before": before,
                "skill_reads_this_cycle": reads_this_cycle,
                "skill_memory_after": list(self.memory.visited_node_ids),
                "agent_rounds": [asdict(item) for item in rounds],
                "observation_at_this_moment": obs_text,
                "decision": asdict(decision) if decision else None,
                "error": error,
            }
        )
        return result
