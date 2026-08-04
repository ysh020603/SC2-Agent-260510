"""Tool-isolated knowledge-assisted macro MainAgent state machine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .contracts import parse_json_object, validate_main_decision
from .runtime import LLMInvoker


ROOT = Path(__file__).resolve().parent
MAX_MAIN_ROUNDS = 20


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").strip()


class MainAgent:
    def __init__(self, invoker: LLMInvoker, recorder: Any) -> None:
        self.invoker = invoker
        self.recorder = recorder

    def run(
        self,
        system_prompt: str,
        decision_event: str,
        ask_subagent: Callable[[str, int], dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        system = "\n\n".join([
            system_prompt.strip(),
            _read("context/dataset_overview.md"),
            _read("context/data_usage_guide.md"),
            _read("context/reasoning_policy.md"),
            _read("context/field_mapping.md"),
            _read("context/graph_traversal_policy.md"),
            _read("context/entity_canonicalization.md"),
        ])
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": decision_event},
        ]
        decisions: list[dict[str, Any]] = []
        sessions: list[dict[str, Any]] = []
        asked: set[str] = set()

        for main_round in range(MAX_MAIN_ROUNDS):
            result = self.invoker(f"main_round_{main_round + 1}", messages)
            content = str(result.get("content") or "")
            try:
                decision = validate_main_decision(parse_json_object(content))
            except Exception as first_error:
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous reply did not match the required MainAgent JSON contract. "
                        "Return exactly one valid JSON object now."
                    ),
                })
                repair = self.invoker(
                    f"main_round_{main_round + 1}_repair",
                    messages,
                )
                content = str(repair.get("content") or "")
                decision = validate_main_decision(parse_json_object(content))
                self.recorder.record("main_contract_repair", {
                    "main_round": main_round,
                    "first_error": first_error,
                })

            decisions.append(decision)
            self.recorder.record("main_decision", {
                "main_round": main_round,
                "decision": decision,
            })
            messages.append({"role": "assistant", "content": content})

            if decision["action"] == "final_decision":
                return decision, decisions, sessions

            question = str(decision["sub_question"]).strip()
            normalized = " ".join(question.lower().split())
            if normalized in asked:
                feedback = {
                    "answer": "This exact subquestion has already been answered. Use the previous facts or ask a narrower follow-up.",
                    "confidence": "low",
                    "evidence_summary": "Duplicate request rejected by the orchestrator.",
                    "limitations": ["Duplicate subquestion."],
                }
            else:
                asked.add(normalized)
                session = ask_subagent(question, main_round)
                sessions.append(session)
                feedback = session["reply"]
            messages.append({
                "role": "user",
                "content": "DataSubAgent reply:\n" + json.dumps(feedback, ensure_ascii=False),
            })

        messages.append({
            "role": "user",
            "content": (
                "The maximum number of MainAgent rounds has been reached. Do not ask another "
                "subquestion. Return one valid JSON object with action `final_decision`, a concise "
                "public reason, and ordered_names using only the visible macro allowlist."
            ),
        })
        result = self.invoker("main_round_limit_final_decision", messages)
        decision = validate_main_decision(parse_json_object(str(result.get("content") or "")))
        if decision["action"] != "final_decision":
            raise RuntimeError("MainAgent failed to return final_decision at the round limit.")
        decisions.append(decision)
        self.recorder.record("main_decision", {
            "main_round": MAX_MAIN_ROUNDS,
            "decision": decision,
            "round_limit": True,
        })
        return decision, decisions, sessions


__all__ = ["MAX_MAIN_ROUNDS", "MainAgent"]
