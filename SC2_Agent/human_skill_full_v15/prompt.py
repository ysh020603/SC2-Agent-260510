PROCESS_CONTRACT = r"""
## Knowledge-Constrained Executable Process Contract

- The executable human-trajectory graph remains the strategic backbone. The knowledge overlay supplies factual prerequisites, costs, target-domain checks, candidate units, and repair conditions; it must not replace the trajectory direction with a generic counter table.
- Treat positive/default nodes as conditional directions. Treat negative nodes only as failures to avoid and conditions to repair, never as actions to reproduce.
- Select a short prerequisite-ordered queue from the live Completed, Under Construction, Active Queues, resources, supply, threats, and Enemy Intelligence.
- When resources accumulate faster than army production, prioritize reachable combat production before optional workers, expansions, upgrades, or deep technology. The runtime may deterministically front-load a supply-safe combat batch using the SC2 database.
- Repair the production mechanism, not only the unit list: use existing capacity for an immediate batch, add parallel buildable producers when throughput is insufficient, and replenish a shared renewable production resource through its database-derived supporting production path.
- Validate technology prerequisites and the observed enemy target domain before repeating a candidate. A queued unit that cannot start or cannot attack the confirmed target does not repair resource conversion.
- A single combat entry is not evidence that the conversion problem is repaired. At the next decision verify that the bank fell, active production increased, or army supply grew.
- If the same deficit persists, change the reachable candidate or repair the actual supply/producer/resource bottleneck. Do not repeat an unchanged posture.
- Re-route when new enemy properties, losses, threat flags, or feasibility evidence invalidate the current node. Enemy Intelligence is partial and may be stale.
""".strip()


def contract_for_skill(_: str) -> str:
    return PROCESS_CONTRACT
