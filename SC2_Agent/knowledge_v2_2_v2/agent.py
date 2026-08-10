"""Public knowledge-assisted macro decision entry point."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from API_Tools.llm_caller import load_agent_pool

from .main_agent import MainAgent
from .planner import (
    build_queue_audit,
    ledger_lookup,
    ledger_store,
    planning_state_update,
    stabilize_queue_constraints,
)
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
    planning_snapshot: dict[str, Any] | None = None,
    planner_state: dict[str, Any] | None = None,
    knowledge_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one V2 planning decision while preserving match-local static facts."""

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
        ledger = knowledge_ledger if isinstance(knowledge_ledger, dict) else {"facts": {}}

        def ask_with_cache(decision: dict[str, Any], main_round: int) -> dict[str, Any]:
            question = str(decision.get("sub_question") or "").strip()
            cached = ledger_lookup(
                ledger,
                question,
                str(decision.get("query_type") or ""),
                list(decision.get("targets") or []),
            )
            if cached is not None:
                session = {
                    "session_id": f"cache-{main_round}",
                    "main_round": main_round,
                    "question": question,
                    "query_type": decision.get("query_type"),
                    "targets": decision.get("targets") or [],
                    "requested_fields": decision.get("requested_fields") or [],
                    "selected_tools": [],
                    "reply": cached["reply"],
                    "observations": [],
                    "cache_hit": True,
                }
                recorder.record("knowledge_cache_hit", session)
                return session
            routed_question = (
                f"Query type: {decision.get('query_type') or 'general_static_fact'}\n"
                f"Targets: {list(decision.get('targets') or [])}\n"
                f"Requested fields: {list(decision.get('requested_fields') or [])}\n"
                f"Focused question: {question}"
            )
            session = subagent.run(routed_question, main_round)
            session.update({
                "original_question": question,
                "query_type": decision.get("query_type"),
                "targets": decision.get("targets") or [],
                "requested_fields": decision.get("requested_fields") or [],
                "cache_hit": False,
            })
            ledger_store(
                ledger,
                question=question,
                query_type=str(decision.get("query_type") or "general_static_fact"),
                targets=list(decision.get("targets") or []),
                reply=session["reply"],
            )
            return session

        snapshot = planning_snapshot or {}

        preflight_sessions: list[dict[str, Any]] = []
        layer_profile = snapshot.get("attack_layer_profile") or {}
        enemy_layers = layer_profile.get("enemy") or {}
        preflight_targets: list[str] = []
        if layer_profile.get("air_attack_gap"):
            preflight_targets.extend(enemy_layers.get("air_combat_units") or [])
        if layer_profile.get("ground_attack_gap"):
            preflight_targets.extend(enemy_layers.get("ground_combat_units") or [])
        preflight_targets = list(dict.fromkeys(str(item) for item in preflight_targets))
        if preflight_targets:
            preflight_decision = {
                "query_type": "combat_capability",
                "targets": preflight_targets,
                "requested_fields": [
                    "target_layer", "direct_weapons", "cost", "supply",
                    "producer", "prerequisites", "build_time",
                ],
                "sub_question": (
                    "For the observed enemy units " + ", ".join(preflight_targets)
                    + f", verify which {str(snapshot.get('race') or '').capitalize()} macro units can directly attack their air/ground layer, "
                    "including cost, supply, current production route, prerequisites, and build time. "
                    "Exclude semantic counters that cannot directly fire at the target layer."
                ),
            }
            preflight = ask_with_cache(preflight_decision, -1)
            preflight_sessions.append(preflight)
            recorder.record("harness_preflight_knowledge", {
                "task": "verified_attack_layer_response",
                "targets": preflight_targets,
                "cache_hit": bool(preflight.get("cache_hit")),
            })
            decision_event = (
                decision_event
                + "\n\n[Harness Preflight Knowledge Evidence]\n"
                + json.dumps(preflight.get("reply") or {}, ensure_ascii=False)
                + "\nUse this evidence in the highest-priority counter-response task."
            )

        def validate_final(decision: dict[str, Any]) -> dict[str, Any] | None:
            normalized_names, corrections = stabilize_queue_constraints(
                list(decision.get("ordered_names") or []),
                snapshot,
                data_path=data_path,
            )
            if normalized_names != list(decision.get("ordered_names") or []):
                decision["ordered_names"] = normalized_names
                counts: dict[str, int] = {}
                for name in normalized_names:
                    counts[name] = counts.get(name, 0) + 1
                queue_summary = ", ".join(
                    f"{name} x{count}" if count > 1 else name
                    for name, count in counts.items()
                )
                original_lead = str(decision.get("reason") or "").split(".", 1)[0].strip()
                correction_types = ", ".join(
                    dict.fromkeys(str(item.get("type") or "correction") for item in corrections)
                )
                decision["reason"] = (
                    (original_lead + ". " if original_lead else "")
                    + f"Deterministic V2 normalization applied {correction_types}; "
                    + f"the authoritative executable queue is: {queue_summary}."
                )[:2000]
                recorder.record("deterministic_queue_normalization", {
                    "corrections": corrections,
                    "ordered_names": normalized_names,
                })
            audit = build_queue_audit(
                list(decision.get("ordered_names") or []),
                snapshot,
                data_path=data_path,
            )
            enemy_evidence = snapshot.get("enemy_evidence") or {}
            composition = enemy_evidence.get("composition") or {}
            layer_profile = snapshot.get("attack_layer_profile") or {}
            enemy_layers = layer_profile.get("enemy") or {}
            combat_names = set(enemy_layers.get("air_combat_units") or []) | set(
                enemy_layers.get("ground_combat_units") or []
            )
            combat_name_keys = {str(name).lower() for name in combat_names}
            threat_targets = [
                str(name) for name, count in composition.items()
                if str(name).lower() in combat_name_keys
                and isinstance(count, (int, float)) and count >= 4
            ]
            capability_targets = []
            if layer_profile.get("air_attack_gap"):
                capability_targets.extend(enemy_layers.get("air_combat_units") or [])
            if layer_profile.get("ground_attack_gap"):
                capability_targets.extend(enemy_layers.get("ground_combat_units") or [])
            capability_targets = list(dict.fromkeys(str(item) for item in capability_targets))

            def has_matching_fact(query_types: set[str], targets: list[str]) -> bool:
                wanted = {_asset.lower() for _asset in targets}
                for item in (ledger.get("facts") or {}).values():
                    if not isinstance(item, dict) or item.get("query_type") not in query_types:
                        continue
                    known = {str(value).lower() for value in item.get("targets") or []}
                    if not wanted or wanted & known:
                        return True
                return False

            mandatory_query = None
            if capability_targets and not has_matching_fact(
                {"combat_capability"}, capability_targets
            ):
                mandatory_query = {
                    "query_type": "combat_capability",
                    "targets": capability_targets,
                    "reason": (
                        "Observed enemy air/ground combat layer cannot be covered by enough current direct-fire "
                        "weapons. Verify target layers and feasible own-race units before finalizing."
                    ),
                }
            elif threat_targets and not has_matching_fact(
                {"enemy_counter", "combat_capability"}, threat_targets
            ):
                mandatory_query = {
                    "query_type": "enemy_counter",
                    "targets": threat_targets,
                    "reason": "Observed enemy composition has at least four units of a named combat type and no counter evidence is cached.",
                }
            budget_overrun = audit.get("budget_overrun") or {}
            conversion = (
                (audit.get("resource_and_strength_conversion") or {}).get("validation") or {}
            )
            conversion_violations = {
                key: value
                for key, value in conversion.items()
                if key not in {
                    "recommended_gas_structure",
                    # These are harness assembly objectives.  They remain in
                    # the audit for measurement but cannot deadlock an entire
                    # decision when gas, prerequisites, or the 20-item limit
                    # make the exact scalar target unattainable.
                    "mineral_commitment_shortfall",
                    "strength_investment_shortfall",
                    "mobile_strength_investment_shortfall",
                } and (
                    (isinstance(value, bool) and value)
                    or (isinstance(value, (int, float)) and value > 0)
                )
            }
            if conversion_violations and conversion.get("recommended_gas_structure"):
                conversion_violations["recommended_gas_structure"] = conversion[
                    "recommended_gas_structure"
                ]
            validation = {
                "unknown_names": audit.get("unknown_names") or [],
                "prerequisite_violations": audit.get("prerequisite_violations") or [],
                "supply_overbuild": (
                    audit.get("supply_projection")
                    if (audit.get("supply_projection") or {}).get("overbuild_warning")
                    else None
                ),
                "budget_overrun": budget_overrun if any(budget_overrun.values()) else None,
                "resource_and_strength_conversion": conversion_violations or None,
                "mandatory_query": mandatory_query,
            }
            return validation if any(validation.values()) else None

        decision, decisions, sessions = mainagent.run(
            system_prompt,
            decision_event,
            ask_with_cache,
            validate_final,
        )
        sessions = preflight_sessions + sessions
        final_counts: dict[str, int] = {}
        for name in decision.get("ordered_names") or []:
            final_counts[name] = final_counts.get(name, 0) + 1
        final_queue_summary = ", ".join(
            f"{name} x{count}" if count > 1 else name
            for name, count in final_counts.items()
        ) or "empty"
        strategic_lead = str(decision.get("reason") or "").split(".", 1)[0].strip()
        decision["reason"] = (
            (strategic_lead + ". " if strategic_lead else "")
            + f"Authoritative final executable queue: {final_queue_summary}."
        )[:2000]
        tool_results = [item for session in sessions for item in session["observations"]]
        queue_audit = build_queue_audit(
            list(decision.get("ordered_names") or []),
            snapshot,
            data_path=data_path,
        )
        if isinstance(planner_state, dict):
            planner_state["previous_snapshot"] = planning_state_update(
                snapshot,
                float((decision_metadata or {}).get("game_time_seconds") or 0.0),
            )
        actual_sessions = [session for session in sessions if not session.get("cache_hit")]
        result = {
            "agent_version": "decision-data-v2.2-v2",
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
                "strategy": "planning_main_triggered_data_subagent_with_match_cache",
                "knowledge_query_used": bool(actual_sessions),
                "knowledge_cache_hit": any(session.get("cache_hit") for session in sessions),
            },
            "decision_metadata": dict(decision_metadata or {}),
            "main_decisions": decisions,
            "subagent_sessions": sessions,
            "tool_results": tool_results,
            "reasoning_trace": reasoning_trace,
            "planning_snapshot": snapshot,
            "queue_audit": queue_audit,
            "knowledge_ledger_size": len((ledger.get("facts") or {})),
            "knowledge_application": decision.get("knowledge_application") or [],
            "query_skip_reason": decision.get("query_skip_reason"),
            "knowledge_not_used_reason": decision.get("knowledge_not_used_reason"),
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
