"""Parsers and validation for Plan-and-Execute artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .decision_prompt import MacroDecision, _extract_json_object, parse_decision_response

MAX_PLAN_STEPS = 4
MAX_QUEUE_NAMES = 20


@dataclass(frozen=True)
class PlanStep:
    step_id: int
    objective: str


@dataclass(frozen=True)
class PlanArtifact:
    plan_summary: str
    steps: List[PlanStep]


@dataclass(frozen=True)
class ExecutorFragment:
    step_id: int
    reason: str
    ordered_names: List[str]


def parse_plan_response(text: str) -> Optional[PlanArtifact]:
    data = _extract_json_object(text)
    if data is None:
        return None
    summary = data.get("plan_summary")
    steps_raw = data.get("steps")
    if not isinstance(summary, str) or not summary.strip():
        return None
    if not isinstance(steps_raw, list) or not steps_raw:
        return None
    if len(steps_raw) > MAX_PLAN_STEPS:
        return None

    steps: List[PlanStep] = []
    seen_ids = set()
    for index, item in enumerate(steps_raw, start=1):
        if not isinstance(item, dict):
            return None
        step_id = item.get("step_id")
        objective = item.get("objective")
        if not isinstance(step_id, int) or isinstance(step_id, bool):
            return None
        if step_id != index:
            return None
        if step_id in seen_ids:
            return None
        if not isinstance(objective, str) or not objective.strip():
            return None
        seen_ids.add(step_id)
        steps.append(PlanStep(step_id=step_id, objective=objective.strip()[:1000]))
    return PlanArtifact(plan_summary=summary.strip()[:2000], steps=steps)


def parse_executor_response(
    text: str,
    *,
    expected_step_id: int,
) -> Optional[ExecutorFragment]:
    data = _extract_json_object(text)
    if data is None:
        return None
    step_id = data.get("step_id")
    reason = data.get("reason")
    names = data.get("ordered_names")
    if step_id != expected_step_id:
        return None
    if not isinstance(reason, str) or not reason.strip():
        return None
    if not isinstance(names, list):
        return None
    if any(not isinstance(name, str) or not name.strip() for name in names):
        return None
    return ExecutorFragment(
        step_id=int(step_id),
        reason=reason.strip()[:2000],
        ordered_names=[name.strip() for name in names],
    )


def plan_to_dict(plan: PlanArtifact) -> Dict[str, Any]:
    return {
        "plan_summary": plan.plan_summary,
        "steps": [
            {"step_id": step.step_id, "objective": step.objective}
            for step in plan.steps
        ],
    }


def fragment_to_dict(fragment: ExecutorFragment) -> Dict[str, Any]:
    return {
        "step_id": fragment.step_id,
        "reason": fragment.reason,
        "ordered_names": list(fragment.ordered_names),
    }


def decision_to_dict(decision: MacroDecision) -> Dict[str, Any]:
    return {
        "reason": decision.reason,
        "ordered_names": list(decision.ordered_names),
    }


__all__ = [
    "MAX_PLAN_STEPS",
    "MAX_QUEUE_NAMES",
    "PlanStep",
    "PlanArtifact",
    "ExecutorFragment",
    "parse_plan_response",
    "parse_executor_response",
    "parse_decision_response",
    "plan_to_dict",
    "fragment_to_dict",
    "decision_to_dict",
]
