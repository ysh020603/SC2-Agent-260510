"""Tool-free DataSubAgent used by the V2 no-knowledge control mode."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from SC2_Agent.knowledge_v2_2_v2.contracts import parse_json_object, validate_sub_reply
from SC2_Agent.knowledge_v2_2_v2.runtime import LLMInvoker


ROOT = Path(__file__).resolve().parent


class DataSubAgent:
    """Answer one focused question without exposing or querying repository data."""

    def __init__(self, invoker: LLMInvoker, recorder: Any, **_: Any) -> None:
        self.invoker = invoker
        self.recorder = recorder

    def run(self, question: str, main_round: int) -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        self.recorder.record("sub_session_started", {
            "session_id": session_id,
            "main_round": main_round,
            "question": question,
            "knowledge_database_access": False,
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
                "evidence_summary": "The model reply did not match the structured reply contract.",
                "limitations": [
                    f"Reply contract error: {type(exc).__name__}",
                ],
            }
        session = {
            "session_id": session_id,
            "main_round": main_round,
            "question": question,
            "selected_tools": [],
            "reply": reply,
            "observations": [],
            "answer_source": "model_prior",
            "knowledge_database_access": False,
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
