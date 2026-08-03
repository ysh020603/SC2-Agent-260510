#!/usr/bin/env python3
"""Reusable search/filter tools for the versioned SC2 dataset.

The functions in this module are intentionally plain Python so they can be
wrapped as Agent tools later. Each search function can run independently, and
`combined_search` composes them in one pass.
"""

from __future__ import annotations

import argparse
import difflib
import inspect
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .data_store import ALL_SECTIONS, DEFAULT_DATABASE_PATH, ENTITY_SECTIONS, get_dataset_store


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = DEFAULT_DATABASE_PATH
DEFAULT_SECTIONS = ENTITY_SECTIONS


def normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def load_data(data_path: str | Path = DEFAULT_DATA_PATH) -> dict[str, list[dict[str, Any]]]:
    return get_dataset_store(data_path).data


def flatten_items(
    data: dict[str, list[dict[str, Any]]] | None = None,
    sections: Iterable[str] | None = None,
    data_path: str | Path = DEFAULT_DATA_PATH,
) -> list[dict[str, Any]]:
    data = data or load_data(data_path)
    wanted = set(sections or DEFAULT_SECTIONS)
    flattened: list[dict[str, Any]] = []
    for section in ALL_SECTIONS:
        if section not in wanted:
            continue
        for item in data.get(section, []):
            row = dict(item)
            row["_section"] = section
            flattened.append(row)
    return flattened


def get_value(item: dict[str, Any], key_path: str, default: Any = None) -> Any:
    value: Any = item
    for part in key_path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default
    return value


def numeric_values(item: dict[str, Any], key_path: str) -> list[float]:
    """Return numeric values for a key path.

    Supports direct scalar paths like `max_health`, nested paths like
    `cost.minerals`, and common combat aggregate paths:
    `weapons.range`, `weapons.damage_per_hit`, `weapons.cooldown`,
    `weapons.attacks`, `weapons.dps`, `weapons.bonuses.damage`.
    """
    if key_path.startswith("weapons."):
        suffix = key_path.split(".", 1)[1]
        values: list[float] = []
        for weapon in item.get("weapons") or []:
            if suffix == "dps":
                damage = weapon.get("damage_per_hit")
                attacks = weapon.get("attacks", 1)
                cooldown = weapon.get("cooldown")
                if is_number(damage) and is_number(attacks) and is_number(cooldown) and float(cooldown) > 0:
                    values.append(float(damage) * float(attacks) / float(cooldown))
            elif suffix.startswith("bonuses."):
                bonus_key = suffix.split(".", 1)[1]
                for bonus in weapon.get("bonuses") or []:
                    value = bonus.get(bonus_key)
                    if is_number(value):
                        values.append(float(value))
            else:
                value = weapon.get(suffix)
                if is_number(value):
                    values.append(float(value))
        return values

    value = get_value(item, key_path)
    if is_number(value):
        return [float(value)]
    return []


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def matches_range(value: float, min_value: float | None = None, max_value: float | None = None) -> bool:
    if min_value is not None and value < min_value:
        return False
    if max_value is not None and value > max_value:
        return False
    return True


def project_item(item: dict[str, Any], keys: list[str] | None = None) -> dict[str, Any]:
    if not keys:
        return item
    projected: dict[str, Any] = {}
    for key in keys:
        if key == "_section":
            projected[key] = item.get("_section")
            continue
        value = get_value(item, key, default=None)
        if value is not None:
            projected[key] = value
    return projected


def apply_projection(items: list[dict[str, Any]], keys: list[str] | None = None) -> list[dict[str, Any]]:
    return [project_item(item, keys) for item in items]


def search_by_name(
    query: str,
    items: list[dict[str, Any]] | None = None,
    sections: Iterable[str] | None = None,
    mode: str = "contains",
    limit: int | None = None,
    keys: list[str] | None = None,
    data_path: str | Path = DEFAULT_DATA_PATH,
) -> list[dict[str, Any]]:
    """Search by `name`.

    mode:
    - `exact`: normalized exact match
    - `contains`: normalized substring match
    - `fuzzy`: difflib similarity match
    """
    source = items if items is not None else flatten_items(sections=sections, data_path=data_path)
    q = normalize_text(query)
    if not q:
        result = list(source)
    elif mode == "exact":
        result = [item for item in source if normalize_text(item.get("name", "")) == q]
    elif mode == "fuzzy":
        scored = []
        for item in source:
            name = normalize_text(item.get("name", ""))
            score = difflib.SequenceMatcher(None, q, name).ratio()
            if q in name:
                score += 0.25
            if score >= 0.45:
                scored.append((score, item))
        result = [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)]
    else:
        result = [item for item in source if q in normalize_text(item.get("name", ""))]
    if limit is not None:
        result = result[:limit]
    return apply_projection(result, keys)


