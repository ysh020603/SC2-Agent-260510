"""Tool-isolated knowledge-assisted macro MainAgent state machine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .contracts import parse_json_object, validate_main_decision
from .runtime import LLMInvoker


ROOT = Path(__file__).resolve().parent
MAX_MAIN_ROUNDS = 5
MAX_FINAL_VALIDATION_REPAIRS = 2


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
        ask_subagent: Callable[[dict[str, Any], int], dict[str, Any]],
        validate_final: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        system = "\n\n".join([
            system_prompt.strip(),
            _read("context/dataset_overview.md"),
            _read("context/data_usage_guide.md"),
            _read("context/reasoning_policy.md"),
            _read("context/field_mapping.md"),
            _read("context/graph_traversal_policy.md"),
            _read("context/entity_canonicalization.md"),
            _read("context/planning_cycle.md"),
            _read("context/resource_forecast.md"),
            _read("context/knowledge_routing.md"),
            _read("context/enemy_response.md"),
            _read("context/upgrade_policy.md"),
        ])
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": decision_event},
        ]
        decisions: list[dict[str, Any]] = []
        sessions: list[dict[str, Any]] = []
        asked: set[str] = set()
        last_contract_final: dict[str, Any] | None = None

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
                    reasoning=False,
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
                last_contract_final = decision
                validation = validate_final(decision) if validate_final else None
                if validation and main_round + 1 < MAX_MAIN_ROUNDS:
                    self.recorder.record("main_plan_validation_repair", {
                        "main_round": main_round,
                        "validation": validation,
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            "Deterministic V2 validation found a required evidence or queue correction:\n"
                            + json.dumps(validation, ensure_ascii=False)
                            + "\nIf mandatory_query is non-null, your next response MUST be ask_subagent with "
                            "that query_type and targets; do not return another final_decision yet. Otherwise return "
                            "a corrected final_decision: insert missing prerequisites before dependents or remove "
                            "dependents, remove redundant supply providers, and shorten mineral/gas spending that "
                            "exceeds the horizon budget. For resource_and_strength_conversion, remove excess workers, "
                            "meet the minimum mineral and strength commitment with executable combat units, upgrades, "
                            "or production, meet the separate mobile-army investment, keep at most 20 queue items, "
                            "add the recommended gas structure when requested, and cover air/ground "
                            "response shortfalls only with units whose direct weapons hit that target layer. Preserve "
                            "committed-work semantics and canonical names."
                        ),
                    })
                    continue
                if validation:
                    self.recorder.record("main_plan_validation_repair", {
                        "main_round": main_round,
                        "validation": validation,
                        "last_regular_round": True,
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            "The last regular round still failed deterministic validation:\n"
                            + json.dumps(validation, ensure_ascii=False)
                            + "\nThe next response must be a corrected final_decision only."
                        ),
                    })
                    break
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
                session = ask_subagent(decision, main_round)
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
        for final_round in range(MAX_FINAL_VALIDATION_REPAIRS + 1):
            result = self.invoker(
                f"main_round_limit_final_decision_{final_round + 1}",
                messages,
                reasoning=False,
            )
            content = str(result.get("content") or "")
            try:
                decision = validate_main_decision(parse_json_object(content))
            except Exception as error:
                self.recorder.record("main_contract_repair", {
                    "main_round": MAX_MAIN_ROUNDS + final_round,
                    "error": error,
                    "round_limit": True,
                })
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": "The reply was not one complete JSON object. Return a final_decision JSON object only.",
                })
                continue
            if decision["action"] != "final_decision":
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": "The round limit forbids another query. Return final_decision JSON only.",
                })
                continue
            last_contract_final = decision
            decisions.append(decision)
            self.recorder.record("main_decision", {
                "main_round": MAX_MAIN_ROUNDS + final_round,
                "decision": decision,
                "round_limit": True,
                "final_validation_attempt": final_round + 1,
            })
            validation = validate_final(decision) if validate_final else None
            if not validation:
                return decision, decisions, sessions
            self.recorder.record("main_plan_validation_repair", {
                "main_round": MAX_MAIN_ROUNDS + final_round,
                "validation": validation,
                "round_limit": True,
            })
            if validation.get("mandatory_query"):
                raise RuntimeError(
                    "MainAgent reached the final round without completing mandatory knowledge evidence."
                )
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": (
                    "The forced final decision still failed deterministic validation:\n"
                    + json.dumps(validation, ensure_ascii=False)
                    + "\nReturn another final_decision only. Correct every listed issue: remove excess "
                    "workers or supply, add missing prerequisites or the recommended gas structure, meet "
                    "minimum mineral/strength commitments, and cover attack-layer response shortfalls with "
                    "verified direct-fire units including the required mobile share; keep at most 20 queue items. "
                    "Do not ask another subquestion."
                ),
            })
        # The harness validator mutates contract-valid decisions into a safe
        # executable form.  Reuse that form rather than dropping the entire
        # decision because the model repeated malformed forced-final output.
        if last_contract_final is not None:
            validation = validate_final(last_contract_final) if validate_final else None
            if not validation:
                self.recorder.record("main_harness_fallback", {
                    "reason": "forced_final_rounds_exhausted",
                    "ordered_names": last_contract_final.get("ordered_names") or [],
                })
                return last_contract_final, decisions, sessions
        raise RuntimeError("MainAgent could not produce a deterministically valid final queue.")


__all__ = ["MAX_MAIN_ROUNDS", "MainAgent"]
