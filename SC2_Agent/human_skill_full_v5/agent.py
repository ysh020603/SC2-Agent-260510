from __future__ import annotations

import re

from SC2_Agent.human_skill_common.agent_base import HumanSkillAgent

from .config import AGENT_VERSION, ALLOWED_NODE_TYPES, ALLOW_GRAPH_NAVIGATION, SKILL_METHOD
from .prompt import VARIANT_CONTRACT


class HumanSkillFullV5Agent(HumanSkillAgent):
    """Trajectory-fusion agent with phase routing and a race-aware live bottleneck."""

    GRAPH_PHASE_START_SECONDS = (0.0, 300.0, 600.0)

    def __init__(self, **kwargs):
        super().__init__(
            agent_version=AGENT_VERSION,
            skill_method=SKILL_METHOD,
            allowed_node_types=ALLOWED_NODE_TYPES,
            allow_graph_navigation=ALLOW_GRAPH_NAVIGATION,
            variant_contract=VARIANT_CONTRACT,
            **kwargs,
        )

    @staticmethod
    def _phase(game_time_seconds: float) -> str:
        if game_time_seconds < 240:
            return "early_game"
        if game_time_seconds < 420:
            return "early_midgame"
        if game_time_seconds < 600:
            return "midgame"
        return "late_midgame"

    def _available_node_summary(self, *, game_time_seconds: float, obs_text: str) -> str:
        del obs_text
        phase = self._phase(game_time_seconds)
        unread = set(self.skill.nodes) - set(self.memory.visited_node_ids)
        unread_in_phase = {
            node.node_id
            for node in self.skill.nodes.values()
            if node.node_id in unread and (not node.phase or node.phase == phase)
        }
        if unread_in_phase:
            return self.navigator.available_summary(phases={phase}, prefer_unread=unread_in_phase)
        if unread:
            # A graph refresh must always be able to see an unread fallback even when the
            # mined graph has no additional node in the exact runtime phase.
            return self.navigator.available_summary(prefer_unread=unread)
        return self.navigator.available_summary(phases={phase})

    @staticmethod
    def _number(pattern: str, text: str, default: float = 0.0) -> float:
        match = re.search(pattern, text, re.IGNORECASE)
        return float(match.group(1)) if match else default

    def _runtime_policy_context(self, *, race: str, obs_text: str, game_time_seconds: float) -> str:
        mineral_match = re.search(r"\[Economy\]\s*([0-9]+)\s+minerals,\s*([0-9]+)\s+vespene", obs_text, re.IGNORECASE)
        minerals = float(mineral_match.group(1)) if mineral_match else 0.0
        gas = float(mineral_match.group(2)) if mineral_match else 0.0
        supply_match = re.search(r"Supply:\s*([0-9.]+)\s*/\s*([0-9.]+).*?workers\s+([0-9.]+)\s*/\s*([0-9.]+).*?army\s+([0-9.]+)", obs_text, re.IGNORECASE)
        if supply_match:
            used, cap, workers, ideal, army = (float(supply_match.group(i)) for i in range(1, 6))
        else:
            used = cap = workers = ideal = army = 0.0
        free = max(0.0, cap - used)
        predicted_match = re.search(r"predicted\s*=\s*([A-Za-z]+)", obs_text, re.IGNORECASE)
        predicted = predicted_match.group(1) if predicted_match else "Unknown"
        threat_match = re.search(r"\[Threat Flags\]\s*([^\n]+)", obs_text, re.IGNORECASE)
        threat_text = threat_match.group(1).strip() if threat_match else "unknown"
        threatened = threat_text.lower() not in {"none.", "none", "unknown"}
        active_match = re.search(r"Active Queues:\s*([^\n]+)", obs_text, re.IGNORECASE)
        active = active_match.group(1).strip() if active_match else "unknown"
        larvae = self._number(r"\b([0-9]+)\s+LARVA\b", obs_text)
        bank = minerals + gas
        severe = predicted.lower() in {"overwhelmingdisadvantage", "disadvantage"}
        phase = self._phase(game_time_seconds)

        if threatened or severe:
            bottleneck = "survival_and_counterproduction"
            action = "Make immediately executable army, counters, and required detection the first queue work; optional workers, expansion, upgrades, and tech wait."
            veto = "Do not preserve economic greed merely to match the opening when a base is threatened or the live comparison is severely unfavorable."
        elif free <= 4 and cap < 200:
            bottleneck = "projected_supply"
            action = "Place only enough supply before the first unit that would block, accounting for completed, pending, queued, and absolute 200-cap supply."
            veto = "Do not pad the queue with supply providers beyond the executable unit demand for this decision interval."
        elif bank >= 750 and army < max(6.0, game_time_seconds / 30.0):
            bottleneck = "bank_to_army_conversion"
            if race.lower().startswith("z"):
                action = "Spend through available larvae on the phase-appropriate army; if larvae are exhausted, improve larva throughput with executable Queen/base mechanics rather than treating tech structures as generic producers."
                veto = "Do not answer a larva bottleneck with extra tech structures, excess Drones, or excess Overlords."
            elif race.lower().startswith("t"):
                action = "Use completed parent producers first; add a Barracks/Factory/Starport only when compatible queues can keep the added capacity busy, and order parent before add-on or dependent unit."
                veto = "Do not leave usable parents idle while ordering future add-ons, upgrades, or optional expansion."
            else:
                action = "Spend through completed powered producers on the phase-appropriate army; add a powered producer only when existing compatible capacity is busy or the planned throughput justifies it."
                veto = "Do not replace an executable army response with extra Robotics Facilities, Gateways, or technology solely because the clock crossed a threshold."
        elif workers < ideal and not threatened:
            bottleneck = "safe_economy"
            action = "Continue worker growth toward the currently reported ideal while retaining room for the current phase's army and technology target."
            veto = "Do not queue workers so far ahead that combat production cannot start within this decision interval."
        else:
            bottleneck = "human_phase_policy"
            action = "Follow the selected trajectory-derived phase target and use live Enemy Intelligence to choose the exact army/economy/technology trade-off."
            veto = "Do not invent a new universal timing threshold or copy a historical action sequence."

        if race.lower().startswith("z"):
            mechanics = f"Zerg capacity snapshot: {larvae:g} visible larvae; Overlords consume larvae, Hatchery/Lair/Hive provide larva cycles, and Drones compete with army morphs."
        elif race.lower().startswith("t"):
            mechanics = "Terran capacity snapshot: distinguish completed parents, add-ons, and active queues; a structure entry always means one additional structure."
        else:
            mechanics = "Protoss capacity snapshot: count only completed/powered compatible production and respect tech prerequisites; a structure entry always means one additional structure."
        return (
            f"Current phase: {phase}. Observed bank={bank:g}, supply={used:g}/{cap:g}, army={army:g}, "
            f"workers={workers:g}/{ideal:g}, predicted={predicted}, threats={threat_text}, active queues={active}.\n"
            f"Single primary bottleneck: {bottleneck}.\nApply now: {action}\nVeto: {veto}\n{mechanics}"
        )
