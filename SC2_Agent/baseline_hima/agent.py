"""HIMA independent-advisors → leader orchestration."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from API_Tools.llm_caller import call_openai_detailed

from .advisor_prompt import build_advisor_messages
from .leader_prompt import build_leader_messages
from .schemas import (
    ADVISOR_IDS,
    advisor_to_dict,
    decision_to_dict,
    parse_advisor_response,
    parse_decision_response,
)
from .trace import TraceRecorder

AGENT_VERSION = "hima-v1"


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
        "agent": f"hima.{role}",
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
    llm_call: Callable[..., Dict[str, Any]] = call_openai_detailed,
) -> Dict[str, Any]:
    tracer = TraceRecorder(log_dir)
    llm_calls: List[Dict[str, Any]] = []
    advisor_records: List[Dict[str, Any]] = []
    valid_advisors: List[Dict[str, Any]] = []
    final_decision: Optional[Dict[str, Any]] = None
    status = "invalid"
    stop_reason = "no_valid_advisors"

    tracer.add_event(
        "decision_start",
        {"metadata": decision_metadata or {}, "provider": provider},
    )

    for advisor_id in ADVISOR_IDS:
        role = f"advisor_{advisor_id.lower()}"
        messages = build_advisor_messages(
            system_prompt=system_prompt,
            decision_event=decision_event,
            advisor_id=advisor_id,
        )
        # Independence check material: each advisor sees only frozen context.
        call = _call_model(
            messages=messages,
            provider=provider,
            role=role,
            seq=len(llm_calls) + 1,
            llm_call=llm_call,
        )
        llm_calls.append(call)
        record: Dict[str, Any] = {
            "advisor": advisor_id,
            "status": "invalid",
            "output": None,
            "error": "",
        }
        if call.get("error"):
            record["error"] = str(call["error"])
        else:
            parsed = parse_advisor_response(
                call["content"], expected_advisor=advisor_id
            )
            if parsed is None:
                record["error"] = "malformed_advisor"
            else:
                payload = advisor_to_dict(parsed)
                record["status"] = "ok"
                record["output"] = payload
                valid_advisors.append(payload)
        advisor_records.append(record)

    if not valid_advisors:
        stop_reason = "no_valid_advisors"
    else:
        leader_call = _call_model(
            messages=build_leader_messages(
                system_prompt=system_prompt,
                decision_event=decision_event,
                advisors=valid_advisors,
            ),
            provider=provider,
            role="leader",
            seq=len(llm_calls) + 1,
            llm_call=llm_call,
        )
        llm_calls.append(leader_call)
        if leader_call.get("error"):
            stop_reason = "leader_provider_error"
        else:
            decision = parse_decision_response(leader_call["content"])
            if decision is None:
                stop_reason = "leader_invalid"
            else:
                final_decision = decision_to_dict(decision)
                status = "completed"
                stop_reason = "leader_completed"

    result = {
        "agent_version": AGENT_VERSION,
        "mode": "hima",
        "run_id": tracer.run_id,
        "decision": final_decision,
        "advisors": advisor_records,
        "valid_advisor_count": len(valid_advisors),
        "stop_reason": stop_reason,
        "final_decision": final_decision,
        "model_call_count": len(llm_calls),
        "llm_calls": llm_calls,
        "orchestration": {
            "stop_reason": stop_reason,
            "valid_advisor_count": len(valid_advisors),
            "advisor_ids": list(ADVISOR_IDS),
        },
        "status": status,
        "log_path": None,
        "decision_metadata": decision_metadata or {},
    }
    result["log_path"] = tracer.finalize(result)
    return result


__all__ = ["AGENT_VERSION", "run_decision"]
