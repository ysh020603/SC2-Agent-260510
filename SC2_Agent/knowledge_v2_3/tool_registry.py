"""Catalog, validation, and local dispatch for V2.3 repository tools."""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

from .query import query_engine
from .query.query_engine import execute_tool
from .query.search_tools import DEFAULT_DATA_PATH


CATALOG: dict[str, str] = {
    "resolve_entity_key": "Resolve a user-facing name or alias to a canonical Unit, Ability, Upgrade, or SubOntology key.",
    "get_entity": "Fetch selected fields or the complete record for one canonical entity.",
    "filter_attributes_and_resources": "Filter entities by names, numeric ranges, race, tags, booleans, combat fields, and sorting.",
    "query_production_outputs": "Follow a producer to Units or Upgrades it trains, builds, morphs, or researches.",
    "query_reverse_production_sources": "Find the structures or units that produce a specified Unit or Upgrade.",
    "query_addon_branches": "Inspect TechLab, Reactor, and no-add-on production branches for one Terran producer.",
    "query_addon_producers": "List add-on-capable Terran structures and their production branches.",
    "query_research_outputs": "Find upgrades researched by a structure or filtered by race and add-on requirement.",
    "query_unit_abilities": "Join Units to Ability records, including energy, range, cooldown, targets, and requirements.",
    "query_dependency_impact": "Find entities affected by a missing prerequisite or technology node.",
    "query_upgrade_effects": "Find units affected by an upgrade, optionally scoped by research structure.",
    "query_gas_units_with_sources": "Find gas-costing units with production sources and technology evidence.",
    "query_combat_production_options": "Combine production constraints with combat properties such as anti-air or speed.",
    "query_candidate_plan_facts": "Return cost, supply, raw and converted time, producer, and requirements for a bounded list of macro candidates.",
    "query_enemy_response_candidates": "Return producible own-race counters gated by whether their weapons can directly attack the enemy unit's air or ground layer.",
    "query_composition_response_matrix": "Aggregate direct-fire own-race counter candidates across several observed enemy unit types and report composition coverage.",
    "query_combat_capabilities": "Return authoritative Unit.weapons target layers (air/ground) and an engagement matrix for named units.",
    "query_upgrade_candidates": "Return upgrades with explicit stat-bonus relations to named current army units, including cost, timing, and research sources.",
    "query_tech_tree": "Query prerequisite paths, missing-node impact, add-on requirements, and multiple paths.",
    "query_tactical_profile": "Query spell, transformation, movement, range, cooldown, and target properties.",
    "search_descriptions": "Search semantic descriptions using tactical keywords.",
    "strategic_join_analysis": "Run supported derived analyses for cost, add-on dependency, or spell targets.",
    "query_counter_relations": "Traverse the unified counters relation for a canonical unit.",
    "query_combat_synergy": "Traverse synergizes_with relations for a canonical unit.",
    "query_garrison_relations": "Traverse transport and garrison compatibility relations.",
    "query_stat_bonuses": "Traverse upgrade-to-unit stat bonus relations.",
    "query_ability_unlocks": "Traverse upgrade-to-unit ability unlock relations.",
    "query_morph_enablers": "Find an Upgrade or structure that enables a morph; do not use it to find the source Unit that morphs into another Unit.",
    "query_relations": "Traverse typed graph relations with configurable direction and endpoint type; use reverse morphs_into traversal to find which Unit morphs into a result Unit.",
    "get_subontology": "Fetch one canonical SubOntology class definition and members.",
    "list_subontology_members": "List concrete Units in a SubOntology class.",
    "query_unit_classes": "Find SubOntology classes that contain a Unit.",
    "filter_units_by_subontology": "Filter concrete Units by a canonical class and optional race.",
    "query_relation_evidence": "Expand a short session-local evidence_ref only when required provenance is absent from the current result.",
    "resolve_markdown_documents": "Map an entity to release-relative Markdown documents.",
    "read_markdown_evidence": "Read an allowed line range from a release Markdown document.",
    "search_markdown": "Search release Markdown for semantic evidence not represented by structured fields.",
}

