# Entity-Expanded Semantic Relations

`entity_expanded_relations.json` is the canonical concrete semantic relation set for this release. It merges the original entity expansion with the deterministic pending-relation post-processing output.

## Counts

- Base entity relations: **4427**
- Post-processed pending relations: **104**
- Overlapping triples: **68**
- Unique merged triples: **4463**

| Relation | Count |
|---|---:|
| `counters` | 2217 |
| `enables_morph` | 20 |
| `garrisons_in` | 342 |
| `grants_stat_bonus` | 1353 |
| `synergizes_with` | 531 |

## Record Structure

Each record contains a stable relation ID, typed concrete endpoints, list-valued descriptions, a list of derivation sources, and a list of exact Markdown facts. No SubOntology remains as an endpoint in this file.

A duplicate triple is retained once. Its `source` list may contain direct Markdown extraction, SubOntology expansion, and pending post-processing entries at the same time. Facts identify the copied Markdown file, page Unit, race, heading path, exact one-based line range, block ID, and evidence text.

## Source Kinds

- `markdown_semantic_extraction`: directly extracted semantic assertion.
- `subontology_expansion`: concrete member edge generated from a class-level assertion.
- `pending_postprocess`: deterministic alias mapping, composite split, explicit-level mapping, or Level 1/2/3 project-policy expansion.

The generic-group rules from deferred Section 8 are not included.
