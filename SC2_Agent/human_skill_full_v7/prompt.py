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


def contract_for_skill(skill_id: str) -> str:
    return V4_CONTRACT if skill_id.startswith("T") or skill_id.startswith("PvP_") else V3_CONTRACT
