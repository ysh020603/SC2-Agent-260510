"""Lightweight filesystem trace for Plan-and-Execute decisions."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TraceRecorder:
    def __init__(self, log_dir: Optional[str]) -> None:
        self.enabled = bool(log_dir)
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:12]
        self.log_path: Optional[str] = None
        self.events: List[Dict[str, Any]] = []
        self._dir: Optional[str] = None
        if self.enabled and log_dir:
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            self._dir = os.path.join(log_dir, day, self.run_id)
            os.makedirs(self._dir, exist_ok=True)
            self.log_path = self._dir

    def add_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            **payload,
        }
        self.events.append(event)
        if not self._dir:
            return
        path = os.path.join(self._dir, "events.jsonl")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def finalize(self, result: Dict[str, Any]) -> Optional[str]:
        if not self._dir:
            return None
        path = os.path.join(self._dir, "trace.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
        return self._dir
