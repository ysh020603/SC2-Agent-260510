"""Shared prompt sections; each package adds its own method contract."""

from __future__ import annotations

import json
from typing import List

from SC2_Agent.prompt_context import OBSERVATION_FIELD_GUIDE, decision_lifecycle_context

from .skill_loader import ReadableSkill
from .skill_memory import MatchSkillMemory


def build_human_skill_messages(
    *,
    race: str,
    enemy_race: str,
    variant_contract: str,
    skill: ReadableSkill,
    memory: MatchSkillMemory,
    available_nodes: str,
    obs_text: str,
    unfinished_canonical_names: List[str],
    canonical_unit_names: List[str],
    canonical_upgrade_names: List[str],
    race_context: str,
    automation_context: str,
    decision_cycle: int,
    trigger_reason: str,
    game_time_seconds: float,
    decision_interval_seconds: float,
    protocol_feedback: str = "",
    force_final: bool = False,
) -> List[dict[str, str]]:
    race_cap = race.capitalize()
    units = ", ".join(canonical_unit_names)
    upgrades = ", ".join(canonical_upgrade_names)
    final_instruction = (
        "You have reached the navigation limit. You MUST output a decision now; "
        "READ_SKILL is not permitted in this final call."
        if force_final
        else "If a relevant summary is insufficient, you may request one node."
    )
    system = f"""[1. Agent Role]
You are the macro decision agent for a {race_cap} StarCraft II bot. Produce a
compact replacement queue of exact canonical macro names. Your public reason
must summarize the decision without private chain-of-thought.

[2. Decision Lifecycle]
{decision_lifecycle_context(decision_interval_seconds=decision_interval_seconds)}

[3. Queue / Commitment Semantics]
ordered_names replaces all uncommitted tasks. Re-include important carry-over
work. Completed, Under Construction, Workers En Route, and Active Queues are
already committed and must not be duplicated. The runtime never inserts
prerequisites. Queue order is priority, not a timing lock.

[4. Race Mechanics]
{race_context}

[5. Economy / Supply / Production Principles]
Inspect resource bank, income, free supply, current/ideal workers, army supply,
production capacity, prerequisites, and active queues. Avoid supply blocks,
keep worker growth sensible, spend persistent banks through usable production,
and keep the queue focused on work safe before the next decision.

[6. Observation Field Guide]
{OBSERVATION_FIELD_GUIDE}

[7. Opening Skill]
Method: {skill.method}
{skill.root_markdown}

[8. Previously Read Skill Nodes]
{memory.rendered_nodes()}

[9. Variant Information Boundary]
{variant_contract}

[10. Available Node Index]
{available_nodes}

[11. Automated Tactical Boundary]
{automation_context}

[12. Skill Use Principles]
First inspect the live observation. Skill prose is strategic guidance, not an
executable build order. Current Observation has priority when selecting exact
actions. Previously read nodes are reusable knowledge, never commands. Never
copy a historical sequence. Reconcile guidance with Resources, Supply,
Completed, Under Construction, Active Queues, Enemy Intelligence, Army/Income
Advantage, and Threat Flags.

[13. Allowed Canonical Outputs]
Canonical units, structures, add-ons, and morphs:
{units}

Canonical upgrades:
{upgrades}

Use exact case-sensitive names from these lists only. Repeat a name for
multiple copies. Do not output counts, action keys, positions, or prose outside
the JSON object. Keep the queue compact, normally no more than 20 names.

[14. Skill Read Protocol]
{final_instruction}
READ_SKILL: {{"type":"read_skill","node_id":"N001"}}
FINAL_DECISION: {{"type":"decision","reason":"1-3 sentence public explanation","ordered_names":["Pylon"]}}
Output exactly one JSON object with exactly the fields shown for its type.
"""
    feedback = protocol_feedback.strip()
    user = (
        "[Decision Event]\n"
        f"Cycle: {int(decision_cycle)}\n"
        f"Trigger: {trigger_reason}\n"
        f"Game time: {float(game_time_seconds):.1f} seconds\n"
        f"Opponent race: {enemy_race.capitalize()}\n\n"
        f"[Current Observation]\n{obs_text or '(empty)'}\n\n"
        "[Carry-over Uncommitted Tasks]\n"
        f"{json.dumps(unfinished_canonical_names, ensure_ascii=False)}\n"
    )
    if feedback:
        user += f"\n[Protocol Feedback From Prior Round]\n{feedback}\n"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
