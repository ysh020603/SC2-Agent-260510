"""HIMA independent advisor prompts."""

from __future__ import annotations

from typing import Dict, List


def build_advisor_messages(
    *,
    system_prompt: str,
    decision_event: str,
    advisor_id: str,
) -> List[Dict[str, str]]:
    role = f"""[HIMA Role: Advisor {advisor_id}]
You are Advisor {advisor_id}. Independently assess the frozen macro situation
and suggest canonical macro actions. Do not coordinate with other advisors.
You do not finalize the replacement queue; the Leader will.

Output exactly one JSON object:
{{"advisor":"{advisor_id}","assessment":"Short public assessment.","suggested_actions":["ExactName"]}}
"""
    return [
        {"role": "system", "content": system_prompt.rstrip() + "\n\n" + role.strip()},
        {
            "role": "user",
            "content": (
                decision_event.rstrip()
                + f"\n\n[Advisor {advisor_id} Task]\n"
                "Provide your independent assessment and suggested_actions."
            ),
        },
    ]
