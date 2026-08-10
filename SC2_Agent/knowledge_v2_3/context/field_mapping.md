# Field Mapping and Units

Use literal dataset fields and do not convert units.

For Unit and structure entities:
- Mineral cost is `minerals`.
- Gas cost is `gas`.
- Maximum health is `max_health`.
- Armor is `armor`.
- Build time, if requested, is `time`.

For Upgrade entities:
- Mineral cost is `cost.minerals`.
- Gas cost is `cost.gas`.
- Research time is `cost.time`.

Do not use ability cooldown, ability cast range, in-game seconds, wiki seconds, or a converted real-time value as research time. If a keyed lookup such as `get_entity(..., keys=["research_time"])` returns no value, retry with the complete entity record and extract the nested `cost.time` value.

When returning final numeric values, copy the dataset value. Decimal forms such as `135.0` and integer forms such as `135` are numerically equivalent, but the entity name must remain exact.
