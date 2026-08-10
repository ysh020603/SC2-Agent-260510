"""Self-Refine orchestration for one frozen macro decision."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from API_Tools.llm_caller import call_openai_detailed

from .feedback_prompt import build_feedback_messages
from .init_prompt import build_init_messages
from .refine_prompt import build_refine_messages
from .schemas import (
    MAX_REFINE_ROUNDS,
    decision_to_dict,
    feedback_to_dict,
    parse_decision_response,
    parse_feedback_response,
)
from .trace import TraceRecorder

AGENT_VERSION = "self-refine-v1"


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
        "agent": f"self_refine.{role}",
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
    max_refine_rounds: int = MAX_REFINE_ROUNDS,
    llm_call: Callable[..., Dict[str, Any]] = call_openai_detailed,
) -> Dict[str, Any]:
    """Init → Feedback → Refine loop on a frozen observation."""
    tracer = TraceRecorder(log_dir)
    llm_calls: List[Dict[str, Any]] = []
    rounds: List[Dict[str, Any]] = []
    stop_reason = "init_invalid"
    status = "invalid"
    initial_candidate: Optional[Dict[str, Any]] = None
    final_decision: Optional[Dict[str, Any]] = None
    current: Optional[Dict[str, Any]] = None

    tracer.add_event(
        "decision_start",
        {
            "metadata": decision_metadata or {},
            "provider": provider,
            "max_refine_rounds": int(max_refine_rounds),
        },
    )

    init_messages = build_init_messages(
        system_prompt=system_prompt,
        decision_event=decision_event,
    )
    init_call = _call_model(
        messages=init_messages,
        provider=provider,
        role="init",
        seq=1,
        llm_call=llm_call,
    )
    llm_calls.append(init_call)
    tracer.add_event(
        "init_call",
        {"call": {k: v for k, v in init_call.items() if k != "messages"}},
    )

    if init_call.get("error"):
        stop_reason = "init_provider_error"
    else:
        init_decision = parse_decision_response(init_call["content"])
        if init_decision is None:
            stop_reason = "init_invalid"
        else:
            current = decision_to_dict(init_decision)
            initial_candidate = dict(current)
            final_decision = dict(current)
            status = "completed"
            stop_reason = "critic_satisfied"

            for round_idx in range(1, int(max_refine_rounds) + 1):
                feedback_messages = build_feedback_messages(
                    system_prompt=system_prompt,
                    decision_event=decision_event,
                    candidate=current,
                )
                feedback_call = _call_model(
                    messages=feedback_messages,
                    provider=provider,
                    role="feedback",
                    seq=len(llm_calls) + 1,
                    llm_call=llm_call,
                )
                llm_calls.append(feedback_call)
                round_record: Dict[str, Any] = {
                    "round": round_idx,
                    "feedback": None,
                    "refined_candidate": None,
                    "error": "",
                }

                if feedback_call.get("error"):
                    round_record["error"] = str(feedback_call["error"])
                    stop_reason = "feedback_invalid"
                    rounds.append(round_record)
                    break

                feedback = parse_feedback_response(feedback_call["content"])
                if feedback is None:
                    round_record["error"] = "malformed_feedback"
                    stop_reason = "feedback_invalid"
                    rounds.append(round_record)
                    break

                feedback_dict = feedback_to_dict(feedback)
                round_record["feedback"] = feedback_dict
                tracer.add_event(
                    "feedback",
                    {"round": round_idx, "feedback": feedback_dict},
                )

                if not feedback.needs_refinement:
                    stop_reason = "critic_satisfied"
                    rounds.append(round_record)
                    break

                refine_messages = build_refine_messages(
                    system_prompt=system_prompt,
                    decision_event=decision_event,
                    candidate=current,
                    feedback=feedback_dict,
                )
                refine_call = _call_model(
                    messages=refine_messages,
                    provider=provider,
                    role="refine",
                    seq=len(llm_calls) + 1,
                    llm_call=llm_call,
                )
                llm_calls.append(refine_call)

                if refine_call.get("error"):
                    round_record["error"] = str(refine_call["error"])
                    stop_reason = "refine_invalid"
                    rounds.append(round_record)
                    break

                refined = parse_decision_response(refine_call["content"])
                if refined is None:
                    round_record["error"] = "malformed_refine"
                    stop_reason = "refine_invalid"
                    rounds.append(round_record)
                    break

                refined_dict = decision_to_dict(refined)
                round_record["refined_candidate"] = refined_dict
                current = refined_dict
                final_decision = dict(current)
                rounds.append(round_record)
                tracer.add_event(
                    "refine",
                    {"round": round_idx, "candidate": refined_dict},
                )

                if round_idx >= int(max_refine_rounds):
                    stop_reason = "max_refine_rounds"
                    break

    result = {
        "agent_version": AGENT_VERSION,
        "mode": "self-refine",
        "run_id": tracer.run_id,
        "decision": final_decision,
        "initial_candidate": initial_candidate,
        "rounds": rounds,
        "stop_reason": stop_reason,
        "final_decision": final_decision,
        "model_call_count": len(llm_calls),
        "llm_calls": llm_calls,
        "orchestration": {
            "max_refine_rounds": int(max_refine_rounds),
            "stop_reason": stop_reason,
            "completed_refine_rounds": sum(
                1 for item in rounds if item.get("refined_candidate") is not None
            ),
        },
        "status": status,
        "log_path": None,
        "decision_metadata": decision_metadata or {},
    }
    result["log_path"] = tracer.finalize(result)
    return result


__all__ = ["AGENT_VERSION", "MAX_REFINE_ROUNDS", "run_decision"]
