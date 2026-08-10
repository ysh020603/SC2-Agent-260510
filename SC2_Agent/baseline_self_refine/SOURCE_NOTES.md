# Source notes — Self-Refine

## Reproduced from

- Madaan et al., NeurIPS 2023 Self-Refine
- Author task structure: Init / Feedback / Iterate prompts
  (e.g. `src/acronym/{task_init,feedback,task_iterate}.py`)

## Not vendored

The upstream repository was not copied. The loop was reimplemented with
`API_Tools.llm_caller.call_openai_detailed`.

## SC2-specific adaptations

- `MAX_REFINE_ROUNDS = 2`
- Init uses the same domain boundary as naive
- Feedback dimensions limited to naive public policy
- No persistent memory across macro decisions
- Domain prompt copied from naive `decision_agent.py` then localized
