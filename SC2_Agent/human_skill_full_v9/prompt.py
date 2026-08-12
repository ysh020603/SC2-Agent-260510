V3_CONTRACT = """This Skill exposes a positive/default adaptive graph plus concise
mistake-to-correction lessons. Use a contrastive lesson only when its live-observation
conditions match. Treat the correction as strategic guidance, not a fixed build order,
and let current resources, queues, prerequisites, supply, threats, and Enemy Intelligence
override any mismatched lesson."""

V4_CONTRACT = """This Skill retains the positive/default adaptive graph and
contrastive lessons, and adds failure-aware execution guardrails. Apply the V4
execution checks before strategic guidance: rebuild a short prerequisite-ordered
queue from the live state, count pending supply, convert large banks into production
and army, maintain worker saturation without crowding out defense, and let current
threats override optional economy or technology. Matchup corrections remain
conditional guidance rather than a fixed build order."""

PROMPT_EXECUTABLE_SUFFIX = """
Translate the routed human-trajectory target into an executable current-state queue in
one response. Order missing prerequisites before dependent actions and do not repeat
already-completed structures merely because they appear in the trajectory. For Zerg,
secure a timely SpawningPool; when army is low, reserve Larva for immediately executable
combat instead of excessive Drones or Overlords. For Terran, when army is low and the
bank is large, order sufficient production before a long unit queue. Count current and
pending supply once. These are planning reminders, not runtime rejection rules: keep a
compact useful queue even when the position is imperfect."""


def contract_for_skill(skill_id: str) -> str:
    native = V4_CONTRACT if skill_id.startswith("T") or skill_id.startswith("PvP_") else V3_CONTRACT
    return native + PROMPT_EXECUTABLE_SUFFIX
