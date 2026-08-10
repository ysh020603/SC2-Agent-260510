"""Deterministic SC2 producer discovery and selection."""

from __future__ import annotations

from typing import Any, List, Tuple

from sc2.ids.ability_id import AbilityId


async def candidate_producers(ai: Any, ability: AbilityId) -> List[Tuple[Any, str]]:
    candidates: List[Any] = []
    for unit in list(ai.units) + list(ai.structures):
        if getattr(unit, "build_progress", 1.0) < 1.0:
            continue
        if getattr(unit, "is_constructing_scv", False):
            continue
        if getattr(unit, "tag", None) in getattr(ai, "unit_tags_received_action", set()):
            continue
        candidates.append(unit)
    if not candidates:
        return []
    try:
        abilities = await ai.get_available_abilities(
            candidates,
            ignore_resource_requirements=True,
        )
    except Exception:
        return []
    return [
        (unit, _status_text(unit))
        for unit, available in zip(candidates, abilities)
        if ability in available
    ]


def choose_producer(candidates: List[Tuple[Any, str]]) -> Any:
    """Prefer idle and short-queued producers, with tag as a stable tie-break."""
    if not candidates:
        return None

    def score(row: Tuple[Any, str]):
        unit = row[0]
        return (
            0 if getattr(unit, "is_idle", False) else 1,
            len(getattr(unit, "orders", None) or []),
            int(getattr(unit, "tag", 0)),
        )

    return min(candidates, key=score)[0]


def _status_text(unit: Any) -> str:
    if getattr(unit, "is_idle", False):
        return "idle"
    orders = getattr(unit, "orders", None) or []
    return f"busy ({len(orders)} order(s))"


__all__ = ["candidate_producers", "choose_producer"]
