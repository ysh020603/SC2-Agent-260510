"""Read only the Agent-facing root, index, and node Markdown files."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable

from .schema import SkillNode
from .validation import (
    HumanSkillValidationError,
    validate_node_type,
    validate_relative_node_path,
)

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_METHODS = {
    "full_signed_graph",
    "full_guarded_graph_v2",
    "ablation_single_trace",
    "ablation_static_population",
    "ablation_flat_adaptive",
    "ablation_positive_only",
    "ablation_frequency_only",
}


@dataclass(frozen=True)
class ReadableSkill:
    skill_id: str
    opening_name: str
    method: str
    race: str
    matchup: str
    directory: str
    root_markdown: str
    nodes: Dict[str, SkillNode]


def resolve_readable_skill_root(repo_root: str, explicit: str = "") -> str:
    candidates = [
        explicit,
        os.environ.get("SC2_READABLE_SKILL_ROOT", ""),
        os.path.join(repo_root, "SKILL_MINING_V2_READABLE"),
        os.path.join(os.path.dirname(repo_root), "SKILL_MINING_V2_READABLE"),
    ]
    for candidate in candidates:
        if candidate and os.path.isdir(os.path.abspath(candidate)):
            return os.path.abspath(candidate)
    rendered = ", ".join(os.path.abspath(item) for item in candidates if item)
    raise FileNotFoundError(f"Readable skill root not found; checked: {rendered}")


class ReadableSkillLoader:
    """Validated loader that cannot access provenance or arbitrary paths."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.realpath(os.path.abspath(root_dir))
        if not os.path.isdir(self.root_dir):
            raise FileNotFoundError(self.root_dir)

    @staticmethod
    def _safe_component(value: str, label: str) -> str:
        value = str(value or "").strip()
        if not _SAFE_ID_RE.fullmatch(value):
            raise HumanSkillValidationError(f"unsafe {label}: {value!r}")
        return value

    def load(
        self,
        *,
        method: str,
        race: str,
        matchup: str,
        skill_id: str,
        allowed_node_types: Iterable[str],
        allow_graph_navigation: bool,
    ) -> ReadableSkill:
        method = self._safe_component(method, "method")
        if method not in _METHODS:
            raise HumanSkillValidationError(f"unknown readable-skill method: {method}")
        race = self._safe_component(race.lower(), "race")
        matchup = self._safe_component(matchup, "matchup")
        skill_id = self._safe_component(skill_id, "skill id")
        directory = os.path.realpath(os.path.join(self.root_dir, method, race, matchup, skill_id))
        if os.path.commonpath([self.root_dir, directory]) != self.root_dir:
            raise HumanSkillValidationError("skill directory escaped configured root")
        root_path = os.path.join(directory, "SKILL.md")
        index_path = os.path.join(directory, "index.json")
        with open(root_path, "r", encoding="utf-8") as handle:
            root_markdown = handle.read()
        with open(index_path, "r", encoding="utf-8") as handle:
            index = json.load(handle)
        if index.get("skill_id") != skill_id or index.get("method") != method:
            raise HumanSkillValidationError("index identity does not match pinned skill")
        if index.get("root") != "SKILL.md":
            raise HumanSkillValidationError("index root must be SKILL.md")
        raw_nodes = index.get("nodes")
        if not isinstance(raw_nodes, dict):
            raise HumanSkillValidationError("index nodes must be an object")
        nodes: Dict[str, SkillNode] = {}
        for node_id, raw in raw_nodes.items():
            node_id = self._safe_component(node_id, "node id")
            if not isinstance(raw, dict):
                raise HumanSkillValidationError(f"invalid index entry for {node_id}")
            node_type = str(raw.get("type") or "").lower()
            validate_node_type(node_type, allowed_node_types)
            path = validate_relative_node_path(str(raw.get("path") or ""))
            children = raw.get("children") or []
            if not isinstance(children, list) or any(not isinstance(x, str) for x in children):
                raise HumanSkillValidationError(f"invalid children for {node_id}")
            if children and not allow_graph_navigation:
                raise HumanSkillValidationError(f"graph navigation is disabled but {node_id} has children")
            nodes[node_id] = SkillNode(
                node_id=node_id,
                path=path,
                node_type=node_type,
                title=str(raw.get("title") or ""),
                summary=str(raw.get("summary") or ""),
                trigger_summary=str(raw.get("trigger_summary") or ""),
                children=list(children),
            )
        for node in nodes.values():
            for child in node.children:
                if child not in nodes:
                    raise HumanSkillValidationError(f"node {node.node_id} references missing child {child}")
            node_path = os.path.realpath(os.path.join(directory, node.path))
            node_root = os.path.realpath(os.path.join(directory, "nodes"))
            if os.path.commonpath([node_root, node_path]) != node_root:
                raise HumanSkillValidationError(f"node path escaped nodes/: {node.path}")
            if not os.path.isfile(node_path):
                raise FileNotFoundError(node_path)
        return ReadableSkill(
            skill_id=skill_id,
            opening_name=str(index.get("opening_name") or skill_id),
            method=method,
            race=race,
            matchup=matchup,
            directory=directory,
            root_markdown=root_markdown,
            nodes=nodes,
        )

    @staticmethod
    def read_node(skill: ReadableSkill, node_id: str) -> str:
        if node_id not in skill.nodes:
            raise HumanSkillValidationError(f"unknown node id: {node_id}")
        node = skill.nodes[node_id]
        node_root = os.path.realpath(os.path.join(skill.directory, "nodes"))
        node_path = os.path.realpath(os.path.join(skill.directory, node.path))
        if os.path.commonpath([node_root, node_path]) != node_root:
            raise HumanSkillValidationError("node read escaped nodes directory")
        with open(node_path, "r", encoding="utf-8") as handle:
            return handle.read()
