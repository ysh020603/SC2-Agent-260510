"""Public knowledge-assisted macro decision entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from API_Tools.llm_caller import load_agent_pool

from .main_agent import MainAgent
from .query.data_store import get_dataset_store
from .query.search_tools import DEFAULT_DATA_PATH
from .runtime import LLMInvoker, V2TraceRecorder
from .sub_agent import DataSubAgent


DEFAULT_PROVIDER = "Kimi-k2.5"


def get_provider_catalog() -> dict[str, dict[str, Any]]:
    pool = load_agent_pool().get("llm_agents_pool") or {}
    return {key: dict(value) for key, value in pool.items() if isinstance(value, dict)}


def run_decision(
    *,
    system_prompt: str,
    decision_event: str,
    provider: str = DEFAULT_PROVIDER,
    model: str | None = None,
    subagent_provider: str | None = None,
    subagent_model: str | None = None,
    data_path: str | Path = DEFAULT_DATA_PATH,
    log_dir: str | Path | None = None,
    decision_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one fresh V2.2 MainAgent/DataSubAgent macro decision session."""

    recorder = V2TraceRecorder(decision_event, log_dir=log_dir)
    result: dict[str, Any] | None = None
    try:
        dataset_metadata = get_dataset_store(data_path).metadata()
        recorder.record("dataset_loaded", dataset_metadata)
        recorder.record("decision_context_loaded", decision_metadata or {})
        resolved_subagent_provider = (subagent_provider or provider).strip()
        reasoning_trace: list[dict[str, Any]] = []
        main_invoker = LLMInvoker(
            recorder,
            provider,
            model,
            agent_role="main_agent",
            trace=reasoning_trace,
        )
        subagent_invoker = LLMInvoker(
            recorder,
            resolved_subagent_provider,
            subagent_model,
            agent_role="data_subagent",
            trace=reasoning_trace,
        )
        subagent = DataSubAgent(subagent_invoker, recorder, data_path=data_path)
        mainagent = MainAgent(main_invoker, recorder)
        decision, decisions, sessions = mainagent.run(
            system_prompt,
            decision_event,
            subagent.run,
        )
        tool_results = [item for session in sessions for item in session["observations"]]
        result = {
            "agent_version": "decision-data-v2.2",
            "run_id": recorder.run_id,
            "log_path": str(recorder.trace_path),
            "provider": provider,
            "mainagent_provider": provider,
            "data_subagent_provider": resolved_subagent_provider,
            "reasoning_enabled": bool(
                main_invoker.reasoning_mode is True
                or subagent_invoker.reasoning_mode is True
            ),
            "reasoning_policy": "per_role_api_profile",
            "mainagent_reasoning_enabled": main_invoker.reasoning_mode,
            "data_subagent_reasoning_enabled": subagent_invoker.reasoning_mode,
            "dataset": dataset_metadata,
            "routing": {
                "strategy": "macro_main_optional_data_subagent",
                "knowledge_query_used": bool(sessions),
            },
            "decision_metadata": dict(decision_metadata or {}),
            "main_decisions": decisions,
            "subagent_sessions": sessions,
            "tool_results": tool_results,
            "reasoning_trace": reasoning_trace,
            "decision": {
                "reason": decision["reason"],
                "ordered_names": list(decision["ordered_names"] or []),
            },
        }
        recorder.finalize(result, status="completed")
        return result
    except Exception as exc:
        recorder.finalize(result, status="failed", error=exc)
        raise


__all__ = [
    "DEFAULT_PROVIDER",
    "get_provider_catalog",
    "run_decision",
]
