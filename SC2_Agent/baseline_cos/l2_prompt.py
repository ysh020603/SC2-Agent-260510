"""CoS L2 commander prompt."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence


L2_ROLE = """[CoS Role: L2 Commander]
Use the recent L1 summaries plus the frozen decision context to emit one
COMPLETE replacement queue. Follow the public response contract.

Output exactly one JSON object:
{"reason":"Concise public explanation.","ordered_names":["ExactName"]}
"""


def build_l2_messages(
    *,
    system_prompt: str,
    decision_event: str,
    l1_history: Sequence[Dict[str, Any]],
) -> List[Dict[str, str]]:
    user = (
        decision_event.rstrip()
        + "\n\n[Recent L1 Summaries]\n"
        + json.dumps(list(l1_history), ensure_ascii=False, indent=2)
        + "\n\n[L2 Task]\nEmit the complete replacement queue."
    )
    return [
        {"role": "system", "content": system_prompt.rstrip() + "\n\n" + L2_ROLE.strip()},
        {"role": "user", "content": user},
    ]
