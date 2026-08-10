"""Parsers for HIMA advisor / leader artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .decision_prompt import MacroDecision, _extract_json_object, parse_decision_response

ADVISOR_IDS = ("A", "B", "C")


@dataclass(frozen=True)
class AdvisorArtifact:
    advisor: str
    assessment: str
    suggested_actions: List[str]


def parse_advisor_response(
    text: str,
    *,
    expected_advisor: str,
) -> Optional[AdvisorArtifact]:
    data = _extract_json_object(text)
    if data is None:
        return None
    advisor = data.get("advisor")
    assessment = data.get("assessment")
    actions = data.get("suggested_actions")
    if advisor != expected_advisor:
        return None
    if not isinstance(assessment, str) or not assessment.strip():
        return None
    if not isinstance(actions, list):
        return None
    if any(not isinstance(name, str) or not name.strip() for name in actions):
        return None
    return AdvisorArtifact(
        advisor=str(advisor),
        assessment=assessment.strip()[:2000],
        suggested_actions=[name.strip() for name in actions],
    )


def advisor_to_dict(item: AdvisorArtifact) -> Dict[str, Any]:
    return {
        "advisor": item.advisor,
        "assessment": item.assessment,
        "suggested_actions": list(item.suggested_actions),
    }


def decision_to_dict(decision: MacroDecision) -> Dict[str, Any]:
    return {"reason": decision.reason, "ordered_names": list(decision.ordered_names)}


__all__ = [
    "ADVISOR_IDS",
    "AdvisorArtifact",
    "MacroDecision",
    "parse_advisor_response",
    "parse_decision_response",
    "advisor_to_dict",
    "decision_to_dict",
]
