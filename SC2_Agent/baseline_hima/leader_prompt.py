"""HIMA leader aggregation prompt."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence


LEADER_ROLE = """[HIMA Role: Leader]
Aggregate the independent advisor outputs into one COMPLETE replacement queue.

Required reasoning order inside your short public reason:
1) agreed points
2) conflicted points
3) how you resolve conflicts
4) isolated useful suggestions
5) final direction

Only use valid advisor outputs supplied below. Ignore missing/invalid advisors.
Emit the final public queue contract.

Output exactly one JSON object:
{"reason":"Concise public explanation.","ordered_names":["ExactName"]}
"""


def build_leader_messages(
    *,
    system_prompt: str,
    decision_event: str,
    advisors: Sequence[Dict[str, Any]],
) -> List[Dict[str, str]]:
    user = (
        decision_event.rstrip()
        + "\n\n[Valid Advisor Outputs]\n"
        + json.dumps(list(advisors), ensure_ascii=False, indent=2)
        + "\n\n[Leader Task]\nSynthesize the advisors into one replacement queue."
    )
    return [
        {"role": "system", "content": system_prompt.rstrip() + "\n\n" + LEADER_ROLE.strip()},
        {"role": "user", "content": user},
    ]
