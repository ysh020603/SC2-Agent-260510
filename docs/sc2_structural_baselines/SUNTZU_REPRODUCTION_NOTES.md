# SunTzu Reproduction Notes

## Original structure

SC2 LLM agents with hierarchical planning and dual verification:
Planner → Plan Verifier (optional refine) → Executor → deterministic/retry checks.

## Essential invariants

- Separate semantic planning from executable queue generation.
- LLM verifies the plan before execution.
- Bounded plan-refine and executor-retry loops.
- Final public output is a macro queue, not low-level unit actions.

## Discarded details

- Original SunTzu specialized models / LLMClient.
- Unit-id / coordinate / ability-level action generation.
- Map-dependent low-level control stacks.

## SC2-Agent adaptation

- All roles use `decision_model_key` via `call_openai_detailed`.
- Planner emits semantic `commands` (1–5), not canonical queues.
- Executor emits full `{reason, ordered_names}` replacement queue.
- `verify_macro_queue` checks only interface-level validity (names, length, types).
- Frozen observation for the whole decision; no knowledge tools.
- CLI mode: `suntzu`; traces: `suntzu_traces/`.
