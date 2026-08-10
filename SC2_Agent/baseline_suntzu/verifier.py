"""Deterministic interface-level macro queue verification for SunTzu."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from .schemas import MAX_QUEUE_NAMES, MacroDecision


def verify_macro_queue(
    decision: Optional[MacroDecision],
    *,
    allowed_names: Sequence[str],
) -> Dict[str, Any]:
    """Validate public decision shape and canonical vocabulary only."""
    errors: List[str] = []
    if decision is None:
        return {"valid": False, "errors": ["missing_decision"]}
    if not isinstance(decision.reason, str) or not decision.reason.strip():
        errors.append("empty_reason")
    if not isinstance(decision.ordered_names, list):
        errors.append("ordered_names_not_list")
        return {"valid": False, "errors": errors}
    if len(decision.ordered_names) > MAX_QUEUE_NAMES:
        errors.append(f"queue_length_gt_{MAX_QUEUE_NAMES}")
    allowed = {name for name in allowed_names}
    for name in decision.ordered_names:
        if not isinstance(name, str) or not name.strip():
            errors.append("empty_canonical_name")
            continue
        if name not in allowed:
            errors.append(f"unknown_name:{name}")
    return {"valid": not errors, "errors": errors}


def allowed_canonical_names(
    unit_names: Iterable[str],
    upgrade_names: Iterable[str],
) -> List[str]:
    return sorted({*unit_names, *upgrade_names})
