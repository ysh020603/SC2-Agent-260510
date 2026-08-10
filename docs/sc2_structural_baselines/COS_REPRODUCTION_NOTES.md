# Chain-of-Summarization (CoS) Reproduction Notes

## Original structure

Temporal summarization pipeline: each frame/decision produces a short L1
summary; L2 commander decides using recent L1 history.

## Essential invariants

- L1 summarizes the current observation only (no queue, no prior L1 inputs).
- L1 history is match-scoped and truncated to K recent summaries.
- L2 uses recent L1s + frozen decision context to emit the final queue.
- Fixed two LLM calls per decision when both stages succeed.

## Discarded details

- TextStarCraft II environment / empty-action mixing / action_mix_rate.
- Separate OpenAI clients or embedding models.
- Protoss-only action dictionaries from the original project.

## SC2-Agent adaptation

- `COS_HISTORY_SIZE = 5`.
- Bot holds `CoSState` and resets on `on_start`.
- Invalid L1 → decision invalid, history unchanged.
- Invalid L2 → L1 already appended is kept; decision invalid.
- CLI mode: `cos`; traces: `cos_traces/`.
