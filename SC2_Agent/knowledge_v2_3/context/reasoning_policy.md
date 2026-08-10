# V2.3 Macro Decision Reasoning Policy

Use deterministic evidence as the source of truth for static StarCraft II facts and the current observation as the source of truth for the live match.

Do not collapse different graph roles into one concept:

- A direct producer trains, builds, morphs, researches, or otherwise creates another entity.
- A prerequisite or requirement must exist before an action is available.
- A tech-chain node may be part of a path without being the direct producer.
- An ability result is produced by executing an ability.
- A morph source and morph result are directional; in `A morphs_into B`, A is the source and B is the result.
- An alias or variant may share statistics with a normal form while remaining a different canonical endpoint.

When a DataSubAgent reply contains several candidates, check whether the focused subquestion selects one role. If it does not, ask one narrower follow-up only when the distinction can materially change the current macro queue.

Do not turn every observed entity into a data investigation. Query facts that can change prerequisite ordering, production feasibility, composition choice, upgrades, or a near-term counter response. Then combine those facts with resources, supply, committed work, strategy, and timing.

Near the round limit, produce the best valid macro decision supported by the observation and gathered evidence. Never output a failure message as an ordered_names entry.
