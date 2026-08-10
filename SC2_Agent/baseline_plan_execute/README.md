# baseline_plan_execute

Structure-only Plan-and-Execute harness for SC2 macro decisions.

## Flow

1. Capture frozen decision context (shared with naive domain prompt).
2. Planner once → 1–4 semantic steps.
3. Sequential Executor calls; each sees previous fragments.
4. Deterministic concatenate → public `{reason, ordered_names}`.

## CLI

```bash
python tools/run_experiment.py \
  --decision-agent-mode plan-execute \
  --decision-model qwen3-32b \
  --strategy marine_rush \
  --bot-race terran \
  --enemy-race zerg
```

## Constraints

- No knowledge tools / DataSubAgent.
- No intra-decision replanning.
- Aggregate queue > 20 names → invalid decision.
- Traces under `<match>/pe_traces/`.
