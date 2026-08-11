# Vendored V2.2 Origin

This package is a decision-oriented, repository-local copy of the SC2 Data Agent V2.2 implementation.

- Source repository: `C:\code\SC2_Agent_add_knowledge\SC2_DATA_Agent`
- Source commit: `dd981f58bdb7ab5b0828a3cd100f868fbdad71f7`
- Source commit subject: `Add V2.2 agent with session-local evidence references.`
- Dataset release: `data_sc2_260701`
- Dataset generated at: `2026-07-01T04:10:43.932155Z`

The copy is intentionally maintained inside the current `SC2-Agent-human-skill` repository. Runtime imports must never depend on the sibling source repository. Upstream V1, V2, V2.1, QA, Streamlit, logs, credentials, caches, and archived experiments are not part of this vendored boundary.

Local changes adapt absolute imports to package-relative imports, replace the question-answering MainAgent contract with a macro decision contract, add decision-specific prompts, route traces into match records, and apply Kimi rate limiting without modifying the naive decision caller.
