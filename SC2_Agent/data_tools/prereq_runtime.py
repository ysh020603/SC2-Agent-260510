"""Runtime prerequisite / tech-chain reasoning for the execution scheduler.

All functions take the live bot (``ai``) and a canonical action name, translate
the bot state into DB entity names via :mod:`obs_entities`, and answer the
three questions the scheduler needs:

* ``is_available_now``   – tech prerequisites + an executor exist right now.
* ``missing_chain``      – which prerequisite entities are missing.
* ``chain_in_progress``  – are the missing prerequisites already being built /
  researched (so the dependent action should keep waiting)?
"""

from __future__ import annotations

from typing import Any

try:  # package import (normal runtime)
    from .check_action_prereqs import check_action_prerequisites, ENTITY_IMPLIES
    from .obs_entities import collect_entities
    from .sc2_data_common import expand_entity_implications
except ImportError:  # pragma: no cover
    from check_action_prereqs import check_action_prerequisites, ENTITY_IMPLIES  # type: ignore
    from obs_entities import collect_entities  # type: ignore
    from sc2_data_common import expand_entity_implications  # type: ignore


def _expand_implications(entities: set[str]) -> set[str]:
    """Add implied entities (e.g. having a Barracks if you have BarracksTechLab)."""
    return expand_entity_implications(
        set(entities),
        extra_implications=ENTITY_IMPLIES,
    )


def _report_for(ai: Any, action: str) -> dict[str, Any]:
    entities = collect_entities(ai)["completed"]
    result = check_action_prerequisites(entities, [action])
    reports = result.get("ordered_reports") or []
    return reports[0] if reports else {}


def is_available_now(ai: Any, action: str) -> bool:
    """True if tech prereqs are satisfied AND an executor is present right now."""
    report = _report_for(ai, action)
    if not report.get("known", False):
        return False
    return bool(report.get("available", False))


def missing_chain(ai: Any, action: str) -> list[str]:
    """Canonical entity names that are missing for ``action`` (tech + executor)."""
    report = _report_for(ai, action)
    missing: list[str] = []
    for item in report.get("missing_requirements", []):
        ent = item.get("entity_name")
        if ent:
            missing.append(ent)
    for item in report.get("missing_executors", []):
        for ex in item.get("accepted_executors", []):
            missing.append(ex)
    # de-dup, keep order
    seen: set[str] = set()
    ordered: list[str] = []
    for ent in missing:
        if ent not in seen:
            seen.add(ent)
            ordered.append(ent)
    return ordered


def chain_in_progress(ai: Any, action: str) -> bool:
    """True if EVERY missing prerequisite is already being built / researched.

    When this holds, the scheduler should keep the action WAITING and let it
    fire as soon as the prerequisite finishes.
    """
    missing = missing_chain(ai, action)
    if not missing:
        return False
    states = collect_entities(ai)
    coming = _expand_implications(set(states["in_progress"]) | set(states["pending"]))
    return all(ent in coming for ent in missing)