FUNCTION_ALIASES = {"filter_attributes_and_resources": "run_query_ir"}
REQUIRED_OVERRIDES = {
    "query_counter_relations": ["entity_name"],
    "query_combat_synergy": ["entity_name"],
    "query_garrison_relations": ["entity_name"],
    "query_stat_bonuses": ["entity_name"],
    "query_ability_unlocks": ["entity_name"],
    "query_morph_enablers": ["entity_name"],
}
SPECIAL_SCHEMAS: dict[str, dict[str, Any]] = {
    "filter_attributes_and_resources": {
        "type": "object",
        "properties": {
            "sections": {"type": "array", "items": {"type": "string"}},
            "name_query": {"type": "string"},
            "name_mode": {"type": "string", "enum": ["contains", "exact", "fuzzy"]},
            "numeric_ranges": {"type": "object"},
            "tag_filters": {"type": "object"},
            "combat_filters": {"type": "object"},
            "sort": {"type": "array", "items": {"type": "object"}},
            "return_keys": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
        },
        "required": ["sections"],
        "additionalProperties": False,
    },
    "query_relation_evidence": {
        "type": "object",
        "properties": {
            "evidence_ref": {
                "type": "string",
                "description": "A short Rn or Fn reference returned earlier in this DataSubAgent session.",
            },
        },
        "required": ["evidence_ref"],
        "additionalProperties": False,
    },
}


def _schema_for_annotation(annotation: Any) -> dict[str, Any]:
    text = str(annotation).lower()
    if "list" in text:
        return {"type": "array", "items": {"type": "string"}}
    if "dict" in text:
        return {"type": "object"}
    if "bool" in text:
        return {"type": "boolean"}
    if "int" in text:
        return {"type": "integer"}
    if "float" in text:
        return {"type": "number"}
    return {"type": "string"}


def _function_schema(tool_name: str) -> dict[str, Any]:
    if tool_name in SPECIAL_SCHEMAS:
        return SPECIAL_SCHEMAS[tool_name]
    function_name = FUNCTION_ALIASES.get(tool_name, tool_name)
    function = getattr(query_engine, function_name)
    signature = inspect.signature(function)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, parameter in signature.parameters.items():
        if name in {"data_path", "query_ir"}:
            continue
        schema = _schema_for_annotation(parameter.annotation)
        if name == "limit":
            schema.update({"minimum": 1, "maximum": 500})
        properties[name] = schema
        if parameter.default is inspect.Parameter.empty:
            required.append(name)
    required = REQUIRED_OVERRIDES.get(tool_name, required)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


