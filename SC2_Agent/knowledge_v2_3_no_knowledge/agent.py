"""V2.3 planning decision entry point with a tool-free DataSubAgent."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from API_Tools.llm_caller import load_agent_pool
from SC2_Agent.knowledge_v2_3.main_agent import MainAgent
from SC2_Agent.knowledge_v2_3.planner import (
    build_queue_audit,
    ledger_lookup,
    ledger_store,
    planning_state_update,
    stabilize_queue_constraints,
)
from SC2_Agent.knowledge_v2_3.query.data_store import get_dataset_store
from SC2_Agent.knowledge_v2_3.query.search_tools import DEFAULT_DATA_PATH
from SC2_Agent.knowledge_v2_3.runtime import LLMInvoker, V2TraceRecorder

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
    """Run V2.3 planning while preventing SubAgent access to the knowledge database."""

    recorder = V2TraceRecorder(decision_event, log_dir=log_dir)
    result: dict[str, Any] | None = None
    try:
        # V2.3's deterministic planner/auditor still uses the same static dataset.
        # The experimental isolation applies specifically to the LLM SubAgent.
        dataset_metadata = get_dataset_store(data_path).metadata()
        recorder.record("dataset_loaded_for_deterministic_harness", dataset_metadata)
        recorder.record("subagent_knowledge_database_access", {"enabled": False})
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
            agent_role="data_subagent_no_knowledge",
            trace=reasoning_trace,
        )
        snapshot = planning_snapshot or {}
        subagent = DataSubAgent(subagent_invoker, recorder)
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
                    "answer_source": "model_prior_cache",
                    "knowledge_database_access": False,
                    "status": "ok",
                }
                recorder.record("model_answer_cache_hit", session)
                return session
            routed_question = (
                f"Query type: {decision.get('query_type') or 'general_static_fact'}\n"
                f"Targets: {list(decision.get('targets') or [])}\n"
                f"Requested fields: {list(decision.get('requested_fields') or [])}\n"
                f"Focused question: {question}"
            )
            portable_request = dict(decision)
            portable_request["sub_question"] = routed_question
            portable_request["race"] = snapshot.get("race")
            session = subagent.run(portable_request, main_round)
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

        preflight_sessions: list[dict[str, Any]] = []
        layer_profile = snapshot.get("attack_layer_profile") or {}
        enemy_layers = layer_profile.get("enemy") or {}
        observed_combat_targets = list(dict.fromkeys(
            str(item)
            for item in (
                list(enemy_layers.get("air_combat_units") or [])
                + list(enemy_layers.get("ground_combat_units") or [])
            )
            if str(item)
        ))
        preflight_targets: list[str] = []
        if layer_profile.get("air_attack_gap"):
            preflight_targets.extend(enemy_layers.get("air_combat_units") or [])
        if layer_profile.get("ground_attack_gap"):
            preflight_targets.extend(enemy_layers.get("ground_combat_units") or [])
        preflight_targets = list(dict.fromkeys(str(item) for item in preflight_targets))
        combat_state = snapshot.get("combat_state") or {}
        enemy_power = float(combat_state.get("enemy_army_power") or 0.0)
        own_power = float(combat_state.get("our_army_power") or 0.0)
        counter_pressure = bool(
            observed_combat_targets
            and enemy_power >= 8.0
            and own_power <= max(8.0, enemy_power * 1.25)
        )
        if counter_pressure and not preflight_targets:
            preflight_targets = observed_combat_targets
        if preflight_targets or counter_pressure:
            preflight_query_type = (
                "combat_capability"
                if layer_profile.get("air_attack_gap") or layer_profile.get("ground_attack_gap")
                else "enemy_counter"
            )
            preflight_decision = {
                "query_type": preflight_query_type,
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
            recorder.record("harness_preflight_model_answer", {
                "task": "unverified_attack_layer_response",
                "targets": preflight_targets,
                "cache_hit": bool(preflight.get("cache_hit")),
                "knowledge_database_access": False,
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
            layer_profile_now = snapshot.get("attack_layer_profile") or {}
            enemy_layers_now = layer_profile_now.get("enemy") or {}
            capability_targets = []
            if layer_profile_now.get("air_attack_gap"):
                capability_targets.extend(enemy_layers_now.get("air_combat_units") or [])
            if layer_profile_now.get("ground_attack_gap"):
                capability_targets.extend(enemy_layers_now.get("ground_combat_units") or [])
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
            budget_overrun = audit.get("budget_overrun") or {}
            conversion = (
                (audit.get("resource_and_strength_conversion") or {}).get("validation") or {}
            )
            recovery_mode = bool(
                (snapshot.get("task_decomposition") or {}).get("recovery_mode")
            )
            recovery_best_effort_keys = {
                "anti_air_response_shortfall",
                "anti_ground_response_shortfall",
                "mobile_anti_air_response_shortfall",
                "mobile_anti_ground_response_shortfall",
            } if recovery_mode else set()
            conversion_violations = {
                key: value
                for key, value in conversion.items()
                if key not in {
                    "recommended_gas_structure",
                    "mineral_commitment_shortfall",
                    "strength_investment_shortfall",
                    "mobile_strength_investment_shortfall",
                } | recovery_best_effort_keys and (
                    (isinstance(value, bool) and value)
                    or (isinstance(value, (int, float)) and value > 0)
                )
            }
            if conversion_violations and conversion.get("recommended_gas_structure"):
                conversion_violations["recommended_gas_structure"] = conversion[
                    "recommended_gas_structure"
                ]
            if recovery_mode and any(
                conversion.get(key) for key in recovery_best_effort_keys
            ):
                recorder.record("recovery_response_best_effort", {
                    "unmet_response_targets": {
                        key: conversion.get(key)
                        for key in recovery_best_effort_keys
                        if conversion.get(key)
                    },
                    "ordered_names": list(decision.get("ordered_names") or []),
                    "reason": (
                        "A destroyed economy/tech state may make the scalar response target "
                        "impossible this horizon; keep the deterministically executable recovery queue."
                    ),
                })
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
        queue_audit = build_queue_audit(
            list(decision.get("ordered_names") or []),
            snapshot,
            data_path=data_path,
        )
        pre_query_queue: list[str] = []
        saw_query = False
        for item in decisions:
            if item.get("action") == "ask_subagent":
                saw_query = True
            elif item.get("action") == "final_decision" and not saw_query:
                pre_query_queue = list(item.get("ordered_names") or [])
        post_query_queue = list(decision.get("ordered_names") or [])
        pre_counts = Counter(pre_query_queue)
        post_counts = Counter(post_query_queue)
        added = list((post_counts - pre_counts).elements())
        removed = list((pre_counts - post_counts).elements())
        knowledge_effect = {
            "pre_query_queue": pre_query_queue,
            "post_query_queue": post_query_queue,
            "added_after_knowledge": added,
            "removed_after_knowledge": removed,
            "queue_changed": bool(added or removed),
            "sessions": [
                {
                    "query_type": session.get("query_type"),
                    "targets": session.get("targets") or [],
                    "status": session.get("status"),
                    "answer_source": session.get("answer_source"),
                    "recommended_shortlist": [],
                }
                for session in sessions
            ],
        }
        if isinstance(planner_state, dict):
            planner_state["previous_snapshot"] = planning_state_update(
                snapshot,
                float((decision_metadata or {}).get("game_time_seconds") or 0.0),
            )
        actual_sessions = [session for session in sessions if not session.get("cache_hit")]
        result = {
            "agent_version": "decision-data-v2.3-no-knowledge",
            "run_id": recorder.run_id,
            "log_path": str(recorder.trace_path),
            "provider": provider,
            "mainagent_provider": provider,
            "data_subagent_provider": resolved_subagent_provider,
            "reasoning_enabled": main_invoker.reasoning_mode is True,
            "reasoning_policy": "main_profile_subagent_forced_non_reasoning",
            "mainagent_reasoning_enabled": main_invoker.reasoning_mode,
            "data_subagent_configured_reasoning_mode": subagent_invoker.reasoning_mode,
            "data_subagent_reasoning_enabled": False,
            "dataset": dataset_metadata,
            "routing": {
                "strategy": "v2_3_planning_main_triggered_tool_free_subagent_with_match_cache",
                "tool_protocol": "none",
                "subagent_used": bool(actual_sessions),
                "knowledge_query_used": False,
                "knowledge_database_access": False,
                "knowledge_cache_hit": any(session.get("cache_hit") for session in sessions),
                "model_answer_cache_hit": any(session.get("cache_hit") for session in sessions),
            },
            "decision_metadata": dict(decision_metadata or {}),
            "main_decisions": decisions,
            "subagent_sessions": sessions,
            "tool_results": [],
            "reasoning_trace": reasoning_trace,
            "planning_snapshot": snapshot,
            "queue_audit": queue_audit,
            "model_answer_ledger_size": len((ledger.get("facts") or {})),
            "knowledge_ledger_size": len((ledger.get("facts") or {})),
            "knowledge_application": decision.get("knowledge_application") or [],
            "knowledge_effect": knowledge_effect,
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
