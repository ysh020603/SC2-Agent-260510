# V2.3 lineage and ownership

V2.3 was forked inside this repository from `SC2_Agent/knowledge_v2_2_v2`.
It is independently maintained and does not modify V1, V2, the no-knowledge
control, or the naive agent.

The original static data lineage remains:

- source repository at import time: none;
- original DataAgent source commit: `dd981f58bdb7ab5b0828a3cd100f868fbdad71f7`;
- dataset release: `data_sc2_260701`;
- generated at: `2026-07-01T04:10:43.932155Z`;
- repository-owned dataset path: `SC2_Agent/knowledge_v2_2_v2/data_sc2_260701`.

Only that immutable dataset is shared. V2.3 owns its runtime, prompts, context,
router, query-engine extensions, MainAgent/DataSubAgent behavior, and traces.
