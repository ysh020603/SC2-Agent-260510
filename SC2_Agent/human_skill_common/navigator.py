"""Validated navigation facade used by READ_SKILL."""

from __future__ import annotations

from .skill_loader import ReadableSkill, ReadableSkillLoader


class SkillNavigator:
    def __init__(self, loader: ReadableSkillLoader, skill: ReadableSkill):
        self.loader = loader
        self.skill = skill

    def read(self, node_id: str) -> str:
        return self.loader.read_node(self.skill, node_id)

    def available_summary(
        self,
        *,
        phases: set[str] | None = None,
        prefer_unread: set[str] | None = None,
    ) -> str:
        if not self.skill.nodes:
            return "(none)"
        nodes = list(self.skill.nodes.values())
        if phases:
            matching = [node for node in nodes if not node.phase or node.phase in phases]
            if matching:
                nodes = matching
        if prefer_unread:
            unread = [node for node in nodes if node.node_id in prefer_unread]
            if unread:
                nodes = unread
        lines = []
        for node in nodes:
            children = f"; children={node.children}" if node.children else ""
            phase = f"; phase={node.phase}" if node.phase else ""
            policy = f" Phase policy: {node.policy_summary}" if node.policy_summary else ""
            lines.append(
                f"{node.node_id} [{node.node_type.upper()}] {node.title}: "
                f"{node.trigger_summary or node.summary}{policy}{phase}{children}"
            )
        return "\n".join(lines)
