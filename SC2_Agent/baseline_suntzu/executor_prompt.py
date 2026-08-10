"""SunTzu Executor / Executor-Retry prompts."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence


EXECUTOR_ROLE = """[SunTzu Role: Executor]
Convert the verified semantic plan into one COMPLETE replacement queue of
exact canonical names. Follow the public response contract.

Output exactly one JSON object:
{"reason":"Concise public explanation.","ordered_names":["ExactName"]}
"""


RETRY_ROLE = """[SunTzu Role: Executor Retry]
Repair the previous queue using the deterministic verifier errors. Emit a
COMPLETE replacement queue, not a patch.

Output exactly one JSON object:
{"reason":"Repaired public explanation.","ordered_names":["ExactName"]}
"""


def build_executor_messages(
    *,
    system_prompt: str,
    decision_event: str,
    plan: Dict[str, Any],
) -> List[Dict[str, str]]:
    user = (
        decision_event.rstrip()
        + "\n\n[Verified Plan]\n"
        + json.dumps(plan, ensure_ascii=False, indent=2)
        + "\n\n[Executor Task]\nEmit the complete replacement queue."
    )
    return [
        {
            "role": "system",
            "content": system_prompt.rstrip() + "\n\n" + EXECUTOR_ROLE.strip(),
        },
        {"role": "user", "content": user},
    ]


def build_executor_retry_messages(
    *,
    system_prompt: str,
    decision_event: str,
    plan: Dict[str, Any],
    candidate: Dict[str, Any],
    errors: Sequence[str],
) -> List[Dict[str, str]]:
    user = (
        decision_event.rstrip()
        + "\n\n[Verified Plan]\n"
        + json.dumps(plan, ensure_ascii=False, indent=2)
        + "\n\n[Previous Candidate]\n"
        + json.dumps(candidate, ensure_ascii=False, indent=2)
        + "\n\n[Queue Verifier Errors]\n"
        + json.dumps(list(errors), ensure_ascii=False, indent=2)
        + "\n\n[Executor Retry Task]\nEmit a repaired complete replacement queue."
    )
    return [
        {
            "role": "system",
            "content": system_prompt.rstrip() + "\n\n" + RETRY_ROLE.strip(),
        },
        {"role": "user", "content": user},
    ]
