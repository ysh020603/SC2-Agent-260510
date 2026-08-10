"""Decision and per-match skill-read logging (schema version 5)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .skill_memory import MatchSkillMemory


class HumanSkillTraceRecorder:
    def __init__(self, record_dir: str = "", match_id: str = "human_skill"):
        self.record_dir = str(record_dir or "").strip()
        self.match_id = str(match_id or "human_skill").strip()
        self.decisions: List[Dict[str, Any]] = []

    def record_decision(self, record: Dict[str, Any]) -> None:
        self.decisions.append(record)

    def flush(self, memory: MatchSkillMemory) -> Dict[str, str]:
        if not self.record_dir:
            return {}
        os.makedirs(self.record_dir, exist_ok=True)
        decision_path = os.path.join(self.record_dir, f"{self.match_id}.human_skill.json")
        reads_path = os.path.join(self.record_dir, f"{self.match_id}.skill_reads.json")
        with open(decision_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "schema_version": 5,
                    "decision_count": len(self.decisions),
                    "decisions": self.decisions,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        with open(reads_path, "w", encoding="utf-8") as handle:
            json.dump(memory.to_log(), handle, ensure_ascii=False, indent=2)
        return {"decisions": decision_path, "skill_reads": reads_path}
