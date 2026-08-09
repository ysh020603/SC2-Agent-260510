"""Provider-independent READ_SKILL / FINAL_DECISION JSON protocol."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from .schema import FinalDecision, ProtocolParseResult, ReadSkillRequest


MAX_ORDERED_NAMES = 40


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[A-Za-z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def parse_agent_response(text: str) -> ProtocolParseResult:
    data = extract_json_object(text)
    if data is None:
        return ProtocolParseResult(error="response is not a JSON object")
    response_type = data.get("type")
    if response_type == "read_skill":
        if set(data) != {"type", "node_id"}:
            return ProtocolParseResult(error="READ_SKILL has unexpected fields")
        node_id = data.get("node_id")
        if not isinstance(node_id, str) or not node_id.strip():
            return ProtocolParseResult(error="READ_SKILL node_id must be non-empty")
        return ProtocolParseResult(request=ReadSkillRequest(node_id=node_id.strip()))
    if response_type == "decision":
        if set(data) != {"type", "reason", "ordered_names"}:
            return ProtocolParseResult(error="FINAL_DECISION has unexpected fields")
        reason = data.get("reason")
        names = data.get("ordered_names")
        if not isinstance(reason, str) or not reason.strip():
            return ProtocolParseResult(error="decision reason must be non-empty")
        if not isinstance(names, list) or any(not isinstance(name, str) or not name.strip() for name in names):
            return ProtocolParseResult(error="ordered_names must be a list of names")
        if len(names) > MAX_ORDERED_NAMES:
            return ProtocolParseResult(
                error=f"ordered_names must contain at most {MAX_ORDERED_NAMES} names; shorten the queue"
            )
        return ProtocolParseResult(
            decision=FinalDecision(
                reason=reason.strip()[:2000],
                ordered_names=[name.strip() for name in names],
            )
        )
    return ProtocolParseResult(error="type must be read_skill or decision")
