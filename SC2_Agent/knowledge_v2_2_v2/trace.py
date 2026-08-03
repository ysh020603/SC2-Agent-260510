"""Durable, per-question event and trace logging for the SC2 agent."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = REPOSITORY_ROOT / "game_records" / "_knowledge_v2_2"
SECRET_KEY_RE = re.compile(
    r"(^|[_-])(api[_-]?key|authorization|access[_-]?token|auth[_-]?token|secret|password)($|[_-])",
    re.IGNORECASE,
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseException):
        return {"type": type(value).__name__, "message": str(value)}
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SECRET_KEY_RE.search(str(key)) else _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                return _json_safe(method())
            except Exception:
                pass
    return repr(value)


class TraceRecorder:
    """Append crash-resilient events and produce one canonical trace.json."""

    schema_version = "sc2-agent-trace-v1"

    def __init__(self, query: str, log_dir: str | Path | None = None) -> None:
        now = datetime.now(timezone.utc)
        # A short random suffix is sufficient for per-process decision traces
        # and leaves headroom for descriptive Windows experiment paths.
        self.run_id = f"{now.strftime('%H%M%S')}_{uuid.uuid4().hex[:12]}"
        root = Path(log_dir or os.environ.get("SC2_LOG_DIR") or DEFAULT_LOG_DIR).expanduser().resolve()
        self.run_dir = root / now.date().isoformat() / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.events_path = self.run_dir / "events.jsonl"
        self.trace_path = self.run_dir / "trace.json"
        self.started_at = now.isoformat()
        self.events: list[dict[str, Any]] = []
        self.record("run_started", {"query": query})

    def record(self, event_type: str, payload: Any = None) -> dict[str, Any]:
        event = {
            "sequence": len(self.events) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "payload": _json_safe(payload or {}),
        }
        self.events.append(event)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def finalize(self, result: dict[str, Any] | None, status: str, error: Any = None) -> Path:
        finished_at = datetime.now(timezone.utc).isoformat()
        self.record("run_finished", {"status": status, "error": error})
        trace = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "status": status,
            "error": _json_safe(error),
            "events": self.events,
            "result": _json_safe(result or {}),
        }
        temporary = self.trace_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.trace_path)
        return self.trace_path


__all__ = ["DEFAULT_LOG_DIR", "TraceRecorder"]
