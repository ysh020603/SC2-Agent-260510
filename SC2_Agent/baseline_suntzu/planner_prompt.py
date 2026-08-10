"""SunTzu Planner / Plan-Refiner prompts."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

from .schemas import MAX_PLAN_COMMANDS


PLANNER_ROLE = f"""[SunTzu Role: Planner]
Produce a short semantic macro plan as ordered commands.

Rules:
* Emit 1 to {MAX_PLAN_COMMANDS} commands.
* Commands are high-level English objectives, not canonical unit names.
* Do NOT emit the final ordered_names queue.
* Do NOT include coordinates, unit ids, worker/producer selection, or CoT.

Output exactly one JSON object:
{{"plan_reason":"Short public summary.","commands":["Stabilize economy","Open production"]}}
"""


REFINER_ROLE = f"""[SunTzu Role: Plan Refiner]
Revise the semantic plan to address verifier errors. Keep 1 to {MAX_PLAN_COMMANDS}
commands. Still do NOT emit a canonical queue.

Output exactly one JSON object:
{{"plan_reason":"Revised plan summary.","commands":["..."]}}
"""


def build_planner_messages(
    *,
    system_prompt: str,
    decision_event: str,
) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt.rstrip() + "\n\n" + PLANNER_ROLE.strip()},
        {
            "role": "user",
            "content": decision_event.rstrip()
            + "\n\n[Planner Task]\nCreate an ordered semantic macro plan.",
        },
    ]


def build_plan_refiner_messages(
    *,
    system_prompt: str,
    decision_event: str,
    plan: Dict[str, Any],
    errors: Sequence[str],
) -> List[Dict[str, str]]:
    user = (
        decision_event.rstrip()
        + "\n\n[Current Plan]\n"
        + json.dumps(plan, ensure_ascii=False, indent=2)
        + "\n\n[Verifier Errors]\n"
        + json.dumps(list(errors), ensure_ascii=False, indent=2)
        + "\n\n[Plan Refiner Task]\nRevise the plan to address the errors."
    )
    return [
        {"role": "system", "content": system_prompt.rstrip() + "\n\n" + REFINER_ROLE.strip()},
        {"role": "user", "content": user},
    ]