class ToolRegistry:
    def names(self) -> list[str]:
        return list(CATALOG)

    def catalog_text(self) -> str:
        return "\n".join(f"- {name}: {summary}" for name, summary in CATALOG.items())

    def validate_selection(self, names: list[str], maximum: int = 4) -> list[str]:
        selected: list[str] = []
        for name in names:
            if name in CATALOG and name not in selected:
                selected.append(name)
        if not selected:
            raise ValueError("No valid tools were selected.")
        return selected[:maximum]

    def openai_tools(self, names: list[str], maximum: int = 4) -> list[dict[str, Any]]:
        selected = self.validate_selection(names, maximum=maximum)
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": CATALOG[name],
                    "parameters": _function_schema(name),
                },
            }
            for name in selected
        ]

    def validate_arguments(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in CATALOG:
            raise ValueError(f"Unknown V2.3 tool: {name}")
        if not isinstance(arguments, dict):
            raise TypeError("Tool arguments must be a JSON object.")
        schema = _function_schema(name)
        unknown = set(arguments) - set(schema.get("properties", {}))
        missing = set(schema.get("required", [])) - set(arguments)
        if unknown:
            raise ValueError(f"Unsupported arguments for {name}: {sorted(unknown)}")
        if missing:
            raise ValueError(f"Missing required arguments for {name}: {sorted(missing)}")
        validated = dict(arguments)
        if "limit" in validated:
            validated["limit"] = max(1, min(int(validated["limit"]), 500))
        return validated

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        data_path: str | Path = DEFAULT_DATA_PATH,
        evidence_references: Any | None = None,
    ) -> dict[str, Any]:
        validated = self.validate_arguments(name, arguments)
        dispatch_arguments = validated
        if name == "query_relation_evidence":
            if evidence_references is None:
                raise ValueError("query_relation_evidence requires the current session evidence reference map.")
            dispatch_arguments = evidence_references.resolve(validated["evidence_ref"])
        result = execute_tool(name, dispatch_arguments, data_path=data_path)
        if name == "get_entity":
            return _get_entity_with_upgrade_field_fallback(result, validated, data_path)
        if name == "query_production_outputs":
            return _compact_production_outputs(result)
        if name == "query_relations":
            return _augment_forward_morph_relations(result, validated, data_path)
        return result

    def fallback_selection(self, question: str, maximum: int = 4) -> list[str]:
        lowered = question.lower()
        scores: list[tuple[int, str]] = []
        for name, summary in CATALOG.items():
            tokens = set(re.findall(r"[a-z_]+", f"{name} {summary}".lower()))
            score = sum(1 for token in tokens if len(token) > 3 and token in lowered)
            scores.append((score, name))
        ranked = [name for score, name in sorted(scores, reverse=True) if score > 0]
        defaults = ["resolve_entity_key", "get_entity", "query_relations", "query_tech_tree"]
        return (ranked + [name for name in defaults if name not in ranked])[:maximum]


def dispatcher_tool_names() -> set[str]:
    source = inspect.getsource(query_engine.execute_tool)
    return set(re.findall(r'if tool_name == "([^"]+)"', source)) - {"run_query_ir"}


def _get_entity_with_upgrade_field_fallback(
    result: dict[str, Any],
    arguments: dict[str, Any],
    data_path: str | Path,
) -> dict[str, Any]:
    keys = arguments.get("keys")
    if not keys or not isinstance(keys, list):
        return result
    rows = result.get("results") if isinstance(result, dict) else None
    if not isinstance(rows, list) or not rows or any(row for row in rows if isinstance(row, dict)):
        return result
    full_args = dict(arguments)
    full_args.pop("keys", None)
    full_result = execute_tool("get_entity", full_args, data_path=data_path)
    full_rows = full_result.get("results") if isinstance(full_result, dict) else None
    if not isinstance(full_rows, list) or not full_rows or not isinstance(full_rows[0], dict):
        return result
    record = full_rows[0]
    cost = record.get("cost") if isinstance(record.get("cost"), dict) else {}
    extracted: dict[str, Any] = {}
    for key in keys:
        key = str(key)
        if key in record:
            extracted[key] = record[key]
        elif key in {"minerals", "mineral_cost"} and "minerals" in cost:
            extracted[key] = cost["minerals"]
        elif key in {"gas", "gas_cost"} and "gas" in cost:
            extracted[key] = cost["gas"]
        elif key in {"time", "research_time", "research_time_loops"} and "time" in cost:
            extracted[key] = cost["time"]
    if extracted:
        fallback = dict(result)
        fallback["results"] = [extracted]
        fallback["field_fallback"] = {
            "source": "complete_get_entity_record",
            "reason": "selected keys were empty; extracted direct fields and nested cost fields",
        }
        return fallback
    return result


