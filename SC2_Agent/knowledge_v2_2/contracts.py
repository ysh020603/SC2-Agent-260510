"""Validated JSON contracts used between the V2.2 orchestrator and agents."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    candidate = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    value = json.loads(candidate)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object.")
    return value


def validate_main_decision(value: dict[str, Any]) -> dict[str, Any]:
    action = value.get("action")
    if action not in {"ask_subagent", "final_decision"}:
        raise ValueError("MainAgent action must be ask_subagent or final_decision.")
    if action == "ask_subagent" and not str(value.get("sub_question") or "").strip():
        raise ValueError("MainAgent must provide a non-empty sub_question.")
    reason = value.get("reason")
    names = value.get("ordered_names")
    if action == "final_decision":
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("MainAgent final_decision must provide a public reason.")
        if not isinstance(names, list):
            raise ValueError("MainAgent final_decision must provide ordered_names as a list.")
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("Every ordered_names entry must be a non-empty string.")
    return {
        "action": action,
        "sub_question": str(value.get("sub_question") or "").strip() or None,
        "decision_summary": str(value.get("decision_summary") or ""),
        "reason": str(reason or "").strip()[:2000] or None,
        "ordered_names": [str(name).strip() for name in names] if isinstance(names, list) else None,
    }


def validate_sub_reply(value: dict[str, Any]) -> dict[str, Any]:
    answer = str(value.get("answer") or "").strip()
    if not answer:
        raise ValueError("DataSubAgent returned an empty answer.")
    confidence = str(value.get("confidence") or "low").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    candidates: list[dict[str, Any]] = []
    for item in value.get("candidate_entities") or []:
        if not isinstance(item, dict):
            continue
        fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
        limitations = item.get("limitations") if isinstance(item.get("limitations"), list) else []
        candidates.append({
            "name": str(item.get("name") or ""),
            "section": str(item.get("section") or "unknown"),
            "role": str(item.get("role") or ""),
            "supporting_relation": str(item.get("supporting_relation") or ""),
            "fields": fields,
            "limitations": [str(entry) for entry in limitations],
        })
    return {
        "answer": answer,
        "confidence": confidence,
        "entities_mentioned": [str(item) for item in value.get("entities_mentioned") or []],
        "candidate_entities": candidates,
        "evidence_summary": str(value.get("evidence_summary") or ""),
        "limitations": [str(item) for item in value.get("limitations") or []],
    }
