"""Match-scoped CoS L1 history state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .schemas import COS_HISTORY_SIZE


@dataclass
class CoSState:
    l1_history: List[Dict[str, Any]] = field(default_factory=list)
    max_history: int = COS_HISTORY_SIZE

    def reset(self) -> None:
        self.l1_history = []

    def append_l1(self, summary: Dict[str, Any]) -> None:
        self.l1_history.append(dict(summary))
        if len(self.l1_history) > int(self.max_history):
            self.l1_history = self.l1_history[-int(self.max_history) :]
