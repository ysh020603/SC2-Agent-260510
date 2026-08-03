# Vendored Data V2.2 planning-agent V2 runtime

This package is the planning-oriented successor to
`SC2_Agent/knowledge_v2_2/`. It is selected with `data-v2.2-v2`; the existing
`data-v2.2` mode remains the V1 behavior and the naive agent remains unchanged.
It has no runtime import from the sibling `SC2_DATA_Agent` repository.

V2 adds a derived horizon resource snapshot, deterministic macro-task
decomposition, capability preflight queries, match-local static knowledge
caching, production-throughput estimates, crisis worker throttling, and an
executable final queue assembler. The assembler removes invalid/excess work,
adds required gas/production/supply capacity, and uses already legal race-native
units for spare throughput without replacing the MainAgent's strategy role. It
preserves the same public `{reason, ordered_names}` scheduler contract.

Public entry points:

```python
from SC2_Agent.knowledge_v2_2_v2 import (
    build_knowledge_decision_context,
    run_decision,
)
```

`build_knowledge_decision_context()` builds the decision-event and derived
planning snapshot from the strategy, structured observation, old uncommitted
queue, match-local ledger, automation context, and allowed canonical names.
`run_decision()` lets MainAgent finalize directly, reuse cached facts, or open
focused DataSubAgent sessions, and returns the public decision plus trace and
queue-audit metadata.
`provider` and `subagent_provider` independently select model-key/API profiles.

Prompts and static context are local to this directory. The complete copied
dataset is under `data_sc2_260701/`. See `UPSTREAM.md` and
`COPY_MANIFEST.json` for source revision and checksums, and
the V2 documentation for the integration contract and validation record.
