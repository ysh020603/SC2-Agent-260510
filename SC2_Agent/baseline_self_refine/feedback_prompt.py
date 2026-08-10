"""Feedback / critic prompt for Self-Refine."""

from __future__ import annotations

import json
from typing import Any, Dict, List


FEEDBACK_ROLE = """[Self-Refine Role: Feedback]
Critique the current candidate queue using only the same public decision
policy already present in the system prompt (strategy consistency, immediate
threat, unfinished carry-over, supply, worker saturation, resource banking,
prerequisite awareness, canonical vocabulary, near-term coherence).

Rules:
* Do NOT emit a replacement queue.
* Do NOT use external knowledge databases, counter tables, or hidden future state.
* needs_refinement must be a JSON boolean.
* Provide 0-5 actionable issues when refinement is needed.
* summary is a short public critique, not hidden chain-of-thought.

Output exactly one JSON object:
{"needs_refinement":true,"summary":"...","issues":[{"issue":"...","suggestion":"..."}]}
"""


def build_feedback_messages(
    *,
    system_prompt: str,
    decision_event: str,
    candidate: Dict[str, Any],
) -> List[Dict[str, str]]:
    user = (
        decision_event.rstrip()
        + "\n\n"
        + "[Current Candidate]\n"
        + json.dumps(candidate, ensure_ascii=False, indent=2)
        + "\n\n"
        + "[Feedback Task]\n"
        + "Judge whether the candidate needs refinement and list actionable issues."
    )
    return [
        {
            "role": "system",
            "content": system_prompt.rstrip() + "\n\n" + FEEDBACK_ROLE.strip(),
        },
        {"role": "user", "content": user},
    ]
