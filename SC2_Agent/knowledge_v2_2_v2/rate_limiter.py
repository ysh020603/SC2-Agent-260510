"""Cross-process request-rate limiting for provider-specific API quotas."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = REPO_ROOT / "game_records" / ".rate_limits" / "requests.sqlite3"
KIMI_BUCKET = "kimi"
KIMI_PROVIDER_MAX_RPM = 60
DEFAULT_KIMI_RPM = 50
DEFAULT_WINDOW_SECONDS = 60.0


def is_kimi_model(model_key: str | None, model_name: str | None) -> bool:
    identity = f"{model_key or ''} {model_name or ''}".lower()
    return "kimi" in identity or "moonshot" in identity


class SlidingWindowRateLimiter:
    """Coordinate one rolling-window quota through a small SQLite database."""

    def __init__(
        self,
        state_path: str | Path = DEFAULT_STATE_PATH,
        *,
        limit: int,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        bucket: str,
    ) -> None:
        if limit < 1:
            raise ValueError("Rate limit must be positive.")
        if window_seconds <= 0:
            raise ValueError("Rate-limit window must be positive.")
        self.state_path = Path(state_path).expanduser().resolve()
        self.limit = limit
        self.window_seconds = float(window_seconds)
        self.bucket = bucket

    def _connect(self) -> sqlite3.Connection:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.state_path), timeout=30.0, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS request_slots (bucket TEXT NOT NULL, requested_at REAL NOT NULL)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS request_slots_bucket_time "
            "ON request_slots(bucket, requested_at)"
        )
        return connection

    def acquire(self) -> float:
        started = time.monotonic()
        while True:
            connection = self._connect()
            wait_seconds = 0.0
            try:
                connection.execute("BEGIN IMMEDIATE")
                now = time.time()
                cutoff = now - self.window_seconds
                connection.execute(
                    "DELETE FROM request_slots WHERE bucket = ? AND requested_at <= ?",
                    (self.bucket, cutoff),
                )
                count, oldest = connection.execute(
                    "SELECT COUNT(*), MIN(requested_at) FROM request_slots WHERE bucket = ?",
                    (self.bucket,),
                ).fetchone()
                if int(count) < self.limit:
                    connection.execute(
                        "INSERT INTO request_slots(bucket, requested_at) VALUES (?, ?)",
                        (self.bucket, now),
                    )
                    connection.execute("COMMIT")
                    return max(0.0, time.monotonic() - started)
                wait_seconds = max(0.05, float(oldest) + self.window_seconds - now + 0.05)
                connection.execute("COMMIT")
            except Exception:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                connection.close()
            time.sleep(wait_seconds)


def configured_kimi_rpm() -> int:
    raw = os.environ.get("SC2_KIMI_RPM", str(DEFAULT_KIMI_RPM)).strip()
    value = int(raw)
    if not 1 <= value <= KIMI_PROVIDER_MAX_RPM:
        raise ValueError(
            f"SC2_KIMI_RPM must be between 1 and {KIMI_PROVIDER_MAX_RPM}, got {value}."
        )
    return value


def acquire_provider_slot(model_key: str | None, model_name: str | None) -> float:
    if not is_kimi_model(model_key, model_name):
        return 0.0
    limiter = SlidingWindowRateLimiter(
        os.environ.get("SC2_RATE_LIMIT_DB", str(DEFAULT_STATE_PATH)),
        limit=configured_kimi_rpm(),
        window_seconds=DEFAULT_WINDOW_SECONDS,
        bucket=KIMI_BUCKET,
    )
    return limiter.acquire()


__all__ = [
    "DEFAULT_KIMI_RPM",
    "KIMI_PROVIDER_MAX_RPM",
    "SlidingWindowRateLimiter",
    "acquire_provider_slot",
    "configured_kimi_rpm",
    "is_kimi_model",
]
