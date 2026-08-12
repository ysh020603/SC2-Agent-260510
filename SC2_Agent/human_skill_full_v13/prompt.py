PROCESS_CONTRACT = r"""
## Knowledge-Grounded General Process Contract

- Human-trajectory evidence supplies the node sign and broad direction. SC2 knowledge constrains feasibility and factual claims; it does not turn the candidate pool into a fixed build order.
- A POSITIVE node is a historically favorable direction, a DEFAULT node is a common continuation, and a NEGATIVE node describes a response to avoid or repair. Never execute a NEGATIVE node's failed direction as a recommendation.
- Select exact actions only after checking live Completed, Under Construction, Active Queues, resources, free supply, producers, and prerequisites.
- When the combined bank is at least 750 and army supply remains below 15 after 05:00, prioritize at least one currently executable combat candidate from the read node before optional expansion or deeper technology.
- If a preferred candidate cannot start before the next decision, use a cheaper currently producible candidate from the same trajectory envelope. Do not hide immediate army production behind a long blocked prerequisite chain.
- If the bank/low-army deficit persists for two decisions, treat repetition as a process failure: re-read the best matching node, identify the producer/resource/supply bottleneck, and change the reachable candidate or repair that bottleneck.
- Enemy Intelligence is partial and may be stale. Re-route when newly observed enemy properties, threat flags, losses, or live feasibility invalidate the current node.
""".strip()


def contract_for_skill(_: str) -> str:
    return PROCESS_CONTRACT
