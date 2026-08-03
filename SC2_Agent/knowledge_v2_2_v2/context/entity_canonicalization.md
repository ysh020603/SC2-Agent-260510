# Entity Canonicalization and Variants

Canonical entity names are exact dataset identifiers. Copy them verbatim.

When the complete entity record provides variant or alias fields, report them in the candidate information:
- `normal_mode_name`
- `unit_alias_name`
- `tech_alias_names`
- `is_flying`
- `is_structure`
- burrowed, flying, hallucinated, temporary, or special-mode indicators when present in the name or fields

Do not silently replace a variant with a normal form or a normal form with a variant. If both are plausible, return both and explain the difference. The final answer may prefer the normal form only when the question asks for the mature, normal, grounded, canonical, or non-variant endpoint, or when the evidence explicitly links the variant to that normal form.

If two candidates share the same costs and statistics, the exact endpoint name still matters. Keep endpoint-name evidence separate from attribute evidence.
