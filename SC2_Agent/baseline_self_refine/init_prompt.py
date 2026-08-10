"""Init-role prompt for Self-Refine (naive-equivalent generation)."""

from __future__ import annotations

from typing import Dict, List


INIT_ROLE = """[Self-Refine Role: Init]
Produce the initial candidate replacement queue for this frozen decision.
This is round-0 generation in a Self-Refine pipeline. Follow the same public
response contract as a single-call macro decision.

Output exactly one JSON object:
{"reason":"A concise public explanation of the decision.","ordered_names":["one exact canonical name"]}
"""


def build_init_messages(
    *,
    system_prompt: str,
    decision_event: str,
) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": system_prompt.rstrip() + "\n\n" + INIT_ROLE.strip(),
        },
        {
            "role": "user",
            "content": (
                decision_event.rstrip()
                + "\n\n"
                + "[Init Task]\n"
                "Generate the initial complete replacement queue."
            ),
        },
    ]
