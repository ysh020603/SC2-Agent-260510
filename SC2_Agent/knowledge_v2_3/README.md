# DataAgent V2.3 portable knowledge runtime

`data-v2.3` is an additive successor to `data-v2.2-v2`. The older modes and
their prompts remain unchanged.

The defining boundary is provider-independent knowledge use:

1. MainAgent returns ordinary JSON text declaring either a final decision or a
   focused knowledge request.
2. `PortableKnowledgeRouter` selects and executes repository query functions
   locally. No OpenAI-style `tools`, `tool_choice`, function-call message, or
   provider-specific tool schema is sent to an API.
3. DataSubAgent receives the bounded evidence packet in an ordinary text
   completion and summarizes it. If that response is missing or malformed, the
   deterministic packet remains usable.
4. MainAgent receives the answer as ordinary text and produces the same public
   `{reason, ordered_names}` decision contract used by the existing bot.

V2.3 also adds composition-level counter coverage, producer/prerequisite and
horizon-affordability filters, completed-versus-reachable production state,
upgrade-beneficiary quality gates, knowledge opportunities derived from the
live observation, and an auditable path from actionable evidence to queue
insertions. Mixed threats are represented as separate air/ground response
shortlists, and a recovery state keeps the best executable queue even when a
destroyed economy makes an exact response-score target impossible this horizon.

Public entry points:

```python
from SC2_Agent.knowledge_v2_3 import (
    build_knowledge_decision_context,
    run_decision,
)
```

The code, prompts, context, query routing, and traces are maintained in this
directory. The immutable `data_sc2_260701` release is shared from the
repository-local `knowledge_v2_2_v2` copy to avoid duplicating a large dataset;
there is no runtime dependency on the sibling `SC2_DATA_Agent` repository.
