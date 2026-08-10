"""SunTzu hierarchical plan/verify/execute orchestration."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from API_Tools.llm_caller import call_openai_detailed

from .executor_prompt import build_executor_messages, build_executor_retry_messages
from .plan_verifier_prompt import build_plan_verifier_messages
from .planner_prompt import build_plan_refiner_messages, build_planner_messages
from .schemas import (
    SUNTZU_MAX_EXECUTOR_RETRY,
    SUNTZU_MAX_PLAN_REFINE,
    decision_to_dict,
    parse_decision_response,
    parse_plan_response,
    parse_plan_verification,
    plan_to_dict,
    verification_to_dict,
)
from .trace import TraceRecorder
from .verifier import allowed_canonical_names, verify_macro_queue

AGENT_VERSION = "suntzu-v1"


def _prompt_chars(messages: List[Dict[str, str]]) -> int:
    return sum(len(str(item.get("content") or "")) for item in messages)


def _call_model(
    *,
    messages: List[Dict[str, str]],
    provider: str,
    role: str,
    seq: int,
    llm_call: Callable[..., Dict[str, Any]],
) -> Dict[str, Any]:
    started = time.monotonic()
    api_result = llm_call(messages=messages, model_key=provider)
    content = str(api_result.get("content") or "")
    return {
        "seq": seq,
        "role": role,
        "agent": f"suntzu.{role}",
        "model_key": api_result.get("model_key") or provider,
        "configured_model_key": provider,
        "model": api_result.get("model", "") or "",
        "is_reasoning": api_result.get("is_reasoning"),
        "messages": list(messages),
        "content": content,
        "raw_content": api_result.get("raw_content", "") or content,
        "provider_reasoning": api_result.get("reasoning", "") or "",
        "reasoning_source": api_result.get("reasoning_source", "none") or "none",
        "reasoning_extract_mode": api_result.get("reasoning_extract_mode", "none")
        or "none",
        "error": api_result.get("error", "") or "",
        "wall_elapsed_seconds": round(time.monotonic() - started, 3),
        "prompt_chars": _prompt_chars(messages),
        "output_chars": len(content),
    }


def run_decision(
    *,
    system_prompt: str,
    decision_event: str,
    provider: str,
    log_dir: Optional[str] = None,
    decision_metadata: Optional[Dict[str, Any]] = None,
    canonical_unit_names: Optional[Sequence[str]] = None,
    canonical_upgrade_names: Optional[Sequence[str]] = None,
    max_plan_refine: int = SUNTZU_MAX_PLAN_REFINE,
    max_executor_retry: int = SUNTZU_MAX_EXECUTOR_RETRY,
    llm_call: Callable[..., Dict[str, Any]] = call_openai_detailed,
) -> Dict[str, Any]:
    tracer = TraceRecorder(log_dir)
    llm_calls: List[Dict[str, Any]] = []
    metadata = decision_metadata or {}
    units = list(canonical_unit_names or metadata.get("canonical_unit_names") or [])
    upgrades = list(
        canonical_upgrade_names or metadata.get("canonical_upgrade_names") or []
    )
    # Fallback: extract from metadata only if provided by caller context.
    allowed = allowed_canonical_names(units, upgrades)

    plan_dict: Optional[Dict[str, Any]] = None
    final_decision: Optional[Dict[str, Any]] = None
    status = "invalid"
    plan_stop = "planner_invalid"
    executor_stop = "not_started"
    plan_rounds: List[Dict[str, Any]] = []
    executor_rounds: List[Dict[str, Any]] = []

    tracer.add_event("decision_start", {"metadata": metadata, "provider": provider})

    planner_call = _call_model(
        messages=build_planner_messages(
            system_prompt=system_prompt, decision_event=decision_event
        ),
        provider=provider,
        role="planner",
        seq=1,
        llm_call=llm_call,
    )
    llm_calls.append(planner_call)
    plan = None if planner_call.get("error") else parse_plan_response(planner_call["content"])
    if plan is None:
        plan_stop = "planner_invalid"
    else:
        plan_dict = plan_to_dict(plan)
        current_plan = plan
        for attempt in range(int(max_plan_refine) + 1):
            verifier_call = _call_model(
                messages=build_plan_verifier_messages(
                    system_prompt=system_prompt,
                    decision_event=decision_event,
                    plan=plan_to_dict(current_plan),
                ),
                provider=provider,
                role="plan_verifier",
                seq=len(llm_calls) + 1,
                llm_call=llm_call,
            )
            llm_calls.append(verifier_call)
            round_record: Dict[str, Any] = {
                "attempt": attempt,
                "verification": None,
                "refined_plan": None,
                "error": "",
            }
            if verifier_call.get("error"):
                round_record["error"] = str(verifier_call["error"])
                plan_stop = "plan_verifier_invalid"
                plan_rounds.append(round_record)
                break
            verification = parse_plan_verification(verifier_call["content"])
            if verification is None:
                round_record["error"] = "malformed_plan_verifier"
                plan_stop = "plan_verifier_invalid"
                plan_rounds.append(round_record)
                break
            round_record["verification"] = verification_to_dict(verification)
            if verification.error_number == 0:
                plan_stop = "plan_verified"
                plan_rounds.append(round_record)
                break
            if attempt >= int(max_plan_refine):
                plan_stop = "max_plan_refine"
                plan_rounds.append(round_record)
                break
            refine_call = _call_model(
                messages=build_plan_refiner_messages(
                    system_prompt=system_prompt,
                    decision_event=decision_event,
                    plan=plan_to_dict(current_plan),
                    errors=verification.errors,
                ),
                provider=provider,
                role="plan_refiner",
                seq=len(llm_calls) + 1,
                llm_call=llm_call,
            )
            llm_calls.append(refine_call)
            if refine_call.get("error"):
                round_record["error"] = str(refine_call["error"])
                plan_stop = "plan_refine_invalid"
                plan_rounds.append(round_record)
                break
            refined = parse_plan_response(refine_call["content"])
            if refined is None:
                round_record["error"] = "malformed_plan_refiner"
                plan_stop = "plan_refine_invalid"
                plan_rounds.append(round_record)
                break
            current_plan = refined
            plan_dict = plan_to_dict(current_plan)
            round_record["refined_plan"] = plan_dict
            plan_rounds.append(round_record)

        # Executor stage uses last valid plan even if verifier/refiner stopped soft.
        if plan_dict is not None:
            candidate_payload: Dict[str, Any] = {
                "reason": "",
                "ordered_names": [],
            }
            last_errors: List[str] = []
            for retry in range(int(max_executor_retry) + 1):
                if retry == 0:
                    messages = build_executor_messages(
                        system_prompt=system_prompt,
                        decision_event=decision_event,
                        plan=plan_dict,
                    )
                    role = "executor"
                else:
                    messages = build_executor_retry_messages(
                        system_prompt=system_prompt,
                        decision_event=decision_event,
                        plan=plan_dict,
                        candidate=candidate_payload,
                        errors=last_errors,
                    )
                    role = "executor_retry"
                exec_call = _call_model(
                    messages=messages,
                    provider=provider,
                    role=role,
                    seq=len(llm_calls) + 1,
                    llm_call=llm_call,
                )
                llm_calls.append(exec_call)
                exec_record: Dict[str, Any] = {
                    "attempt": retry,
                    "role": role,
                    "candidate": None,
                    "verification": None,
                    "error": "",
                }
                if exec_call.get("error"):
                    exec_record["error"] = str(exec_call["error"])
                    executor_stop = "executor_provider_error"
                    executor_rounds.append(exec_record)
                    break
                parsed = parse_decision_response(exec_call["content"])
                if parsed is None:
                    exec_record["error"] = "malformed_executor"
                    executor_stop = "executor_invalid"
                    executor_rounds.append(exec_record)
                    last_errors = ["missing_or_malformed_decision"]
                    if retry >= int(max_executor_retry):
                        break
                    continue
                candidate_payload = decision_to_dict(parsed)
                exec_record["candidate"] = candidate_payload
                check_allowed = allowed if allowed else list(parsed.ordered_names)
                verification = verify_macro_queue(parsed, allowed_names=check_allowed)
                exec_record["verification"] = verification
                executor_rounds.append(exec_record)
                if verification["valid"]:
                    final_decision = decision_to_dict(parsed)
                    status = "completed"
                    executor_stop = "queue_verified"
                    break
                last_errors = list(verification["errors"])
                if retry >= int(max_executor_retry):
                    executor_stop = "max_executor_retry"
                    # Last syntactically valid parse is accepted after retries.
                    final_decision = decision_to_dict(parsed)
                    status = "completed"
                    break

    result = {
        "agent_version": AGENT_VERSION,
        "mode": "suntzu",
        "run_id": tracer.run_id,
        "decision": final_decision,
        "plan": plan_dict,
        "plan_rounds": plan_rounds,
        "executor_rounds": executor_rounds,
        "stop_reason": plan_stop if status != "completed" else executor_stop,
        "plan_stop_reason": plan_stop,
        "executor_stop_reason": executor_stop,
        "final_decision": final_decision,
        "model_call_count": len(llm_calls),
        "llm_calls": llm_calls,
        "orchestration": {
            "plan_stop_reason": plan_stop,
            "executor_stop_reason": executor_stop,
            "max_plan_refine": int(max_plan_refine),
            "max_executor_retry": int(max_executor_retry),
        },
        "status": status,
        "log_path": None,
        "decision_metadata": metadata,
    }
    result["log_path"] = tracer.finalize(result)
    return result


__all__ = ["AGENT_VERSION", "run_decision"]
