# baseline_self_refine

Structure-only Self-Refine harness for SC2 macro decisions.

## Flow

1. Init (naive-equivalent candidate)
2. Feedback critic
3. Optional Refine (full replacement queue)
4. Repeat until critic satisfied or `MAX_REFINE_ROUNDS=2`

## CLI

```bash
python tools/run_experiment.py \
  --decision-agent-mode self-refine \
  --decision-model qwen3-32b \
  --strategy marine_rush \
  --bot-race terran \
  --enemy-race zerg
```

## Constraints

- No knowledge tools / DataSubAgent.
- No cross-decision reflection memory.
- Feedback cannot use external datasets or V2 auditors.
- Traces under `<match>/sr_traces/`.
