"""Tool-free DataSubAgent used by the V2.3 no-knowledge control mode."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from SC2_Agent.knowledge_v2_3.contracts import parse_json_object, validate_sub_reply
from SC2_Agent.knowledge_v2_3.runtime import LLMInvoker


ROOT = Path(__file__).resolve().parent


class DataSubAgent:
    """Answer one focused question without exposing or querying repository data."""

    def __init__(self, invoker: LLMInvoker, recorder: Any, **_: Any) -> None:
        self.invoker = invoker
        self.recorder = recorder

    def run(self, request: dict[str, Any] | str, main_round: int) -> dict[str, Any]:
        if isinstance(request, dict):
            question = str(
                request.get("sub_question") or request.get("question") or ""
            ).strip()
            query_type = request.get("query_type")
            targets = list(request.get("targets") or [])
            requested_fields = list(request.get("requested_fields") or [])
        else:
            question = str(request or "").strip()
            query_type = None
            targets = []
            requested_fields = []

        session_id = uuid.uuid4().hex
        self.recorder.record("sub_session_started", {
            "session_id": session_id,
            "main_round": main_round,
            "question": question,
            "query_type": query_type,
            "targets": targets,
            "knowledge_database_access": False,
            "protocol": "model_prior_text_v1",
        })
        system = (ROOT / "prompts" / "sub_system.md").read_text(
            encoding="utf-8"
        ).strip()
        messages = [
            {
                "role": "system",
                "content": system,
            },
            {"role": "user", "content": question},
        ]
        result = self.invoker(
            f"sub_{session_id}_direct_answer",
            messages,
            reasoning=False,
        )
        final_content = str(result.get("content") or "")
        try:
            reply = validate_sub_reply(parse_json_object(final_content))
        except Exception as exc:
            reply = {
                "answer": final_content.strip() or "No answer was returned.",
                "confidence": "low",
                "entities_mentioned": [],
                "candidate_entities": [],
                "evidence_summary": (
                    "The model reply did not match the structured reply contract."
                ),
                "limitations": [
                    f"Reply contract error: {type(exc).__name__}",
                ],
            }
        session = {
            "session_id": session_id,
            "main_round": main_round,
            "question": question,
            "query_type": query_type,
            "targets": targets,
            "requested_fields": requested_fields,
            "selected_tools": [],
            "reply": reply,
            "observations": [],
            "answer_source": "model_prior",
            "knowledge_database_access": False,
            "status": "ok",
        }
        self.recorder.record("sub_direct_answer", {
            "session_id": session_id,
            "main_round": main_round,
            "answer_source": "model_prior",
            "knowledge_database_access": False,
            "reply": reply,
        })
        self.recorder.record("sub_summary", {
            "session_id": session_id,
            "main_round": main_round,
            "reply": reply,
        })
        return session


__all__ = ["DataSubAgent"]
