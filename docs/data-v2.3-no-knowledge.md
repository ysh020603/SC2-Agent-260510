# Data V2.3 no-knowledge control mode

## Experimental boundary

`data-v2.3-no-knowledge` is an additive control for `data-v2.3`. The isolated
variable is DataSubAgent retrieval.

Kept identical to V2.3:

- MainAgent class, MainAgent system prompt, appended context files, and
  decision-event construction, including `knowledge_opportunities` and
  Cached Static Knowledge;
- planning snapshot, deterministic queue assembly (`stabilize_queue_constraints`),
  queue audit, scheduler, and canonical action boundary;
- match-local answer cache keyed by query type and targets.

Changed only on the SubAgent side:

- SubAgent system prompt answers from model knowledge with no tool catalog,
  portable router, or repository evidence packet;
- each focused question gets exactly one non-thinking model call with no
  `tools` argument;
- sessions record `selected_tools: []`, `observations: []`,
  `answer_source: "model_prior"`, and `knowledge_database_access: false`;
- no `knowledge_packet`, `tool_request`, or `tool_response` events can be
  emitted, so verified knowledge preferences cannot enter queue assembly.

The non-thinking constraint applies only to this control's DataSubAgent. Its
MainAgent follows the `decision_model` API profile. The deterministic V2.3
planner and auditor still read the repository dataset. This mode therefore
isolates SubAgent retrieval, not all code-side data use. It is not equivalent
to `naive`.

Implementation lives under `SC2_Agent/knowledge_v2_3_no_knowledge/`. It reuses
the V2.3 MainAgent, decision prompt, and planner; owns the tool-free
DataSubAgent and its prompt; and keeps a separate planner state, answer ledger,
and `kv2_3_no_knowledge_traces/` directory.

## Run

```powershell
python run_vs_ai.py `
  --decision-agent-mode data-v2.3-no-knowledge `
  --decision-model qwen3-32b `
  --data-subagent-model qwen3-32b `
  --force-strategy lurkers
```

Matrix sibling:

```bash
python tools/run_experiment_config.py \
  --config experiment_configs/local/matrix450_qwen_v23_noknowledge_20260806.json
```

Traces are stored at
`<match>/kv2_3_no_knowledge_traces/<date>/<trace-id>/trace.json`.
