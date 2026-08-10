# V2.3 Knowledge Routing

The Derived Planning Snapshot may contain `knowledge_opportunities`. They are
ranked, non-blocking opportunities, not commands. Ask the DataSubAgent only when
the returned repository packet can change the current executable queue.

Available query types:

- `enemy_counter`: composition-wide typed counters, direct target-layer coverage,
  current producer readiness, cost, arrival time, and strategy compatibility;
- `combat_capability`: authoritative direct weapon-layer coverage when the current
  army cannot engage an observed air or ground threat;
- `upgrade_path`: upgrades affecting several established main-army units, including
  researcher readiness, cost, prerequisites, effect, and converted time;
- `tech_feasibility`: production and prerequisite chain for a bounded expensive plan;
- `resource_facts`: bounded static facts only when the deterministic snapshot and
  queue audit do not already supply them.

Do not query merely to confirm a strategy-native unit already known to be directly
trainable and able to hit the observed layer. In survival mode, preserve an immediate
executable provisional force; knowledge may refine it but must never block production.

The knowledge layer exists to compensate for recurring LLM weaknesses, not to add
more strategy prose:

- LLMs confuse a semantic counter with a unit that can actually hit the target layer.
  Require direct weapon-layer evidence.
- LLMs omit morph sources, add-ons, earlier upgrade levels, and production capacity.
  Require an executable producer/prerequisite sequence.
- LLMs overreact to the strongest-sounding counter and ignore opportunity cost.
  Compare coverage, readiness, affordability, arrival time, and strategy compatibility.
- LLMs perform unreliable resource/supply arithmetic and propose more orders than
  current producers can execute. The deterministic snapshot and audit are authoritative.
- LLMs may let a retrieved fact overwrite a sound live-state plan. Knowledge may change
  the queue only when `decision_guidance.actionable` is true and the change improves
  feasibility or observed-layer coverage.

Read `decision_guidance`, `immediate_mobile_shortlist`,
`horizon_mobile_shortlist`, `coverage_ratio`, `producer_ready`,
`producer_reachable_in_horizon`, `missing_requirements`,
`affordable_in_horizon`, and `strategy_compatible` together. A theoretical counter
with unavailable production is not an immediate response. Prefer one candidate that
covers several observed enemy types over several narrow technology pivots. In normal
play, mobile combat units outrank static defense; static defense may lead only during
a real survival emergency.

After evidence arrives, preserve the pre-evidence queue unless a named fact changes a
specific item. Record that mapping in `knowledge_application`. If the answer merely
confirms the existing executable response, keep the queue and state the confirmation;
do not create a technology pivot to make the query appear useful.

Cached Static Knowledge is authoritative for static facts established successfully in
this match. An unavailable or limited reply is not permission to invent facts: keep the
safe live-state plan and state why knowledge was not used.
