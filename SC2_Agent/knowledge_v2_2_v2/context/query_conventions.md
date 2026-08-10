# Query Conventions

- Use `resolve_entity_key` when a name, alias, display label, or entity section is uncertain.
- Use `get_entity` for exact fields on one known canonical entity.
- For entity costs and durability, request the literal keys `minerals`, `gas`, `max_health`, and `armor`. The dataset does not use `mineral_cost` or `gas_cost` as Unit field keys.
- Use production and reverse-production tools for producer/output questions.
- Use research tools for structure-to-upgrade queries.
- Use ability tools for Unit-to-Ability fields and requirements.
- Use dependency or technology-tree tools for prerequisites and reverse impact.
- For "which Unit morphs into X", use `query_relations` with `entity_name=X`, `relation=morphs_into`, `direction=reverse`, and `endpoint_type=Unit`. The graph represents Zerg Larva production as a morph relationship as well as production. Follow the dataset relation literally even if ordinary gameplay wording would describe it as production.
- Use `query_morph_enablers` only for an Upgrade or structure that enables a morph. It is not the source-Unit lookup for "what morphs into X".
- Use typed relation tools for counters, synergy, garrison, stat bonuses, ability unlocks, and morph enablers.
- Use SubOntology tools for class membership.
- Use Markdown tools only when structured fields do not represent the requested semantic information or when exact source lines are requested.
- Before reporting a missing relationship or challenging the premise of a subquestion, verify the relation in both the required forward or reverse direction with `query_relations`.
- Game-loop time values must be converted to seconds only when the returned field is documented as game loops; use 22.4 loops per second.
