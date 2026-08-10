# V2 Knowledge Routing

Choose one query type before asking DataSubAgent:

- `resource_facts`: cost, supply, producer, requirements, or converted time for a bounded candidate set.
- `enemy_counter`: typed counter direction and feasible our-race production candidates for observed enemy entities.
- `combat_capability`: authoritative `Unit.weapons.target_type` facts and an explicit candidate-versus-enemy engagement matrix.
- `upgrade_path`: upgrades that affect the current main army, including effect, researcher, sequence, cost, and converted time.
- `tech_feasibility`: producer, add-on, morph direction, and prerequisite chain for an expensive or multi-step plan.

The subquestion must include canonical candidates, our race, relation direction when relevant, and requested fields. Do not send the complete observation. Do not ask DataSubAgent to choose the final macro queue.

Cached Static Knowledge is authoritative for facts already established in this match. Reuse it unless the cached reply reports low confidence or a limitation that matters now.

Use `combat_capability` before `enemy_counter` when the primary uncertainty is whether the current or proposed army can hit the enemy layer at all. A semantic counter edge cannot override a false weapon-layer result.
