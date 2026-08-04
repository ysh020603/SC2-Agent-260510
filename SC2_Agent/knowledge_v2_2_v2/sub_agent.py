"""Fresh, tool-using DataSubAgent sessions for V2.2."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .query.search_tools import DEFAULT_DATA_PATH

from .contracts import parse_json_object, validate_sub_reply
from .model_view import EvidenceReferenceMap
from .runtime import LLMInvoker, assistant_message
from .tool_registry import ToolRegistry


ROOT = Path(__file__).resolve().parent
MAX_SUB_TOOL_ROUNDS = 5
MAX_TOOL_RESULT_CHARS = 40_000


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").strip()


def _normalize_tool_call(call: Any) -> tuple[str, str, dict[str, Any]]:
    if hasattr(call, "model_dump"):
        call = call.model_dump()
    if not isinstance(call, dict):
        raise TypeError("Invalid tool call payload.")
    function = call.get("function") or {}
    call_id = str(call.get("id") or uuid.uuid4().hex)
    name = str(function.get("name") or "")
    raw_arguments = function.get("arguments") or "{}"
    arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
    if not isinstance(arguments, dict):
        raise TypeError("Tool-call arguments must decode to an object.")
    return call_id, name, arguments


class DataSubAgent:
    def __init__(
        self,
        invoker: LLMInvoker,
        recorder: Any,
        data_path: str | Path = DEFAULT_DATA_PATH,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.invoker = invoker
        self.recorder = recorder
        self.data_path = data_path
        self.registry = registry or ToolRegistry()

    def run(self, question: str, main_round: int) -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        self.recorder.record("sub_session_started", {
            "session_id": session_id,
            "main_round": main_round,
            "question": question,
        })
        system = "\n\n".join([
            _read("prompts/sub_system.md"),
            _read("context/query_conventions.md"),
            _read("context/evidence_references.md"),
            _read("context/field_mapping.md"),
            _read("context/graph_traversal_policy.md"),
            _read("context/entity_canonicalization.md"),
            "# Available Tool Catalog\n" + self.registry.catalog_text(),
            (
                "# Tool Selection Protocol\n"
                "Before tools are enabled, return one JSON object with selected_tools and selection_summary. "
                "Select at most four tool names. Do not select query_relation_evidence initially; it is enabled "
                "automatically after a short evidence_ref exists. Do not provide tool arguments yet."
            ),
        ])
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]
        selection_result = self.invoker(
            f"sub_{session_id}_select_tools", messages
        )
        selection_content = selection_result.get("content", "")
        try:
            selection = parse_json_object(selection_content)
            selected = self.registry.validate_selection(selection.get("selected_tools") or [])
            selected = [name for name in selected if name != "query_relation_evidence"]
            if not selected:
                raise ValueError("Initial selection must contain at least one non-evidence tool.")
            fallback_used = False
        except Exception as exc:
            selected = [
                name
                for name in self.registry.fallback_selection(question)
                if name != "query_relation_evidence"
            ][:4]
            selection = {"selected_tools": selected, "selection_summary": "Local catalog fallback."}
            fallback_used = True
            self.recorder.record("sub_tool_selection_fallback", {
                "session_id": session_id,
                "error": exc,
                "selected_tools": selected,
            })
        if "query type: combat_capability" in question.lower():
            required = ["query_combat_capabilities", "query_enemy_response_candidates"]
            selected = (required + [name for name in selected if name not in required])[:4]
            selection["selection_summary"] = (
                "Orchestrator-enforced combat layer verification using structured weapons, "
                "followed by capability-gated response candidates."
            )
        self.recorder.record("sub_tool_selection", {
            "session_id": session_id,
            "selected_tools": selected,
            "selection_summary": selection.get("selection_summary", ""),
            "fallback_used": fallback_used,
        })
        messages.append({"role": "assistant", "content": selection_content or json.dumps(selection)})
        messages.append({
            "role": "user",
            "content": (
                "The orchestrator has validated the selection. The selected tool schemas are now enabled. "
                "Use tool calls until the focused question is supported, then return the required final JSON object."
            ),
        })
        native_tools = self.registry.openai_tools(selected)
        evidence_references = EvidenceReferenceMap()
        observations: list[dict[str, Any]] = []
        final_content = ""
        for tool_round in range(MAX_SUB_TOOL_ROUNDS):
            result = self.invoker(
                f"sub_{session_id}_tool_round_{tool_round + 1}",
                messages,
                tools=native_tools,
            )
            raw_message = result.get("raw_message") or {}
            tool_calls = raw_message.get("tool_calls") or []
            if not tool_calls:
                final_content = result.get("content", "")
                messages.append(assistant_message(result))
                break
            messages.append(assistant_message(result))
            for call in tool_calls:
                call_id = uuid.uuid4().hex
                name = ""
                arguments: dict[str, Any] = {}
                try:
                    call_id, name, arguments = _normalize_tool_call(call)
                    request = {
                        "session_id": session_id,
                        "tool_round": tool_round,
                        "tool_call_id": call_id,
                        "tool": name,
                        "arguments": arguments,
                    }
                    self.recorder.record("tool_request", request)
                    tool_result = self.registry.execute(
                        name,
                        arguments,
                        data_path=self.data_path,
                        evidence_references=evidence_references,
                    )
                    observation = {**request, "result": tool_result}
                except Exception as exc:
                    observation = {
                        "session_id": session_id,
                        "tool_round": tool_round,
                        "tool_call_id": call_id,
                        "tool": name,
                        "arguments": arguments,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    tool_result = {"error": observation["error"]}
                model_tool_result, compaction = evidence_references.compact(tool_result)
                raw_content = json.dumps(tool_result, ensure_ascii=False, default=str)
                tool_content = json.dumps(model_tool_result, ensure_ascii=False, default=str)
                compaction.update({
                    "raw_chars": len(raw_content),
                    "model_chars": len(tool_content),
                    "saved_chars": len(raw_content) - len(tool_content),
                    "truncated": len(tool_content) > MAX_TOOL_RESULT_CHARS,
                })
                observation["model_view_compaction"] = compaction
                observations.append(observation)
                self.recorder.record("tool_response", observation)
                if len(tool_content) > MAX_TOOL_RESULT_CHARS:
                    tool_content = tool_content[:MAX_TOOL_RESULT_CHARS] + "\n[truncated]"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": tool_content,
                })
            if evidence_references.has_references and "query_relation_evidence" not in selected:
                native_tools = self.registry.openai_tools(
                    [*selected, "query_relation_evidence"],
                    maximum=len(selected) + 1,
                )
        if not final_content:
            messages.append({
                "role": "user",
                "content": (
                    "The tool-round limit has been reached. Do not call more tools. "
                    "Return the required final JSON object using only the observations already available. "
                    "If evidence is incomplete, include partial candidates, confirmed fields, and limitations."
                ),
            })
            try:
                summary_result = self.invoker(
                    f"sub_{session_id}_tool_limit_summary", messages
                )
                final_content = summary_result.get("content", "")
            except Exception as exc:
                self.recorder.record("sub_tool_limit_summary_failed", {
                    "session_id": session_id,
                    "error": f"{type(exc).__name__}: {exc}",
                })
            if not final_content:
                final_content = json.dumps({
                    "answer": "The tool-round limit was reached before a conclusive reply was produced.",
                    "confidence": "low",
                    "entities_mentioned": [],
                    "candidate_entities": [],
                    "evidence_summary": "Available tool observations were incomplete.",
                    "limitations": ["DataSubAgent tool-round limit reached."],
                })
        try:
            reply = validate_sub_reply(parse_json_object(final_content))
        except Exception as exc:
            reply = {
                "answer": final_content.strip() or "No answer was returned.",
                "confidence": "low",
                "entities_mentioned": [],
                "candidate_entities": [],
                "evidence_summary": "The model reply did not match the structured reply contract.",
                "limitations": [f"Reply contract error: {type(exc).__name__}"],
            }
        session = {
            "session_id": session_id,
            "main_round": main_round,
            "question": question,
            "selected_tools": selected,
            "reply": reply,
            "observations": observations,
        }
        self.recorder.record("sub_summary", {
            "session_id": session_id,
            "main_round": main_round,
            "reply": reply,
        })
        return session


__all__ = ["DataSubAgent", "MAX_SUB_TOOL_ROUNDS"]
