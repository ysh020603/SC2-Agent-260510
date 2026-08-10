"""Refine / iterate prompt for Self-Refine."""

from __future__ import annotations

import json
from typing import Any, Dict, List


REFINE_ROLE = """[Self-Refine Role: Refine]
Produce a COMPLETE replacement queue that addresses the feedback. Do not emit
a patch or diff. Re-include still-important unfinished tasks. Keep the same
canonical vocabulary and near-term horizon constraints.

Output exactly one JSON object:
{"reason":"Revised macro decision after self-feedback.","ordered_names":["ExactName"]}
"""


def build_refine_messages(
    *,
    system_prompt: str,
    decision_event: str,
    candidate: Dict[str, Any],
    feedback: Dict[str, Any],
) -> List[Dict[str, str]]:
    user = (
        decision_event.rstrip()
        + "\n\n"
        + "[Current Candidate]\n"
        + json.dumps(candidate, ensure_ascii=False, indent=2)
        + "\n\n"
        + "[Feedback]\n"
        + json.dumps(feedback, ensure_ascii=False, indent=2)
        + "\n\n"
        + "[Refine Task]\n"
        + "Emit a full revised replacement queue."
    )
    return [
        {
            "role": "system",
            "content": system_prompt.rstrip() + "\n\n" + REFINE_ROLE.strip(),
        },
        {"role": "user", "content": user},
    ]
