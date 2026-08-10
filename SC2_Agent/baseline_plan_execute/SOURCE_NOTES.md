# Source notes — Plan-and-Execute

## Reproduced from

- LangChain Plan-and-Execute Agents (2023): Planner → sequential Executor;
  classic initial version plans once.
- Plan-and-Solve (Wang et al., 2023): planning-before-solving / subtask split
  as conceptual confirmation only.

## Not vendored

Third-party repositories were not copied into this tree. The harness was
reimplemented against `API_Tools.llm_caller.call_openai_detailed`.

## SC2-specific adaptations (not paper requirements)

- Max 4 planner steps.
- Executor emits canonical name fragments instead of tool actions.
- No Finalizer LLM; concatenate fragments.
- Queue length hard fail at >20.
- Frozen observation for the whole decision.
- Domain prompt copied from naive `decision_agent.py` then localized.
