"""CoS L1 single-frame summary prompt."""

from __future__ import annotations

from typing import Dict, List


L1_ROLE = """[CoS Role: L1 Summarizer]
Summarize ONLY the current frozen observation into compact fields.
Do not emit a replacement queue.
Do not use previous L1 history.
Do not invent unseen enemy details beyond the observation text.

Output exactly one JSON object:
{"game_time":0.0,"economy":"...","production":"...","army":"...","enemy":"...","supply":"...","committed_work":"...","strategic_signal":"..."}
"""


def build_l1_messages(
    *,
    system_prompt: str,
    decision_event: str,
) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt.rstrip() + "\n\n" + L1_ROLE.strip()},
        {
            "role": "user",
            "content": decision_event.rstrip()
            + "\n\n[L1 Task]\nSummarize the current observation fields only.",
        },
    ]
