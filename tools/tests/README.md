# Tests

Run from the repository root:

```powershell
python -m pytest tools\tests -q
```

Decision-runtime coverage:

- `test_decision_agent.py`: prompt contract and JSON parsing;
- `test_decision_runtime.py`: triggers, uncommitted names, queue replacement,
  and deterministic producer choice;
- `test_strategy_summaries.py`: all strategy markdown files contain only
  `# Summary`.

The remaining tests cover data-tool costs/prerequisites, reasoning extraction,
and the bundled python-sc2 runtime.
