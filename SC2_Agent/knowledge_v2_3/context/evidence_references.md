# On-Demand Evidence Expansion

Opaque SHA-256 identifiers are intentionally hidden from model-visible tool results. When a relation or fact can be expanded, the result may contain a short session-local `evidence_ref` such as `R1` or `F1`.

- An `evidence_ref` is only a retrieval handle. It is not game evidence and must never appear in the SubAgent reply.
- Do not expand a reference merely because it exists. Most relation tools already return enough endpoint, description, source-kind, and fact-location information.
- Call `query_relation_evidence` with `evidence_ref` only when a required provenance detail is absent, a result was compacted or truncated before the needed evidence, or conflicting relation results require exact verification.
- Prefer the semantic fields already present. If they support the focused question, answer without another evidence call.
- References are valid only inside the current DataSubAgent session.
