# Graph Traversal Policy

Choose tool routes based on the relation phrase in the question.

For production phrases such as "produces", "trained from", "built by", "creates", or "is made at":
- Query direct production outputs from the candidate producer.
- Query reverse production sources for the candidate product.
- Include requirements and tech-chain evidence when available.
- Keep direct producer, required structure, and tech-chain node as separate candidate roles.

For prerequisite phrases such as "required for", "prerequisite structure", or "through its requirement":
- Query tech-tree and dependency evidence.
- Verify whether the question asks for the required entity itself or an entity produced through that required entity.

For morph or transform phrases:
- Query `morphs_into` in the direction stated by the question.
- Also verify the reverse direction when the user names the result and asks what becomes it.
- Do not reverse the relation unless the deterministic result supports that reversal.
- For source units such as production larvae or morph-capable units, `query_production_outputs` can contain morph ability outputs that are not visible in a direct relation-only candidate list. Use production outputs as the complete candidate-discovery source, then use relations for direction and verification.

For ability-result phrases such as "spawns", "creates", "summons", "hallucinates", or "results in":
- Query unit abilities for the source unit.
- Query typed relations such as `action_result` in forward and reverse directions when needed.
- If an ability produces a temporary, flying, burrowed, or alternate-mode variant, also inspect that variant's normal mode and alias fields before selecting the final endpoint.
- Do not treat ordinary morphs such as `Overlord morphs_into Overseer` as a spawn unless the question explicitly allows morph/transform outputs. If the question says "spawned by", prefer `spawns` relations or ability targets whose action semantics are spawn/create/summon.

For research and upgrade phrases:
- Query research outputs for the researcher.
- Query upgrade effects, stat bonuses, and ability unlocks in both useful directions.
- If several upgrades at the same researcher affect different units, compare all upgrades before choosing an endpoint. Do not choose the first upgrade returned by the data.

For large production-output lists:
- If a tool result reports a count larger than the visible or summarized result list, ask for a compact list of produced canonical names or use another query that can return only names.
- Prefer complete candidate coverage over rich per-candidate detail during candidate discovery. Fetch detailed fields only after the endpoint candidate is selected or when ambiguity requires field comparison.
