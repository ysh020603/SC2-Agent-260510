"""Append-only tactical posture trace."""

from __future__ import annotations

import json
import os
from datetime import datetime


class TacticalTraceLogger:
    def __init__(self, output_directory="", skill_id=None, config=None):
        self.output_directory = output_directory or "game_records"
        self.skill_id = skill_id
        self.config = config
        self.events = []
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        self.output_path = os.path.join(
            self.output_directory,
            "UniversalTactics_{}.tactical_trace.json".format(timestamp),
        )

    def record(self, *, game_time, from_posture, to_posture, reason, snapshot, event="posture_change"):
        item = {
            "event": event,
            "game_time": float(game_time),
            "from": getattr(from_posture, "value", from_posture),
            "to": getattr(to_posture, "value", to_posture),
            "reason": reason,
            "snapshot": snapshot.trace_view() if snapshot is not None else {},
            "skill_id": self.skill_id,
            "skill_id_used_for_routing": False,
        }
        self.events.append(item)
        self.flush()

    def flush(self):
        os.makedirs(self.output_directory, exist_ok=True)
        payload = {
            "schema_version": 1,
            "controller": "Universal Tactical Controller V1",
            "config": self.config.as_dict() if self.config else {},
            "config_hash": self.config.stable_hash() if self.config else None,
            "skill_id_used_for_routing": False,
            "posture_timeline": self.events,
        }
        temporary = self.output_path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, self.output_path)
