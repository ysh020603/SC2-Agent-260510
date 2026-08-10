"""Parsers for Self-Refine Init / Feedback / Refine artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .decision_prompt import MacroDecision, _extract_json_object, parse_decision_response

MAX_REFINE_ROUNDS = 2
MAX_FEEDBACK_ISSUES = 5


@dataclass(frozen=True)
class FeedbackIssue:
    issue: str
    suggestion: str


@dataclass(frozen=True)
class FeedbackArtifact:
    needs_refinement: bool
    summary: str
    issues: List[FeedbackIssue]


def parse_feedback_response(text: str) -> Optional[FeedbackArtifact]:
    data = _extract_json_object(text)
    if data is None:
        return None
    needs = data.get("needs_refinement")
    summary = data.get("summary")
    issues_raw = data.get("issues", [])
    if not isinstance(needs, bool):
        return None
    if not isinstance(summary, str) or not summary.strip():
        return None
    if not isinstance(issues_raw, list):
        return None
    if len(issues_raw) > MAX_FEEDBACK_ISSUES:
        return None
    issues: List[FeedbackIssue] = []
    for item in issues_raw:
        if not isinstance(item, dict):
            return None
        issue = item.get("issue")
        suggestion = item.get("suggestion")
        if not isinstance(issue, str) or not issue.strip():
            return None
        if not isinstance(suggestion, str) or not suggestion.strip():
            return None
        issues.append(
            FeedbackIssue(
                issue=issue.strip()[:1000],
                suggestion=suggestion.strip()[:1000],
            )
        )
    return FeedbackArtifact(
        needs_refinement=needs,
        summary=summary.strip()[:2000],
        issues=issues,
    )


def decision_to_dict(decision: MacroDecision) -> Dict[str, Any]:
    return {
        "reason": decision.reason,
        "ordered_names": list(decision.ordered_names),
    }


def feedback_to_dict(feedback: FeedbackArtifact) -> Dict[str, Any]:
    return {
        "needs_refinement": feedback.needs_refinement,
        "summary": feedback.summary,
        "issues": [
            {"issue": item.issue, "suggestion": item.suggestion}
            for item in feedback.issues
        ],
    }


__all__ = [
    "MAX_REFINE_ROUNDS",
    "MAX_FEEDBACK_ISSUES",
    "FeedbackIssue",
    "FeedbackArtifact",
    "parse_decision_response",
    "parse_feedback_response",
    "decision_to_dict",
    "feedback_to_dict",
    "MacroDecision",
]