def _compact_production_outputs(result: dict[str, Any]) -> dict[str, Any]:
    rows = result.get("results") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return result
    compact_rows: list[dict[str, Any]] = []
    changed = False
    for row in rows:
        if not isinstance(row, dict):
            compact_rows.append(row)
            continue
        produced = row.get("produced") if isinstance(row.get("produced"), dict) else {}
        producer = row.get("producer") if isinstance(row.get("producer"), dict) else {}
        ability = row.get("ability") if isinstance(row.get("ability"), dict) else {}
        compact: dict[str, Any] = {
            "producer_name": row.get("producer_name") or producer.get("name"),
            "producer_section": row.get("producer_section") or producer.get("section"),
            "target_type": row.get("target_type"),
            "produced_section": row.get("produced_section"),
            "produced": {
                "name": produced.get("name"),
                "race": produced.get("race"),
                "minerals": produced.get("minerals"),
                "gas": produced.get("gas"),
                "max_health": produced.get("max_health"),
                "armor": produced.get("armor"),
                "is_flying": produced.get("is_flying"),
                "is_structure": produced.get("is_structure"),
                "normal_mode_name": produced.get("normal_mode_name"),
                "unit_alias_name": produced.get("unit_alias_name"),
                "tech_alias_names": produced.get("tech_alias_names"),
            },
            "ability": {
                "name": ability.get("name") or row.get("ability_name"),
                "target": ability.get("target"),
            },
            "requirements": row.get("requirements") or [],
            "required_addon": row.get("required_addon"),
        }
        if row.get("tech_chain"):
            compact["tech_chain"] = row.get("tech_chain")
        compact_rows.append(compact)
        changed = True
    if not changed:
        return result
    compact_result = dict(result)
    compact_result["results"] = compact_rows
    compact_result["compacted"] = {
        "reason": "V2.2 keeps production candidate coverage compact to avoid hiding later candidates in very large entity records.",
        "original_result_count": len(rows),
    }
    return compact_result


def _augment_forward_morph_relations(
    result: dict[str, Any],
    arguments: dict[str, Any],
    data_path: str | Path,
) -> dict[str, Any]:
    relation = arguments.get("relation")
    relations = relation if isinstance(relation, list) else [relation]
    if "morphs_into" not in relations or arguments.get("direction") not in {None, "forward"}:
        return result
    entity_name = arguments.get("entity_name")
    if not entity_name:
        return result
    rows = result.get("results") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return result
    existing = {row.get("object_name") for row in rows if isinstance(row, dict)}
    try:
        production = _compact_production_outputs(
            execute_tool("query_production_outputs", {"producer_name": entity_name, "limit": 500}, data_path=data_path)
        )
    except Exception:
        return result
    supplemental: list[dict[str, Any]] = []
    for row in production.get("results", []):
        if not isinstance(row, dict):
            continue
        target_type = str(row.get("target_type") or "")
        if target_type.lower() not in {"morph", "train"}:
            continue
        produced = row.get("produced") if isinstance(row.get("produced"), dict) else {}
        produced_name = produced.get("name")
        if not produced_name or produced_name in existing:
            continue
        supplemental.append({
            "relation_id": "",
            "subject_name": entity_name,
            "subject_type": row.get("producer_section") or "Unit",
            "relation": "morphs_into" if target_type.lower() == "morph" else "production_output",
            "object_name": produced_name,
            "object_type": row.get("produced_section") or "Unit",
            "description": [
                f"{entity_name} has a {target_type} production output that produces {produced_name}."
            ],
            "source": [{
                "kind": "v2_2_tool_supplement",
                "rule": "production_output_candidate",
                "ability": row.get("ability"),
            }],
            "fact": [],
            "matched_direction": "forward",
            "candidate_fields": produced,
            "requirements": row.get("requirements") or [],
        })
        existing.add(produced_name)
    if not supplemental:
        return result
    augmented = dict(result)
    augmented["results"] = rows + supplemental
    augmented["count"] = len(augmented["results"])
    augmented["supplemented"] = {
        "reason": "V2.2 added production-output candidates visible in production outputs but absent from direct relation results.",
        "added_count": len(supplemental),
    }
    return augmented


__all__ = ["CATALOG", "ToolRegistry", "dispatcher_tool_names"]
