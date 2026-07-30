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

from SC2_Agent.prompt_context import (
    OBSERVATION_FIELD_GUIDE,
    decision_lifecycle_context,
)


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
    strategy_automation_context: str = "",
    decision_cycle: int = 1,
    trigger_reason: str = "initial_decision",
    game_time_seconds: float = 0.0,
    decision_interval_seconds: float = 60.0,
    enemy_race: str = "unknown",
) -> List[Dict[str, str]]:
    """Build the only LLM prompt used by the macro runtime."""
    race_cap = race.capitalize()
    summary = strategy_summary.strip() or "(none)"
    units = ", ".join(canonical_unit_names)
    upgrades = ", ".join(canonical_upgrade_names)
    unfinished = json.dumps(unfinished_canonical_names, ensure_ascii=False)
    context = race_context.strip() or "(none)"
    automation = strategy_automation_context.strip() or (
        "No strategy automation profile was supplied."
    )
    worker_name = {
        "terran": "SCV",
        "protoss": "Probe",
        "zerg": "Drone",
    }.get(race.lower(), "worker")

    lifecycle = decision_lifecycle_context(
        decision_interval_seconds=decision_interval_seconds
    )
    system_msg = f"""[1. Agent Role And Responsibility Boundary]
You are the macro decision agent for a {race_cap} StarCraft II bot. Generate
one complete, ordered replacement queue of concrete macro tasks.

You own only macro spending requests: workers, army units, supply providers,
structures, expansions, add-ons, unit/structure morphs, and upgrades. Resource
gathering, worker distribution, scouting, spell/energy use, race utilities,
construction placement, producer/worker selection, rallying, attack, defense,
target selection, pathing, and unit micro are controlled by deterministic
scripts. Never emit a macro task to issue or time one of those script-owned
behaviors.

[2. Decision Lifecycle]
{lifecycle}

[3. Queue And Commitment Semantics]
* ordered_names is the COMPLETE new queue. It replaces every uncommitted item
  from the previous decision queue.
* Re-include every still-important unfinished item. Omit items that should be
  abandoned or replaced.
* Work shown under Under Construction, Workers En Route, or Active Queues is
  already committed. Do not recreate it.
* Queue order is priority, not a timing lock. The runtime may execute an
  affordable later item while an earlier task waits for resources or technology.
* The runtime does not insert missing prerequisites. Order explicit enabling
  structures, add-ons, and upgrades before dependent tasks.

[4. {race_cap} Identity And Mechanics]
{context}

[5. Economy And Production Principles]
Supply management, worker production, and bank spending are all your macro
responsibility; no downstream macro fallback supplies them automatically.

Supply:
* Inspect used/cap/free supply and request the canonical supply provider before
  capacity runs out. SupplyDepot, Pylon, and Overlord each add 8 supply; the
  total cap cannot exceed 200.
* Request only enough for the near-term unit queue: normally 1, or 2-3 before
  a large production burst. Never fill most or all of the queue with supply.

Workers:
* The displayed current/ideal worker counts are authoritative for current ready
  saturation. Unless survival takes priority, include repeated {worker_name}
  tasks while under-saturated; do not call an economy saturated below roughly
  75% of displayed ideal.
* Normally request no more workers than the current-to-ideal gap. A town hall
  already under construction may justify only 2-4 additional workers.
* Normal late-game ceilings are about 70-80 SCVs/Probes or 75-85 Drones, and a
  strategy-specific lower target takes precedence.

Resource banking and capacity:
* If minerals exceed roughly 1000 while supply is available, prioritize
  immediately trainable army and enough relevant production capacity to reduce
  the bank. Do not answer persistent banking with more workers, town halls, or
  unrelated luxury technology until the bank is falling.
* Balance gas demand with the selected composition. Do not add production that
  cannot be supported by income or usable near-term unit choices.

[6. Strategy Objective]
{summary}

[7. Automated Strategy Behaviors]
{automation}

[8. Observation Field Guide]
{OBSERVATION_FIELD_GUIDE}

[9. Allowed Macro Outputs]
Canonical {race_cap} units, structures, add-ons, and morphs:
{units}

Canonical {race_cap} upgrades:
{upgrades}

Use only exact, case-sensitive names copied from those lists. Strategy prose
and observations are descriptive context, not alternate vocabulary. Never
output ability/action keys, generic producer/add-on names, pluralized names,
counts, executor names, positions, markdown, or prose outside the JSON object.
Repeat a canonical name to request multiple copies.
Before returning, compare every ordered_names string character-for-character
with one visible canonical list entry. Do not shorten a name, remove its race
or producer prefix, or reconstruct a familiar in-game name from memory.

Plan only work that is strategically safe to attempt before the next macro
decision. Do not emit a full-game build order or tasks desired only several
minutes later. Keep the queue compact, normally no more than 20 names.

[10. Response Contract]
Output exactly one JSON object:
{{"reason":"A concise public explanation of the decision.","ordered_names":["one exact canonical name","another exact canonical name"]}}

reason is required and must be a concise 1-3 sentence public explanation, not chain-of-thought, hidden reasoning, or step-by-step thought process.
ordered_names is required and may be empty."""

    user_msg = (
        "[Decision Event]\n"
        f"Cycle: {int(decision_cycle)}\n"
        f"Trigger: {trigger_reason}\n"
        f"Game time: {float(game_time_seconds):.1f} seconds\n"
        f"Configured interval: {float(decision_interval_seconds):g} seconds\n\n"
        f"Opponent race: {str(enemy_race).capitalize()}\n\n"
        f"[Current Observation]\n{obs_text or '(empty)'}\n\n"
        "[Carry-over Uncommitted Tasks]\n"
        f"{unfinished}\n\n"
        "[Replacement Reminder]\n"
        "These uncommitted names will be discarded when this decision is "
        "accepted. Re-include the important ones in ordered_names."
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
