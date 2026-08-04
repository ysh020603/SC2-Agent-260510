# Data V2.2 V2 no-knowledge control mode

## Experimental boundary

`data-v2.2-v2-no-knowledge` is an additive control for `data-v2.2-v2`. The
isolated variable is DataSubAgent retrieval.

Kept identical to V2:

- MainAgent class, MainAgent system prompt, decision-event construction, and
  preflight / mandatory-query question text;
- planning snapshot, deterministic queue assembly (`stabilize_queue_constraints`),
  queue audit, scheduler, and canonical action boundary;
- match-local answer cache keyed by query type and targets.

Changed only on the SubAgent side:

- SubAgent system prompt is adapted for direct answering (no tool catalog, no
  tool-selection protocol, no dataset/tool context files);
- each focused question gets exactly one non-thinking model call with no
  `tools` argument;
- sessions record `selected_tools: []`, `observations: []`,
  `answer_source: "model_prior"`, and `knowledge_database_access: false`;
- no `tool_request` / `tool_response` events can be emitted.

The deterministic V2 planner and auditor still read the repository dataset.
This mode therefore isolates SubAgent retrieval, not all code-side data use.
It is not equivalent to `naive`.

Implementation lives under
`SC2_Agent/knowledge_v2_2_v2_no_knowledge/`. It reuses the V2 MainAgent and
planner, owns the tool-free DataSubAgent and its prompt, and keeps a separate
planner state, answer ledger, and `kv2_no_knowledge_traces/` directory.

## SubAgent prompt contract

The control SubAgent prompt tells the model to answer MainAgent's focused
question from model knowledge under the same structured JSON reply contract
used by V2 (`answer`, `confidence`, `entities_mentioned`,
`candidate_entities`, `evidence_summary`, `limitations`). It must:

- follow the request's query type, targets, and fields;
- distinguish direct Air versus Ground attack for combat-capability questions;
- disclose uncertainty instead of inventing precision;
- never claim database or tool verification.

## Directed probes (current design)

After aligning MainAgent wording and switching SubAgent to the direct-answer
prompt, the three race resource/combat probes completed under
`game_records/prompt_probes/strict_no_knowledge_direct_answer_20260804_r2/`:

- Protoss and Zerg air-gap probes returned legal queues with zero remaining
  attack-layer shortfall and empty `selected_tools`;
- Terran ground-bank probe completed with only soft mineral/strength shortfalls
  (the same soft metrics allowed by V2);
- all probes reported `knowledge_database_access: false`.

## Earlier same-six-match DeepSeek batch

An earlier DeepSeek non-thinking six-match matrix used a previous control
revision and remains useful as historical evidence under
`game_records/v2_no_knowledge_ds4f_mh_3race_20260804_r3/` plus the PvT rerun
`..._r4/`. Accepted comparison set: 3W/3L, average RUR 1155.8, average bank
2152.6, APU 0.6435, versus knowledge V2's 2W/0L/4T. That batch predates the
final "same MainAgent wording + direct-answer SubAgent prompt" cleanup; a fresh
six-match matrix should be rerun when a same-revision comparison is required.

## Commands

```powershell
python tools\run_experiment.py `
  --decision-agent-mode data-v2.2-v2-no-knowledge `
  --decision-model DeepSeek-V4-flash `
  --data-subagent-model DeepSeek-V4-flash `
  --strategy lurkers `
  --bot-race zerg `
  --enemy-race terran `
  --enemy-difficulty mediumhard
```

```powershell
python tools\probe_v2_resource_combat_scenarios.py `
  --model-key DeepSeek-V4-flash `
  --decision-agent-mode data-v2.2-v2-no-knowledge
```

Control traces are stored under
`<match>/kv2_no_knowledge_traces/<date>/<trace-id>/trace.json`.
