"""Planner-role prompt for Plan-and-Execute."""

from __future__ import annotations

from typing import Dict, List

from .schemas import MAX_PLAN_STEPS


PLANNER_ROLE = f"""[Plan-and-Execute Role: Planner]
You are the Planner only. Produce a short ordered plan of semantic macro
subtasks for the frozen decision context below.

Rules:
* Output 1 to {MAX_PLAN_STEPS} steps inclusive.
* step_id must be 1..N in order with no gaps.
* Each objective is a high-level macro subtask in plain English.
* Do NOT emit canonical unit/structure names as the plan itself.
* Do NOT emit the final ordered_names queue.
* Do NOT call tools, request new observations, or choose workers/producers.
* Do NOT include hidden chain-of-thought. plan_summary is a short public note.

Output exactly one JSON object:
{{"plan_summary":"Short public summary.","steps":[{{"step_id":1,"objective":"..."}},{{"step_id":2,"objective":"..."}}]}}
"""


def build_planner_messages(
    *,
    system_prompt: str,
    decision_event: str,
) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": system_prompt.rstrip() + "\n\n" + PLANNER_ROLE.strip(),
        },
        {
            "role": "user",
            "content": (
                decision_event.rstrip()
                + "\n\n"
                + "[Planner Task]\n"
                "Decompose the macro decision into ordered semantic steps."
            ),
        },
    ]
