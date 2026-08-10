"""Parsers and constants for SunTzu structural baseline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .decision_prompt import MacroDecision, _extract_json_object, parse_decision_response

SUNTZU_MAX_PLAN_REFINE = 3
SUNTZU_MAX_EXECUTOR_RETRY = 3
MAX_PLAN_COMMANDS = 5
MAX_QUEUE_NAMES = 20


@dataclass(frozen=True)
class PlanArtifact:
    plan_reason: str
    commands: List[str]


@dataclass(frozen=True)
class PlanVerification:
    error_number: int
    errors: List[str]


def parse_plan_response(text: str) -> Optional[PlanArtifact]:
    data = _extract_json_object(text)
    if data is None:
        return None
    reason = data.get("plan_reason")
    commands = data.get("commands")
    if not isinstance(reason, str) or not reason.strip():
        return None
    if not isinstance(commands, list) or not commands:
        return None
    if len(commands) > MAX_PLAN_COMMANDS:
        return None
    if any(not isinstance(item, str) or not item.strip() for item in commands):
        return None
    return PlanArtifact(
        plan_reason=reason.strip()[:2000],
        commands=[item.strip()[:500] for item in commands],
    )


def parse_plan_verification(text: str) -> Optional[PlanVerification]:
    data = _extract_json_object(text)
    if data is None:
        return None
    error_number = data.get("error_number")
    errors = data.get("errors", [])
    if not isinstance(error_number, int) or isinstance(error_number, bool):
        return None
    if error_number < 0:
        return None
    if not isinstance(errors, list):
        return None
    if any(not isinstance(item, str) or not item.strip() for item in errors):
        return None
    if error_number == 0 and errors:
        return None
    if error_number > 0 and not errors:
        return None
    if error_number != len(errors) and error_number > 0:
        # Allow mismatch only if error_number equals len(errors); else invalid.
        return None
    return PlanVerification(
        error_number=error_number,
        errors=[item.strip()[:1000] for item in errors],
    )


def plan_to_dict(plan: PlanArtifact) -> Dict[str, Any]:
    return {"plan_reason": plan.plan_reason, "commands": list(plan.commands)}


def verification_to_dict(item: PlanVerification) -> Dict[str, Any]:
    return {"error_number": item.error_number, "errors": list(item.errors)}


def decision_to_dict(decision: MacroDecision) -> Dict[str, Any]:
    return {"reason": decision.reason, "ordered_names": list(decision.ordered_names)}


__all__ = [
    "SUNTZU_MAX_PLAN_REFINE",
    "SUNTZU_MAX_EXECUTOR_RETRY",
    "MAX_PLAN_COMMANDS",
    "MAX_QUEUE_NAMES",
    "PlanArtifact",
    "PlanVerification",
    "MacroDecision",
    "parse_plan_response",
    "parse_plan_verification",
    "parse_decision_response",
    "plan_to_dict",
    "verification_to_dict",
    "decision_to_dict",
]