def filter_by_numeric_ranges(
    ranges: dict[str, dict[str, float | int | None]],
    items: list[dict[str, Any]] | None = None,
    sections: Iterable[str] | None = None,
    keys: list[str] | None = None,
    data_path: str | Path = DEFAULT_DATA_PATH,
) -> list[dict[str, Any]]:
    """Filter items by numeric field ranges.

    Example:
    `{"max_health": {"min": 100}, "weapons.range": {"min": 6}}`
    """
    source = items if items is not None else flatten_items(sections=sections, data_path=data_path)
    result = []
    for item in source:
        keep = True
        for field, bounds in ranges.items():
            values = numeric_values(item, field)
            if not values:
                keep = False
                break
            min_value = bounds.get("min")
            max_value = bounds.get("max")
            if not any(matches_range(value, min_value, max_value) for value in values):
                keep = False
                break
        if keep:
            result.append(item)
    return apply_projection(result, keys)


def filter_by_tags(
    race: str | None = None,
    attributes_any: list[str] | None = None,
    attributes_all: list[str] | None = None,
    booleans: dict[str, bool] | None = None,
    items: list[dict[str, Any]] | None = None,
    sections: Iterable[str] | None = None,
    keys: list[str] | None = None,
    data_path: str | Path = DEFAULT_DATA_PATH,
) -> list[dict[str, Any]]:
    """Filter by race, attributes and boolean flags."""
    source = items if items is not None else flatten_items(sections=sections, data_path=data_path)
    any_set = {normalize_text(value) for value in (attributes_any or []) if value}
    all_set = {normalize_text(value) for value in (attributes_all or []) if value}
    result = []
    for item in source:
        if race and normalize_text(item.get("race", "")) != normalize_text(race):
            continue
        item_attrs = {normalize_text(value) for value in item.get("attributes") or []}
        if any_set and not (item_attrs & any_set):
            continue
        if all_set and not all_set.issubset(item_attrs):
            continue
        if booleans:
            if any(item.get(flag) is not expected for flag, expected in booleans.items()):
                continue
        result.append(item)
    return apply_projection(result, keys)


def filter_combat_profile(
    can_attack_air: bool | None = None,
    can_attack_ground: bool | None = None,
    target_type: str | None = None,
    min_range: float | None = None,
    max_range: float | None = None,
    min_damage_per_hit: float | None = None,
    min_dps: float | None = None,
    bonus_against: str | None = None,
    has_weapons: bool | None = None,
    items: list[dict[str, Any]] | None = None,
    keys: list[str] | None = None,
    data_path: str | Path = DEFAULT_DATA_PATH,
) -> list[dict[str, Any]]:
    """Filter Unit items by combat/weapon profile."""
    source = items if items is not None else flatten_items(sections=["Unit"], data_path=data_path)
    result = []
    for item in source:
        if item.get("_section") != "Unit":
            continue
        weapons = item.get("weapons") or []
        if has_weapons is not None and bool(weapons) != has_weapons:
            continue
        if not weapons and any(v is not None for v in [can_attack_air, can_attack_ground, target_type, min_range, max_range, min_damage_per_hit, min_dps, bonus_against]):
            continue
        if weapon_matches(
            weapons,
            can_attack_air=can_attack_air,
            can_attack_ground=can_attack_ground,
            target_type=target_type,
            min_range=min_range,
            max_range=max_range,
            min_damage_per_hit=min_damage_per_hit,
            min_dps=min_dps,
            bonus_against=bonus_against,
        ):
            result.append(item)
    return apply_projection(result, keys)


