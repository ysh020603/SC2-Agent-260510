# SC2 Dataset Overview

The active release contains Unit, Ability, Upgrade, and SubOntology records.

- Unit covers combat units, workers, structures, transformed forms, summons, and temporary entities.
- Ability covers construction, training, research, morphing, spawning, movement, and spell actions.
- Upgrade covers technologies, ability unlocks, and stat improvements.
- SubOntology contains canonical classes such as Workers, Spellcasters, GroundUnits, AirUnits, and race/class intersections.

The deterministic query layer can retrieve entity attributes, production and research links, requirements, technology dependencies, abilities, typed graph relations, ontology membership, and line-addressed Markdown evidence.

Entity keys are canonical and may differ from display names or user wording. Production and technology questions often require following Unit abilities to Ability targets and requirements. Typed semantic relations include counters, synergy, garrison compatibility, stat bonuses, ability unlocks, and morph enablers.

Structured records and typed relationships are authoritative for exact fields. Markdown evidence is useful for semantic descriptions and provenance. Absence of a Markdown page does not imply absence of a structured entity.

Common exact Unit and structure field keys include `name`, `race`, `minerals`, `gas`, `supply`, `time`, `max_health`, and `armor`. Use `minerals` and `gas`; do not invent keys such as `mineral_cost` or `gas_cost`. When several exact attributes are requested, fetch them together with `get_entity.keys`.
