"""Single-call macro decision prompt and response contract.

The model receives the strategy summary, current observation, and only the
canonical names from the previous queue that have not yet been committed to
the SC2 simulation.  Its response is the complete replacement queue.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MacroDecision:
    reason: str
    ordered_names: List[str]


def build_decision_messages(
    *,
    race: str,
    strategy_summary: str,
    obs_text: str,
    unfinished_canonical_names: List[str],
    canonical_unit_names: List[str],
    canonical_upgrade_names: List[str],
    race_context: str = "",
) -> List[Dict[str, str]]:
    """Build the only LLM prompt used by the macro runtime."""
    race_cap = race.capitalize()
    summary = strategy_summary.strip() or "(none)"
    units = ", ".join(canonical_unit_names)
    upgrades = ", ".join(canonical_upgrade_names)
    unfinished = json.dumps(unfinished_canonical_names, ensure_ascii=False)
    context = race_context.strip() or "(none)"
    worker_name = {
        "terran": "SCV",
        "protoss": "Probe",
        "zerg": "Drone",
    }.get(race.lower(), "worker")

    system_msg = f"""You are the macro decision agent for a {race_cap} StarCraft II bot.
Generate one complete, ordered replacement queue of concrete macro tasks.

[Overall Strategy Summary]
{summary}

[Canonical {race_cap} Units]
{units}

[Canonical {race_cap} Upgrades]
{upgrades}

[Race Mechanics]
{context}

Output exactly one JSON object:
{{"reason":"A concise public explanation of the decision.","ordered_names":["one exact canonical name","another exact canonical name"]}}

Rules:
* reason is required. It must be a concise 1-3 sentence decision explanation,
  not chain-of-thought, hidden reasoning, or a step-by-step thought process.
* ordered_names is required and may be empty.
* ordered_names is the COMPLETE new queue. It replaces every uncommitted item
  from the previous decision queue.
* Plan only the near-term work that should be attempted before the next macro
  decision. Do not emit the full-game build order. Keep the queue compact,
  normally no more than 20 names.
* The unfinished names in the user message have NOT been committed to the SC2
  simulation. Re-include every still-important item in ordered_names. Omit old
  items that should be abandoned or replaced.
* Work already committed to the simulation is not listed as unfinished. Do not
  recreate units, structures, morphs, add-ons, or research that the current
  observation already shows as in progress.
* Use only exact, case-sensitive names copied from the canonical lists.
  Strategy prose and observations are descriptive context, not an alternate
  vocabulary. Never output ability/action keys, generic producer/add-on names,
  pluralized entity names, counts, markdown, or prose outside the JSON object.
* Repeat a canonical name to request multiple copies.
* Order prerequisites and enabling infrastructure before dependent tasks.
* The runtime may execute an affordable later queue item while one earlier
  item waits for resources or technology. Queue order is priority, not a
  timing lock. Do not include a task merely because you want it several
  minutes later; include it only when executing it now is strategically safe
  or its explicit technology prerequisite makes early execution impossible.
* Supply is NOT managed by downstream code. Inspect current used/cap/free
  supply and include the race's canonical supply provider at the appropriate
  positions whenever needed. SupplyDepot, Pylon, and Overlord each add 8
  supply, and total supply cannot exceed 200. Request only enough copies for
  the near-term unit queue: normally 1, or 2-3 when a large production burst
  is imminent. Never fill most or all of the queue with supply providers.
* Worker production is NOT automatic. The observation's current/ideal worker
  counts are authoritative. Unless immediate survival takes priority, include
  repeated {worker_name} tasks while the economy is under-saturated; never
  describe it as saturated below roughly 75% of the displayed ideal count.
  In one near-term queue, normally request no more worker copies than the
  displayed current-to-ideal gap; if a new town hall is already under
  construction, only a small additional 2-4 workers may anticipate its slots.
  Do not chase every theoretical slot indefinitely: a normal late-game ceiling
  is about 70-80 SCVs/Probes or 75-85 Drones, and a strategy-specific lower
  worker target takes precedence.
* If minerals exceed roughly 1000 while supply is available, prioritize
  immediately trainable army units and enough production capacity to spend the
  income. Do not answer persistent banking with more workers, town halls, or
  unrelated luxury technology until the bank is falling.
* The runtime chooses the concrete executor or producer for each requested
  task. Do not emit executor names or positions."""

    user_msg = (
        f"[Current Observation]\n{obs_text or '(empty)'}\n\n"
        "[Uncommitted Tasks From The Previous Decision]\n"
        f"{unfinished}\n\n"
        "These names will be discarded when this decision is accepted. "
        "Re-include the important ones in the new ordered_names queue."
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def parse_decision_response(text: str) -> Optional[MacroDecision]:
    """Parse and validate the public decision response."""
    data = _extract_json_object(text)
    if data is None:
        return None
    reason = data.get("reason")
    names = data.get("ordered_names")
    if not isinstance(reason, str) or not reason.strip():
        return None
    if not isinstance(names, list):
        return None
    if any(not isinstance(name, str) or not name.strip() for name in names):
        return None
    return MacroDecision(
        reason=reason.strip()[:2000],
        ordered_names=[name.strip() for name in names],
    )


__all__ = [
    "MacroDecision",
    "build_decision_messages",
    "parse_decision_response",
]
