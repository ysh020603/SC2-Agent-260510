"""Multi-round skill navigation without provider-native tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional

from API_Tools.llm_caller import call_openai_detailed

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

        def run_round(round_number: int, force_final: bool) -> bool:
            nonlocal feedback, decision
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
            if run_round(round_number, False):
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
