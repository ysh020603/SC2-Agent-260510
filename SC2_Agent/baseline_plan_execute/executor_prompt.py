"""Executor-role prompt for Plan-and-Execute."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

from .schemas import MAX_QUEUE_NAMES, PlanArtifact, PlanStep, plan_to_dict


EXECUTOR_ROLE = f"""[Plan-and-Execute Role: Executor]
You are the Executor for exactly one planner step. Convert that semantic
subtask into a canonical macro queue fragment.

Rules:
* Use only exact canonical names from the Allowed Macro Outputs lists.
* ordered_names is a FRAGMENT for this step, not the final full queue.
* Empty ordered_names is allowed when this step needs no new tasks.
* Preserve priority order inside the fragment.
* Do not deduplicate across steps; repeats are meaningful.
* Respect remaining recommended capacity for the aggregate queue
  (normally <= {MAX_QUEUE_NAMES} names total).
* Do not insert automatic prerequisites beyond what you explicitly list.
* Do not request a new observation or replan.
* reason is a concise public note, not hidden chain-of-thought.

Output exactly one JSON object:
{{"step_id":1,"reason":"Short public explanation.","ordered_names":["ExactName"]}}
"""


def build_executor_messages(
    *,
    system_prompt: str,
    decision_event: str,
    plan: PlanArtifact,
    step: PlanStep,
    previous_results: Sequence[Dict[str, Any]],
    accumulated_queue: Sequence[str],
) -> List[Dict[str, str]]:
    remaining = max(0, MAX_QUEUE_NAMES - len(accumulated_queue))
    user = (
        decision_event.rstrip()
        + "\n\n"
        + "[Full Plan]\n"
        + json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=2)
        + "\n\n"
        + "[Current Step To Execute]\n"
        + json.dumps(
            {"step_id": step.step_id, "objective": step.objective},
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        + "[Previous Executor Results]\n"
        + json.dumps(list(previous_results), ensure_ascii=False, indent=2)
        + "\n\n"
        + "[Accumulated Queue So Far]\n"
        + json.dumps(list(accumulated_queue), ensure_ascii=False)
        + "\n\n"
        + "[Capacity]\n"
        + f"current_accumulated_length: {len(accumulated_queue)}\n"
        + f"remaining_recommended_capacity: {remaining}\n"
        + f"recommended_max_total: {MAX_QUEUE_NAMES}\n\n"
        + "[Executor Task]\n"
        + "Emit the ordered_names fragment for the current step only."
    )
    return [
        {
            "role": "system",
            "content": system_prompt.rstrip() + "\n\n" + EXECUTOR_ROLE.strip(),
        },
        {"role": "user", "content": user},
    ]
