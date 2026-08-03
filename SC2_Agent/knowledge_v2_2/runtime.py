"""Shared V2.2 model invocation and message helpers."""

from __future__ import annotations

import time
from typing import Any

from API_Tools.llm_caller import call_openai_detailed, load_agent_pool

from .rate_limiter import acquire_provider_slot
from .trace import TraceRecorder


def resolve_model_key(provider: str, enable_reasoning: bool) -> str:
    pool = load_agent_pool().get("llm_agents_pool") or {}
    current = pool.get(provider)
    if not isinstance(current, dict) or bool(current.get("is_reasoning")) == enable_reasoning:
        return provider
    wanted = provider[:-6] if provider.lower().endswith("_think") else f"{provider}_think"
    for key, value in pool.items():
        if key.lower() == wanted.lower() and bool(value.get("is_reasoning")) == enable_reasoning:
            return key
    return provider


class V2TraceRecorder(TraceRecorder):
    schema_version = "sc2-agent-trace-v2.2"


class LLMInvoker:
    def __init__(
        self,
        recorder: TraceRecorder,
        provider: str,
        model: str | None,
        enable_reasoning: bool,
        *,
        agent_role: str = "agent",
        trace: list[dict[str, Any]] | None = None,
    ) -> None:
        self.recorder = recorder
        self.provider = provider
        self.model = model
        self.enable_reasoning = enable_reasoning
        self.agent_role = agent_role
        self.trace = trace if trace is not None else []

    def __call__(
        self,
        phase: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        reasoning: bool | None = None,
    ) -> dict[str, Any]:
        reasoning_enabled = self.enable_reasoning if reasoning is None else reasoning
        model_key = resolve_model_key(self.provider, reasoning_enabled)
        request_payload: dict[str, Any] = {
            "agent_role": self.agent_role,
            "phase": phase,
            "provider": self.provider,
            "model_key": model_key,
            "reasoning_requested": reasoning_enabled,
            "messages": messages,
            "tool_names": [tool["function"]["name"] for tool in tools or []],
        }
        self.recorder.record("llm_request", request_payload)
        kwargs: dict[str, Any] = {}
        if tools:
            kwargs.update({"tools": tools, "tool_choice": "auto"})
        result: dict[str, Any] = {}
        for attempt in range(3):
            rate_limit_wait_seconds = acquire_provider_slot(model_key, self.model)
            started = time.perf_counter()
            result = call_openai_detailed(
                messages=messages,
                model_key=model_key,
                model=self.model,
                is_reasoning=reasoning_enabled,
                **kwargs,
            )
            result.setdefault("latency_seconds", round(time.perf_counter() - started, 6))
            result.setdefault("rate_limit_wait_seconds", round(rate_limit_wait_seconds, 6))
            result.setdefault("usage", {})
            result.setdefault("finish_reason", "")
            result.setdefault("request_metadata", {
                "tool_names": request_payload["tool_names"],
                "reasoning_requested": reasoning_enabled,
            })
            error = str(result.get("error") or "")
            retryable = any(marker in error.lower() for marker in (
                "429", "500", "502", "503", "504", "overload", "timeout", "temporarily unavailable"
            ))
            if not error or not retryable or attempt == 2:
                break
            delay = 2.0 * (attempt + 1)
            self.recorder.record("llm_retry", {
                "phase": phase,
                "attempt": attempt + 1,
                "delay_seconds": delay,
                "error": error,
            })
            time.sleep(delay)
        if result.get("error"):
            self.recorder.record("llm_error", {"phase": phase, "error": result.get("error")})
            raise RuntimeError(f"LLM call failed for {model_key}: {result['error']}")
        entry = {
            "agent_role": self.agent_role,
            "phase": phase,
            "provider": self.provider,
            "model_key": model_key,
            "model": result.get("model"),
            "is_reasoning": result.get("is_reasoning"),
            "reasoning": result.get("reasoning", ""),
            "reasoning_available": bool(result.get("reasoning")),
            "reasoning_source": result.get("reasoning_source"),
            "reasoning_extract_mode": result.get("reasoning_extract_mode"),
            "content": result.get("content", ""),
            "raw_content": result.get("raw_content", ""),
            "raw_message": result.get("raw_message", {}),
            "usage": result.get("usage", {}),
            "finish_reason": result.get("finish_reason", ""),
            "latency_seconds": result.get("latency_seconds", 0.0),
            "rate_limit_wait_seconds": result.get("rate_limit_wait_seconds", 0.0),
            "request_metadata": result.get("request_metadata", {}),
        }
        self.trace.append(entry)
        self.recorder.record("llm_response", entry)
        return entry


def assistant_message(result: dict[str, Any]) -> dict[str, Any]:
    raw = result.get("raw_message") or {}
    message: dict[str, Any] = {"role": "assistant", "content": raw.get("content")}
    if raw.get("tool_calls"):
        message["tool_calls"] = raw["tool_calls"]
    return message


__all__ = ["LLMInvoker", "V2TraceRecorder", "assistant_message", "resolve_model_key"]
