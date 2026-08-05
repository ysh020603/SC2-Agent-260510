"""Compact, session-local tool-result views retained for V2.3 compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


OPAQUE_ID_KEYS = frozenset({
    "relation_id",
    "source_id",
    "origin_relation_id",
    "fact_id",
    "fact_ids",
    "split_group_id",
    "expansion_group_id",
})


@dataclass
class EvidenceReferenceMap:
    """Replace long evidence hashes with short references visible only in one session."""

    _targets_by_ref: dict[str, dict[str, str]] = field(default_factory=dict)
    _refs_by_target: dict[tuple[str, str], str] = field(default_factory=dict)
    _relation_count: int = 0
    _fact_count: int = 0

    @property
    def has_references(self) -> bool:
        return bool(self._targets_by_ref)

    def _register(self, kind: str, value: Any) -> str | None:
        identifier = str(value or "").strip()
        if not identifier:
            return None
        key = (kind, identifier)
        existing = self._refs_by_target.get(key)
        if existing:
            return existing
        if kind == "relation_id":
            self._relation_count += 1
            reference = f"R{self._relation_count}"
        else:
            self._fact_count += 1
            reference = f"F{self._fact_count}"
        self._refs_by_target[key] = reference
        self._targets_by_ref[reference] = {kind: identifier}
        return reference

    def resolve(self, evidence_ref: str) -> dict[str, str]:
        reference = str(evidence_ref or "").strip().upper()
        target = self._targets_by_ref.get(reference)
        if not target:
            raise ValueError(
                f"Unknown evidence_ref {evidence_ref!r}. Use a short reference returned in the current tool session."
            )
        return dict(target)

    def compact(self, value: Any) -> tuple[Any, dict[str, Any]]:
        removed_counts: dict[str, int] = {}
        references_added = 0

        def visit(item: Any) -> Any:
            nonlocal references_added
            if isinstance(item, list):
                return [visit(entry) for entry in item]
            if not isinstance(item, dict):
                return item

            reference = None
            if item.get("relation_id"):
                reference = self._register("relation_id", item.get("relation_id"))
            elif item.get("fact_id"):
                reference = self._register("fact_id", item.get("fact_id"))

            compacted: dict[str, Any] = {}
            for key, entry in item.items():
                if key in OPAQUE_ID_KEYS:
                    removed_counts[key] = removed_counts.get(key, 0) + 1
                    continue
                compacted[key] = visit(entry)
            if reference:
                compacted["evidence_ref"] = reference
                references_added += 1
            return compacted

        compacted_value = visit(value)
        return compacted_value, {
            "removed_fields": removed_counts,
            "removed_field_count": sum(removed_counts.values()),
            "references_added": references_added,
            "known_references": len(self._targets_by_ref),
        }


__all__ = ["EvidenceReferenceMap", "OPAQUE_ID_KEYS"]
