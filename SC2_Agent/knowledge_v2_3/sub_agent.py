"""Portable V2.3 DataSubAgent using ordinary text completions only."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .contracts import parse_json_object, validate_sub_reply
from .knowledge_router import PortableKnowledgeRouter
from .query.search_tools import DEFAULT_DATA_PATH
from .runtime import LLMInvoker
from .tool_registry import ToolRegistry


ROOT = Path(__file__).resolve().parent


class DataSubAgent:
    def __init__(
        self,
        invoker: LLMInvoker,
        recorder: Any,
        data_path: str | Path = DEFAULT_DATA_PATH,
        registry: ToolRegistry | None = None,
        planning_snapshot: dict[str, Any] | None = None,
    ) -> None:
        self.invoker = invoker
        self.recorder = recorder
        self.data_path = data_path
        self.registry = registry or ToolRegistry()
        self.router = PortableKnowledgeRouter(
            self.registry,
            recorder,
            data_path=data_path,
            planning_snapshot=planning_snapshot,
        )

    def run(self, request: dict[str, Any], main_round: int) -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        question = str(request.get("sub_question") or request.get("question") or "").strip()
        self.recorder.record("sub_session_started", {
            "session_id": session_id,
            "main_round": main_round,
            "question": question,
            "query_type": request.get("query_type"),
            "targets": request.get("targets") or [],
            "protocol": "portable_text_v1",
        })
        packet, observations, selected_tools = self.router.run(request, session_id)
        self.recorder.record("sub_tool_selection", {
            "session_id": session_id,
            "selected_tools": selected_tools,
            "selection_summary": "Deterministic V2.3 query-type router.",
            "fallback_used": False,
            "protocol": "portable_local_orchestrator",
        })

        system = (ROOT / "prompts" / "sub_system.md").read_text(encoding="utf-8").strip()
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "Focused MainAgent question:\n" + question
                    + "\n\nAuthoritative repository evidence packet:\n"
                    + json.dumps(packet, ensure_ascii=False, default=str)
                    + "\n\nSummarize only this packet as the required JSON reply."
                ),
            },
        ]
        answer_source = "repository_data_portable"
        model_error = None
        try:
            result = self.invoker(f"sub_{session_id}_summarize", messages)
            reply = validate_sub_reply(parse_json_object(str(result.get("content") or "")))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            answer_source = "repository_data_deterministic_fallback"
            names = packet.get("recommended_shortlist") or []
            reply = {
                "answer": (
                    "Repository evidence recommends the feasible shortlist: "
                    + ", ".join(str(name) for name in names)
                    if names
                    else "Repository evidence did not establish a feasible candidate."
                ),
                "confidence": "medium" if names else "low",
                "entities_mentioned": [str(name) for name in names],
                "candidate_entities": [],
                "evidence_summary": "Deterministic summary of the V2.3 evidence packet.",
                "limitations": list(packet.get("limitations") or []) + [model_error],
            }

        # Candidate details are supplied by deterministic repository tools, not
        # trusted from free-form model text.
        reply["candidate_entities"] = [
            {
                "name": str(item.get("name") or ""),
                "section": str(item.get("section") or "Unit"),
                "role": "feasible_candidate",
                "supporting_relation": str(item.get("relation") or ""),
                "fields": dict(item),
                "limitations": [],
            }
            for item in packet.get("feasible_candidates") or []
            if isinstance(item, dict) and item.get("name")
        ]
        reply["knowledge_packet"] = packet
        session = {
            "session_id": session_id,
            "main_round": main_round,
            "question": question,
            "query_type": request.get("query_type"),
            "targets": list(request.get("targets") or []),
            "requested_fields": list(request.get("requested_fields") or []),
            "selected_tools": selected_tools,
            "reply": reply,
            "observations": observations,
            "status": packet.get("status"),
            "answer_source": answer_source,
            "model_error": model_error,
            "protocol": "portable_text_v1",
        }
        self.recorder.record("sub_direct_answer", {
            "session_id": session_id,
            "answer_source": answer_source,
            "status": packet.get("status"),
            "protocol": "portable_text_v1",
        })
        self.recorder.record("sub_summary", {
            "session_id": session_id,
            "main_round": main_round,
            "reply": reply,
            "status": packet.get("status"),
        })
        return session


__all__ = ["DataSubAgent"]
