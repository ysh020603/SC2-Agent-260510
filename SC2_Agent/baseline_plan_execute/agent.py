"""Plan-and-Execute orchestration for one frozen macro decision."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from API_Tools.llm_caller import call_openai_detailed

from .decision_prompt import MacroDecision
from .executor_prompt import build_executor_messages
from .planner_prompt import build_planner_messages
from .schemas import (
    MAX_QUEUE_NAMES,
    decision_to_dict,
    fragment_to_dict,
    parse_executor_response,
    parse_plan_response,
    plan_to_dict,
)
from .trace import TraceRecorder

AGENT_VERSION = "plan-execute-v1"


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
    elapsed = round(time.monotonic() - started, 3)
    content = str(api_result.get("content") or "")
    return {
        "seq": seq,
        "role": role,
        "agent": f"plan_execute.{role}",
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
        "wall_elapsed_seconds": elapsed,
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
    llm_call: Callable[..., Dict[str, Any]] = call_openai_detailed,
) -> Dict[str, Any]:
    """Run Planner once, then sequential Executors on a frozen context."""
    tracer = TraceRecorder(log_dir)
    llm_calls: List[Dict[str, Any]] = []
    executor_steps: List[Dict[str, Any]] = []
    orchestration: Dict[str, Any] = {
        "planner_status": "pending",
        "executor_status": "pending",
        "queue_length_violation": False,
        "error": "",
    }
    status = "invalid"
    plan_dict: Optional[Dict[str, Any]] = None
    final_decision: Optional[Dict[str, Any]] = None

    tracer.add_event(
        "decision_start",
        {"metadata": decision_metadata or {}, "provider": provider},
    )

    planner_messages = build_planner_messages(
        system_prompt=system_prompt,
        decision_event=decision_event,
    )
    planner_call = _call_model(
        messages=planner_messages,
        provider=provider,
        role="planner",
        seq=1,
        llm_call=llm_call,
    )
    llm_calls.append(planner_call)
    tracer.add_event("planner_call", {"call": {k: v for k, v in planner_call.items() if k != "messages"}})

    if planner_call.get("error"):
        orchestration["planner_status"] = "provider_error"
        orchestration["error"] = str(planner_call["error"])
    else:
        plan = parse_plan_response(planner_call["content"])
        if plan is None:
            orchestration["planner_status"] = "malformed"
            orchestration["error"] = "malformed_planner_response"
        else:
            orchestration["planner_status"] = "ok"
            plan_dict = plan_to_dict(plan)
            tracer.add_event("plan_parsed", {"plan": plan_dict})

            accumulated: List[str] = []
            previous_results: List[Dict[str, Any]] = []
            failed = False
            for step in plan.steps:
                exec_messages = build_executor_messages(
                    system_prompt=system_prompt,
                    decision_event=decision_event,
                    plan=plan,
                    step=step,
                    previous_results=previous_results,
                    accumulated_queue=accumulated,
                )
                exec_call = _call_model(
                    messages=exec_messages,
                    provider=provider,
                    role="executor",
                    seq=len(llm_calls) + 1,
                    llm_call=llm_call,
                )
                llm_calls.append(exec_call)
                step_record: Dict[str, Any] = {
                    "step_id": step.step_id,
                    "step": {"step_id": step.step_id, "objective": step.objective},
                    "input_previous_results": list(previous_results),
                    "output_fragment": None,
                    "error": "",
                }
                if exec_call.get("error"):
                    step_record["error"] = str(exec_call["error"])
                    orchestration["executor_status"] = "provider_error"
                    orchestration["error"] = (
                        f"executor_step_{step.step_id}_provider_error"
                    )
                    executor_steps.append(step_record)
                    failed = True
                    break
                fragment = parse_executor_response(
                    exec_call["content"],
                    expected_step_id=step.step_id,
                )
                if fragment is None:
                    step_record["error"] = "malformed_executor_response"
                    orchestration["executor_status"] = "malformed"
                    orchestration["error"] = (
                        f"executor_step_{step.step_id}_malformed"
                    )
                    executor_steps.append(step_record)
                    failed = True
                    break
                fragment_dict = fragment_to_dict(fragment)
                step_record["output_fragment"] = fragment_dict
                executor_steps.append(step_record)
                previous_results.append(fragment_dict)
                accumulated.extend(fragment.ordered_names)
                tracer.add_event(
                    "executor_step",
                    {"step_id": step.step_id, "fragment": fragment_dict},
                )

            if not failed:
                if len(accumulated) > MAX_QUEUE_NAMES:
                    orchestration["executor_status"] = "queue_length_violation"
                    orchestration["queue_length_violation"] = True
                    orchestration["error"] = "queue_length_violation"
                else:
                    orchestration["executor_status"] = "ok"
                    decision = MacroDecision(
                        reason=plan.plan_summary,
                        ordered_names=list(accumulated),
                    )
                    final_decision = decision_to_dict(decision)
                    status = "completed"

    result = {
        "agent_version": AGENT_VERSION,
        "mode": "plan-execute",
        "run_id": tracer.run_id,
        "decision": final_decision,
        "plan": plan_dict,
        "executor_steps": executor_steps,
        "final_decision": final_decision,
        "model_call_count": len(llm_calls),
        "llm_calls": llm_calls,
        "orchestration": orchestration,
        "status": status,
        "log_path": None,
        "decision_metadata": decision_metadata or {},
    }
    result["log_path"] = tracer.finalize(result)
    return result


__all__ = ["AGENT_VERSION", "run_decision"]
