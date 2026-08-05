"""Provider-independent, deterministic routing for V2.3 SC2 knowledge tools."""

from __future__ import annotations

from typing import Any

from .tool_registry import ToolRegistry


WORKERS = {"scv", "probe", "drone"}
MAX_CANDIDATES = 6


def _key(value: Any) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


class PortableKnowledgeRouter:
    """Execute local data tools without exposing function calling to the API."""

    def __init__(
        self,
        registry: ToolRegistry,
        recorder: Any,
        *,
        data_path: Any,
        planning_snapshot: dict[str, Any] | None = None,
    ) -> None:
        self.registry = registry
        self.recorder = recorder
        self.data_path = data_path
        self.snapshot = planning_snapshot or {}
        assets = self.snapshot.get("committed_and_available_assets") or {}
        self.completed_assets = {
            _key(name)
            for name, count in (assets.get("completed") or {}).items()
            if _number(count) > 0
        }
        self.completed_assets.update(
            _key(name) for name in self.snapshot.get("completed_upgrades") or []
        )
        self.committed_assets = {
            _key(name)
            for field in ("completed", "under_construction", "active_queues")
            for name, count in (assets.get(field) or {}).items()
            if _number(count) > 0
        }
        self.committed_assets.update(self.completed_assets)

    def _execute(
        self,
        session_id: str,
        tool: str,
        arguments: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        request = {
            "session_id": session_id,
            "protocol": "portable_local_orchestrator",
            "tool": tool,
            "arguments": arguments,
        }
        self.recorder.record("tool_request", request)
        try:
            result = self.registry.execute(tool, arguments, data_path=self.data_path)
            observation = {**request, "result": result}
        except Exception as exc:
            result = {"error": f"{type(exc).__name__}: {exc}"}
            observation = {**request, "error": result["error"]}
        self.recorder.record("tool_response", observation)
        return result, observation

    def _asset_available(self, name: str, *, completed_only: bool) -> bool:
        key = _key(name)
        assets = self.completed_assets if completed_only else self.committed_assets
        if key in assets:
            return True
        # Larva are an implicit, transient Zerg production resource and are not
        # emitted in the macro observation. A completed Hatchery-family townhall
        # proves that a Larva production route exists.
        if key == "larva":
            return bool({"hatchery", "lair", "hive"} & assets)
        return False

    def _producer_state(
        self,
        sources: list[dict[str, Any]],
    ) -> tuple[bool, bool, list[str], list[str], list[str]]:
        producers: list[str] = []
        requirements: list[str] = []
        missing_requirements: list[str] = []
        ready = False
        reachable = False
        for source in sources:
            producer = source.get("producer") if isinstance(source.get("producer"), dict) else {}
            producer_name = str(producer.get("name") or source.get("producer_name") or "")
            source_ready = bool(
                producer_name and self._asset_available(producer_name, completed_only=True)
            )
            source_reachable = bool(
                producer_name and self._asset_available(producer_name, completed_only=False)
            )
            if producer_name:
                producers.append(producer_name)
            for requirement in source.get("requirements") or []:
                if not isinstance(requirement, dict):
                    continue
                name = str(
                    requirement.get("building_name")
                    or requirement.get("addon_to_name")
                    or requirement.get("addon_name")
                    or requirement.get("upgrade_name")
                    or ""
                )
                if name:
                    requirements.append(name)
                    combined_addon = producer_name + name if producer_name else ""
                    requirement_ready = self._asset_available(name, completed_only=True) or bool(
                        combined_addon
                        and self._asset_available(combined_addon, completed_only=True)
                    )
                    requirement_reachable = self._asset_available(name, completed_only=False) or bool(
                        combined_addon
                        and self._asset_available(combined_addon, completed_only=False)
                    )
                    source_ready = source_ready and requirement_ready
                    source_reachable = source_reachable and requirement_reachable
                    if not requirement_reachable:
                        missing_requirements.append(name)
            addon = str(source.get("required_addon") or "")
            if addon:
                requirements.append(addon)
                combined_addon = producer_name + addon if producer_name else ""
                addon_ready = self._asset_available(addon, completed_only=True) or bool(
                    combined_addon and self._asset_available(combined_addon, completed_only=True)
                )
                addon_reachable = self._asset_available(addon, completed_only=False) or bool(
                    combined_addon and self._asset_available(combined_addon, completed_only=False)
                )
                source_ready = source_ready and addon_ready
                source_reachable = source_reachable and addon_reachable
                if not addon_reachable:
                    missing_requirements.append(addon)
            ready = ready or source_ready
            reachable = reachable or source_reachable
        return (
            ready,
            reachable,
            list(dict.fromkeys(producers)),
            list(dict.fromkeys(requirements)),
            list(dict.fromkeys(missing_requirements)),
        )

    def _rank_enemy_candidates(self, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        current = self.snapshot.get("current") or {}
        budget = self.snapshot.get("projected_without_new_spending") or {}
        fallback = ((self.snapshot.get("task_decomposition") or {}).get("fallback_units") or {})
        combat_emergency = bool(
            (self.snapshot.get("task_decomposition") or {}).get("combat_emergency")
        )
        strategy_names = {
            _key(name)
            for values in fallback.values()
            for name in (values if isinstance(values, list) else [])
        }
        feasible: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("candidate_name") or row.get("name") or "")
            if not name or _key(name) in WORKERS:
                excluded.append({"name": name, "reason": "worker_or_invalid_candidate"})
                continue
            sources = row.get("production_sources") or row.get("production_or_research_sources") or []
            producer_ready, producer_reachable, producers, requirements, missing_requirements = (
                self._producer_state(sources)
            )
            minerals = _number(row.get("minerals"))
            gas = _number(row.get("gas"))
            directly_attacks = bool(
                row.get("can_directly_attack_target_layer", row.get("can_directly_attack_all_covered_layers", True))
            )
            affordable = (
                minerals <= _number(budget.get("minerals", current.get("minerals")))
                and gas <= _number(budget.get("gas", current.get("gas")))
            )
            is_structure = bool(row.get("is_structure"))
            mobile_combat = not is_structure and _number(row.get("supply")) > 0
            immediately_executable = bool(directly_attacks and producer_ready and affordable)
            horizon_reachable = bool(directly_attacks and producer_reachable and affordable)
            semantic_coverage = _number(row.get("semantic_counter_coverage_ratio"))
            gas_surplus = _number(current.get("gas")) > _number(current.get("minerals")) * 0.5
            score = (
                (6 if directly_attacks else -20)
                # Full-layer generalists are useful, but should not crowd out a
                # stronger air+ground portfolio.  Layer coverage is assembled
                # explicitly below instead of being treated as a winner-takes-all
                # ranking signal.
                + (2 if row.get("covers_all_requested_targets") else 0)
                + (4 if producer_ready else 0)
                + (3 if _key(name) in strategy_names else 0)
                + (1 if affordable else -2)
                + (4 if mobile_combat else (2 if combat_emergency else -4))
                + (2 if horizon_reachable else 0)
                + 6 * semantic_coverage
                + (2 if gas_surplus and gas > 0 else 0)
                + (1 if _number(row.get("time_seconds")) <= _number(self.snapshot.get("horizon_seconds")) else 0)
                + 4 * _number(row.get("coverage_ratio"))
            )
            candidate = {
                "name": name,
                "enemy_name": row.get("enemy_name"),
                "covered_enemy_names": row.get("covered_enemy_names") or ([row.get("enemy_name")] if row.get("enemy_name") else []),
                "coverage_ratio": _number(row.get("coverage_ratio")) or (1.0 if row.get("enemy_name") else 0.0),
                "covers_all_requested_targets": bool(row.get("covers_all_requested_targets")),
                "relation": row.get("relation_direction") or row.get("relation") or row.get("relations") or [],
                "target_layer": row.get("target_layer") or row.get("target_layers") or [],
                "can_directly_attack_target_layer": directly_attacks,
                "minerals": minerals,
                "gas": gas,
                "supply": _number(row.get("supply")),
                "is_structure": is_structure,
                "is_flying": bool(row.get("is_flying")),
                "weapon_target_layers": list(row.get("weapon_target_layers") or []),
                "mobile_combat": mobile_combat,
                "time_seconds": _number(row.get("time_seconds")),
                "producer_ready": producer_ready,
                "producer_reachable_in_horizon": producer_reachable,
                "producers": producers,
                "requirements": requirements,
                "missing_requirements": missing_requirements,
                "affordable_in_horizon": affordable,
                "immediately_executable": immediately_executable,
                "horizon_reachable": horizon_reachable,
                "strategy_compatible": _key(name) in strategy_names,
                "semantic_counter_coverage_ratio": semantic_coverage,
                "score": score,
                "evidence_description": row.get("evidence_description") or [],
            }
            if directly_attacks:
                feasible.append(candidate)
            else:
                excluded.append({"name": name, "reason": "cannot_directly_attack_target_layer"})
        feasible.sort(key=lambda item: (
            not bool(item.get("immediately_executable")),
            not bool(item.get("horizon_reachable")),
            not bool(item.get("mobile_combat")),
            -_number(item.get("score")),
            _number(item.get("minerals")),
            str(item.get("name")),
        ))
        return feasible[:MAX_CANDIDATES], excluded[:MAX_CANDIDATES]

    def run(self, request: dict[str, Any], session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        query_type = str(request.get("query_type") or "general_static_fact")
        targets = [str(item) for item in request.get("targets") or [] if str(item)]
        race = str(self.snapshot.get("race") or request.get("race") or "")
        combat_emergency = bool(
            (self.snapshot.get("task_decomposition") or {}).get("combat_emergency")
        )
        observations: list[dict[str, Any]] = []
        selected_tools: list[str] = []

        def call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
            selected_tools.append(tool)
            result, observation = self._execute(session_id, tool, arguments)
            observations.append(observation)
            return result

        packet: dict[str, Any] = {
            "query_type": query_type,
            "targets": targets,
            "requested_fields": list(request.get("requested_fields") or []),
            "our_race": race,
            "status": "success",
            "protocol": "portable_local_orchestrator",
            "verified_facts": [],
            "feasible_candidates": [],
            "excluded_candidates": [],
            "limitations": [],
        }

        if query_type == "enemy_counter":
            result = call("query_composition_response_matrix", {
                "enemy_names": targets,
                "own_race": race,
                "limit": 24,
            })
            rows = result.get("results") or []
            feasible, excluded = self._rank_enemy_candidates(rows)
            packet["feasible_candidates"] = feasible
            packet["excluded_candidates"] = excluded
            packet["verified_facts"] = [
                {
                    "candidate": item["name"],
                    "targets": item.get("covered_enemy_names") or [],
                    "coverage_ratio": item.get("coverage_ratio"),
                    "direct_attack": item["can_directly_attack_target_layer"],
                    "producer_ready": item["producer_ready"],
                    "mobile_combat": item["mobile_combat"],
                    "immediately_executable": item["immediately_executable"],
                    "horizon_reachable": item["horizon_reachable"],
                    "cost": {"minerals": item["minerals"], "gas": item["gas"]},
                }
                for item in feasible
            ]
        elif query_type == "combat_capability":
            tasks = self.snapshot.get("task_decomposition") or {}
            fallback = tasks.get("fallback_units") or {}
            layer = self.snapshot.get("attack_layer_profile") or {}
            candidate_names: list[str] = []
            if layer.get("air_attack_gap"):
                candidate_names.extend(fallback.get("anti_air") or [])
            if layer.get("ground_attack_gap"):
                candidate_names.extend(fallback.get("anti_ground") or [])
            own_layer = layer.get("own") or {}
            candidate_names.extend(own_layer.get("air_combat_units") or [])
            candidate_names.extend(own_layer.get("ground_combat_units") or [])

            # Counter relations remain a discovery hint only. Final capability
            # is established independently from structured weapon target types.
            semantic = call("query_composition_response_matrix", {
                "enemy_names": targets,
                "own_race": race,
                "limit": 16,
            })
            candidate_names.extend(
                str(item.get("name"))
                for item in semantic.get("results") or []
                if isinstance(item, dict) and item.get("name")
            )
            production = call("query_combat_production_options", {
                "race": race,
                "limit": 100,
            })
            candidate_names.extend(
                str(item.get("name"))
                for item in production.get("results") or []
                if isinstance(item, dict) and item.get("name")
            )
            candidate_names = list(dict.fromkeys(candidate_names))[:40]
            capabilities = call("query_combat_capabilities", {
                "names": candidate_names,
                "enemy_names": targets,
                "race": race,
                "limit": 50,
            })
            facts = call("query_candidate_plan_facts", {
                "names": candidate_names,
                "race": race,
                "limit": 50,
            })
            fact_by_name = {
                _key(item.get("name")): item
                for item in facts.get("results") or []
                if isinstance(item, dict) and item.get("name")
            }
            semantic_by_name = {
                _key(item.get("name")): _number(item.get("coverage_ratio"))
                for item in semantic.get("results") or []
                if isinstance(item, dict) and item.get("name")
            }
            rows = []
            denominator = max(1, len(targets))
            for capability in capabilities.get("results") or []:
                if not isinstance(capability, dict) or not capability.get("name"):
                    continue
                name = str(capability["name"])
                fact = fact_by_name.get(_key(name)) or {}
                covered = [
                    str(item.get("enemy_name"))
                    for item in capability.get("engagement") or []
                    if isinstance(item, dict) and item.get("can_directly_attack")
                ]
                if not covered:
                    continue
                rows.append({
                    **fact,
                    "name": name,
                    "covered_enemy_names": covered,
                    "coverage_ratio": round(len(set(covered)) / denominator, 4),
                    "covers_all_requested_targets": len(set(covered)) >= denominator,
                    "semantic_counter_coverage_ratio": semantic_by_name.get(_key(name), 0.0),
                    "target_layers": list(dict.fromkeys(
                        str(item.get("enemy_layer"))
                        for item in capability.get("engagement") or []
                        if isinstance(item, dict)
                        and item.get("can_directly_attack")
                        and item.get("enemy_layer")
                    )),
                    "can_directly_attack_all_covered_layers": True,
                    "relations": ["structured Unit.weapons target-layer verification"],
                    "evidence_description": [
                        "Candidate coverage is derived from structured weapon target types, not semantic counter text."
                    ],
                })
            feasible, excluded = self._rank_enemy_candidates(rows)
            packet["feasible_candidates"] = feasible
            packet["excluded_candidates"] = excluded
            packet["verified_facts"] = [
                {
                    "candidate": item["name"],
                    "targets": item.get("covered_enemy_names") or [],
                    "coverage_ratio": item.get("coverage_ratio"),
                    "covers_all_requested_targets": item.get("covers_all_requested_targets"),
                    "direct_attack": item["can_directly_attack_target_layer"],
                    "producer_ready": item["producer_ready"],
                    "cost": {"minerals": item["minerals"], "gas": item["gas"]},
                }
                for item in feasible
            ]
        elif query_type == "upgrade_path":
            result = call("query_upgrade_candidates", {
                "own_unit_names": targets,
                "race": race,
                "limit": 16,
            })
            rows = [row for row in result.get("results") or [] if isinstance(row, dict)]
            candidates = []
            for row in rows:
                if _key(row.get("name")) in self.committed_assets:
                    continue
                ready, reachable, producers, requirements, missing_requirements = self._producer_state(
                    row.get("research_sources") or []
                )
                minerals = _number(row.get("minerals"))
                gas = _number(row.get("gas"))
                current = self.snapshot.get("current") or {}
                budget = self.snapshot.get("projected_without_new_spending") or {}
                affordable = bool(
                    minerals <= _number(budget.get("minerals", current.get("minerals")))
                    and gas <= _number(budget.get("gas", current.get("gas")))
                )
                candidates.append({
                    "name": row.get("name"),
                    "minerals": minerals,
                    "gas": gas,
                    "time_seconds": _number(row.get("time_seconds")),
                    "affected_units": row.get("affected_named_units") or [],
                    "effects": (row.get("effects") or [])[:3],
                    "researcher_ready": ready,
                    "researcher_reachable_in_horizon": reachable,
                    "research_sources": producers,
                    "requirements": requirements,
                    "missing_requirements": missing_requirements,
                    "affordable_in_horizon": affordable,
                    "score": (
                        (4 if ready else 2 if reachable else 0)
                        + (1 if affordable else -3)
                        + min(3, len(row.get("affected_named_units") or []))
                    ),
                })
            candidates.sort(key=lambda item: (-_number(item.get("score")), _number(item.get("minerals")) + _number(item.get("gas"))))
            packet["feasible_candidates"] = candidates[:MAX_CANDIDATES]
        elif query_type == "tech_feasibility":
            for target in targets[:4]:
                result = call("query_tech_tree", {"target": target, "limit": 12})
                packet["verified_facts"].extend(result.get("results") or [])
            facts = call("query_candidate_plan_facts", {"names": targets, "race": race, "limit": 12})
            candidates = []
            for row in facts.get("results") or []:
                if not isinstance(row, dict):
                    continue
                sources = row.get("production_or_research_sources") or []
                ready, reachable, producers, requirements, missing_requirements = self._producer_state(sources)
                candidates.append({
                    **row,
                    "producer_ready": ready,
                    "producer_reachable_in_horizon": reachable,
                    "producers": producers,
                    "requirements": requirements,
                    "missing_requirements": missing_requirements,
                    "required_sequence": list(dict.fromkeys(
                        missing_requirements
                        + ([producers[0]] if producers and not ready and producers[0] not in {"Larva"} else [])
                        + ([str(row.get("name"))] if row.get("name") else [])
                    )),
                })
            packet["feasible_candidates"] = candidates
        else:
            result = call("query_candidate_plan_facts", {"names": targets, "race": race, "limit": 16})
            packet["verified_facts"] = result.get("results") or []
            packet["feasible_candidates"] = result.get("results") or []

        errors = [item.get("error") for item in observations if item.get("error")]
        if errors:
            packet["limitations"].extend(str(error) for error in errors)
            packet["status"] = "degraded" if packet["verified_facts"] or packet["feasible_candidates"] else "unavailable"
        if not packet["verified_facts"] and not packet["feasible_candidates"]:
            packet["status"] = "unavailable"
            packet["limitations"].append("No repository evidence matched the focused query.")
        feasible_candidates = [
            item for item in packet["feasible_candidates"] if isinstance(item, dict)
        ]
        packet["immediate_mobile_shortlist"] = [
            item.get("name") for item in feasible_candidates
            if item.get("mobile_combat") and item.get("immediately_executable")
        ][:3]
        packet["horizon_mobile_shortlist"] = [
            item.get("name") for item in feasible_candidates
            if item.get("mobile_combat") and item.get("horizon_reachable")
        ][:3]
        packet["static_defense_shortlist"] = [
            item.get("name") for item in feasible_candidates
            if item.get("is_structure") and item.get("immediately_executable")
        ][:3]
        packet["recommended_shortlist"] = [
            item.get("name") for item in packet["feasible_candidates"][:3] if isinstance(item, dict) and item.get("name")
        ]
        required_layers: list[str] = []
        layer_profile = self.snapshot.get("attack_layer_profile") or {}
        if layer_profile.get("air_attack_gap"):
            required_layers.append("Air")
        if layer_profile.get("ground_attack_gap"):
            required_layers.append("Ground")
        if query_type in {"enemy_counter", "combat_capability"}:
            enemy_layer_profile = layer_profile.get("enemy") or {}
            if enemy_layer_profile.get("air_combat_units") and "Air" not in required_layers:
                required_layers.append("Air")
            if enemy_layer_profile.get("ground_combat_units") and "Ground" not in required_layers:
                required_layers.append("Ground")

        preferred_by_layer: dict[str, list[str]] = {}
        for required_layer in required_layers:
            preferred_by_layer[required_layer.lower()] = [
                str(item.get("name"))
                for item in feasible_candidates
                if item.get("mobile_combat")
                and item.get("immediately_executable")
                and required_layer in (item.get("target_layer") or [])
                and item.get("name")
            ][:3]

        # Preserve a portfolio order: the best verified specialist for each
        # threatened layer comes before additional all-purpose candidates.
        portfolio_now: list[str] = []
        for required_layer in required_layers:
            for name in preferred_by_layer.get(required_layer.lower(), []):
                if name not in portfolio_now:
                    portfolio_now.append(name)
                    break
        for name in packet["immediate_mobile_shortlist"]:
            if name not in portfolio_now:
                portfolio_now.append(name)
        portfolio_now = portfolio_now[:4]
        packet["decision_guidance"] = {
            "actionable": bool(
                packet["immediate_mobile_shortlist"]
                or packet["horizon_mobile_shortlist"]
                or (combat_emergency and packet["static_defense_shortlist"])
                or (query_type == "tech_feasibility" and feasible_candidates)
                or (
                    query_type == "upgrade_path"
                    and any(
                        item.get("affordable_in_horizon")
                        and (
                            item.get("researcher_ready")
                            or item.get("researcher_reachable_in_horizon")
                        )
                        for item in feasible_candidates
                    )
                )
            ),
            "preferred_mobile_now": portfolio_now,
            "preferred_mobile_this_horizon": packet["horizon_mobile_shortlist"],
            "preferred_mobile_by_layer": preferred_by_layer,
            "portfolio_rule": (
                "Cover each observed attack layer with the best verified immediately executable "
                "candidate; do not require one unit type to solve the whole composition."
            ),
            "emergency_static_only": packet["static_defense_shortlist"] if combat_emergency else [],
            "rule": (
                "Use verified mobile candidates before static defense in normal play; "
                "do not replace an executable strategy unit unless coverage or feasibility improves."
            ),
        }
        return packet, observations, list(dict.fromkeys(selected_tools))


__all__ = ["PortableKnowledgeRouter"]
