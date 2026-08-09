# Human Skill Runtime

The six `SC2_Agent/human_skill_*` packages pin one readable-skill method each.
They share only validated loading, match-scoped read memory, the two-message
JSON protocol, prompt scaffolding, non-reasoning model enforcement, and logs.

Runtime reads are restricted to `SKILL.md`, `index.json`, and validated
`nodes/*.md`; provenance is never exposed. A `read_skill` response updates
memory but cannot reach the scheduler. Only a valid final `decision` returned
to `UniversalLLMHumanSkillBot` can atomically replace the uncommitted queue.

Use `tools/probe_human_skill_agent.py` for one variant and scenario, or
`tools/probe_human_skill_ablation_matrix.py` for the same-condition six-way
matrix. Both default to the committed readable-skill fixtures and accept
`--live-llm` for `DeepSeek-V4-flash` non-reasoning API validation.