def weapon_matches(
    weapons: list[dict[str, Any]],
    can_attack_air: bool | None,
    can_attack_ground: bool | None,
    target_type: str | None,
    min_range: float | None,
    max_range: float | None,
    min_damage_per_hit: float | None,
    min_dps: float | None,
    bonus_against: str | None,
) -> bool:
    if not weapons:
        return not any(
            value is not None
            for value in [can_attack_air, can_attack_ground, target_type, min_range, max_range, min_damage_per_hit, min_dps, bonus_against]
        )

    for weapon in weapons:
        weapon_target = normalize_text(weapon.get("target_type", ""))
        if target_type and normalize_text(target_type) != weapon_target:
            continue
        if can_attack_air is True and weapon_target not in {"air", "any"}:
            continue
        if can_attack_air is False and weapon_target in {"air", "any"}:
            continue
        if can_attack_ground is True and weapon_target not in {"ground", "any"}:
            continue
        if can_attack_ground is False and weapon_target in {"ground", "any"}:
            continue
        if min_range is not None and float(weapon.get("range", -1)) < min_range:
            continue
        if max_range is not None and float(weapon.get("range", 10**9)) > max_range:
            continue
        if min_damage_per_hit is not None and float(weapon.get("damage_per_hit", -1)) < min_damage_per_hit:
            continue
        if min_dps is not None:
            damage = weapon.get("damage_per_hit")
            attacks = weapon.get("attacks", 1)
            cooldown = weapon.get("cooldown")
            if not (is_number(damage) and is_number(attacks) and is_number(cooldown) and float(cooldown) > 0):
                continue
            if float(damage) * float(attacks) / float(cooldown) < min_dps:
                continue
        if bonus_against:
            wanted = normalize_text(bonus_against)
            bonuses = weapon.get("bonuses") or []
            if not any(normalize_text(bonus.get("against", "")) == wanted for bonus in bonuses):
                continue
        return True
    return False


def combined_search(
    name_query: str | None = None,
    name_mode: str = "contains",
    numeric_ranges: dict[str, dict[str, float | int | None]] | None = None,
    tag_filters: dict[str, Any] | None = None,
    combat_filters: dict[str, Any] | None = None,
    sections: Iterable[str] | None = None,
    keys: list[str] | None = None,
    limit: int | None = None,
    data_path: str | Path = DEFAULT_DATA_PATH,
) -> list[dict[str, Any]]:
    """Compose name, numeric, tag/boolean and combat filters."""
    items = flatten_items(sections=sections, data_path=data_path)
    if name_query:
        items = search_by_name(name_query, items=items, mode=name_mode)
    if numeric_ranges:
        items = filter_by_numeric_ranges(numeric_ranges, items=items)
    if tag_filters:
        items = filter_by_tags(items=items, **tag_filters)
    if combat_filters:
        allowed = {
            name
            for name, param in inspect.signature(filter_combat_profile).parameters.items()
            if param.kind in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
        }
        items = filter_combat_profile(items=items, **{key: value for key, value in combat_filters.items() if key in allowed})
    if limit is not None:
        items = items[:limit]
    return apply_projection(items, keys)


def parse_key_list(text: str | None) -> list[str] | None:
    if not text:
        return None
    values = [part.strip() for part in text.split(",") if part.strip()]
    return values or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the configured SC2 dataset release.")
    parser.add_argument("--name", default=None)
    parser.add_argument("--name-mode", default="contains", choices=["exact", "contains", "fuzzy"])
    parser.add_argument("--sections", default=None, help="Comma separated: Ability,Unit,Upgrade,SubOntology")
    parser.add_argument("--ranges-json", default=None, help='Example: {"max_health":{"min":100}}')
    parser.add_argument("--race", default=None)
    parser.add_argument("--attributes-any", default=None)
    parser.add_argument("--attributes-all", default=None)
    parser.add_argument("--booleans-json", default=None, help='Example: {"is_flying":true}')
    parser.add_argument("--combat-json", default=None, help='Example: {"can_attack_air":true,"min_range":6}')
    parser.add_argument("--keys", default=None, help="Comma separated output key paths. Default: full item.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH))
    args = parser.parse_args()

    sections = parse_key_list(args.sections)
    numeric_ranges = json.loads(args.ranges_json) if args.ranges_json else None
    tag_filters: dict[str, Any] = {}
    if args.race:
        tag_filters["race"] = args.race
    if args.attributes_any:
        tag_filters["attributes_any"] = parse_key_list(args.attributes_any)
    if args.attributes_all:
        tag_filters["attributes_all"] = parse_key_list(args.attributes_all)
    if args.booleans_json:
        tag_filters["booleans"] = json.loads(args.booleans_json)
    combat_filters = json.loads(args.combat_json) if args.combat_json else None
    keys = parse_key_list(args.keys)

    result = combined_search(
        name_query=args.name,
        name_mode=args.name_mode,
        numeric_ranges=numeric_ranges,
        tag_filters=tag_filters or None,
        combat_filters=combat_filters,
        sections=sections,
        keys=keys,
        limit=args.limit,
        data_path=args.data,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
