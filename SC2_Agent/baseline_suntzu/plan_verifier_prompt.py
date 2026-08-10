"""SunTzu Plan Verifier prompt."""

from __future__ import annotations

import json
from typing import Any, Dict, List


VERIFIER_ROLE = """[SunTzu Role: Plan Verifier]
Critique the semantic plan using only the same public macro policy in the
system prompt. Do not emit a queue. Do not use external knowledge.

If the plan is acceptable, set error_number to 0 and errors to [].
Otherwise list concrete errors; error_number must equal len(errors).

Output exactly one JSON object:
{"error_number":0,"errors":[]}
"""


def build_plan_verifier_messages(
    *,
    system_prompt: str,
    decision_event: str,
    plan: Dict[str, Any],
) -> List[Dict[str, str]]:
    user = (
        decision_event.rstrip()
        + "\n\n[Plan To Verify]\n"
        + json.dumps(plan, ensure_ascii=False, indent=2)
        + "\n\n[Plan Verifier Task]\nReturn error_number and errors."
    )
    return [
        {
            "role": "system",
            "content": system_prompt.rstrip() + "\n\n" + VERIFIER_ROLE.strip(),
        },
        {"role": "user", "content": user},
    ]
