"""Validated navigation facade used by READ_SKILL."""

from __future__ import annotations

from .skill_loader import ReadableSkill, ReadableSkillLoader


class SkillNavigator:
    def __init__(self, loader: ReadableSkillLoader, skill: ReadableSkill):
        self.loader = loader
        self.skill = skill

    def read(self, node_id: str) -> str:
        return self.loader.read_node(self.skill, node_id)

    def available_summary(self) -> str:
        if not self.skill.nodes:
            return "(none)"
        lines = []
        for node in self.skill.nodes.values():
            children = f"; children={node.children}" if node.children else ""
            lines.append(
                f"{node.node_id} [{node.node_type.upper()}] {node.title}: "
                f"{node.trigger_summary or node.summary}{children}"
            )
        return "\n".join(lines)
