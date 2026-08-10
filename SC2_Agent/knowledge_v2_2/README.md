# Vendored Data V2.2 decision runtime

This package is the repository-local V2.2 MainAgent plus DataSubAgent runtime
used by the `data-v2.2` decision mode. It is maintained independently from the
naive `SC2_Agent/decision_agent.py` implementation and has no runtime import
from the sibling `SC2_DATA_Agent` repository.

Public entry points:

```python
from SC2_Agent.knowledge_v2_2 import (
    build_knowledge_decision_context,
    run_decision,
)
```

`build_knowledge_decision_context()` builds the decision-event message from
the strategy, observation, old uncommitted queue, automation context, and
allowed canonical names. `run_decision()` lets MainAgent either finalize
directly or open fresh DataSubAgent sessions when knowledge is useful, and
returns the public `{reason, ordered_names}` decision plus trace metadata.
`provider` and `subagent_provider` independently select model-key/API profiles.

Prompts and static context are local to this directory. The complete copied
dataset is under `data_sc2_260701/`. See `UPSTREAM.md` and
`COPY_MANIFEST.json` for source revision and checksums, and
`docs/data-v2.2-decision-agent.md` for the integration contract and validation
record.
