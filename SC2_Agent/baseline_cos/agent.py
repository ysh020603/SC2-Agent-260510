"""CoS L1 summary → L2 commander orchestration."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from API_Tools.llm_caller import call_openai_detailed

from .l1_prompt import build_l1_messages
from .l2_prompt import build_l2_messages
from .schemas import (
    COS_HISTORY_SIZE,
    decision_to_dict,
    l1_to_dict,
    parse_decision_response,
    parse_l1_response,
)
from .state import CoSState
from .trace import TraceRecorder

AGENT_VERSION = "cos-v1"


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
        "agent": f"cos.{role}",
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
    cos_state: Optional[CoSState] = None,
    log_dir: Optional[str] = None,
    decision_metadata: Optional[Dict[str, Any]] = None,
    max_history: int = COS_HISTORY_SIZE,
    llm_call: Callable[..., Dict[str, Any]] = call_openai_detailed,
) -> Dict[str, Any]:
    state = cos_state if cos_state is not None else CoSState(max_history=max_history)
    state.max_history = int(max_history)
    tracer = TraceRecorder(log_dir)
    llm_calls: List[Dict[str, Any]] = []
    final_decision: Optional[Dict[str, Any]] = None
    l1_payload: Optional[Dict[str, Any]] = None
    status = "invalid"
    stop_reason = "l1_invalid"
    history_before = len(state.l1_history)

    tracer.add_event(
        "decision_start",
        {
            "metadata": decision_metadata or {},
            "provider": provider,
            "history_size_before": history_before,
        },
    )

    l1_call = _call_model(
        messages=build_l1_messages(
            system_prompt=system_prompt, decision_event=decision_event
        ),
        provider=provider,
        role="l1",
        seq=1,
        llm_call=llm_call,
    )
    llm_calls.append(l1_call)

    if not l1_call.get("error"):
        l1 = parse_l1_response(l1_call["content"])
        if l1 is not None:
            l1_payload = l1_to_dict(l1)
            state.append_l1(l1_payload)
            l2_call = _call_model(
                messages=build_l2_messages(
                    system_prompt=system_prompt,
                    decision_event=decision_event,
                    l1_history=state.l1_history,
                ),
                provider=provider,
                role="l2",
                seq=2,
                llm_call=llm_call,
            )
            llm_calls.append(l2_call)
            if l2_call.get("error"):
                stop_reason = "l2_provider_error"
            else:
                decision = parse_decision_response(l2_call["content"])
                if decision is None:
                    stop_reason = "l2_invalid"
                else:
                    final_decision = decision_to_dict(decision)
                    status = "completed"
                    stop_reason = "l2_completed"
        else:
            stop_reason = "l1_invalid"
    else:
        stop_reason = "l1_provider_error"

    result = {
        "agent_version": AGENT_VERSION,
        "mode": "cos",
        "run_id": tracer.run_id,
        "decision": final_decision,
        "l1": l1_payload,
        "history_size": len(state.l1_history),
        "history_size_before": history_before,
        "stop_reason": stop_reason,
        "final_decision": final_decision,
        "model_call_count": len(llm_calls),
        "llm_calls": llm_calls,
        "orchestration": {
            "stop_reason": stop_reason,
            "max_history": int(state.max_history),
            "history_size": len(state.l1_history),
        },
        "status": status,
        "log_path": None,
        "decision_metadata": decision_metadata or {},
        "cos_state": state,
    }
    result["log_path"] = tracer.finalize(
        {k: v for k, v in result.items() if k != "cos_state"}
    )
    return result


__all__ = ["AGENT_VERSION", "COS_HISTORY_SIZE", "run_decision"]
