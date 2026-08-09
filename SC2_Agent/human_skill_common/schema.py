"""Typed data exchanged inside the human-skill runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SkillNode:
    node_id: str
    path: str
    node_type: str
    title: str
    summary: str
    trigger_summary: str
    children: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReadSkillRequest:
    node_id: str


@dataclass(frozen=True)
class FinalDecision:
    reason: str
    ordered_names: List[str]


@dataclass(frozen=True)
class AgentRound:
    round: int
    type: str
    node_id: Optional[str] = None
    error: Optional[str] = None
    model_key: str = ""
    model: str = ""
    token_usage: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProtocolParseResult:
    request: Optional[ReadSkillRequest] = None
    decision: Optional[FinalDecision] = None
    error: Optional[str] = None
