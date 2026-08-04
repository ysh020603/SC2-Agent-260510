# Reasoning profile routing

## Single source of truth

For every normal model call, reasoning mode comes from the selected entry in
`API_config/config.json`:

```json
{
  "llm_agents_pool": {
    "qwen3-32b": {"is_reasoning": false},
    "qwen3-32b_think": {"is_reasoning": true}
  }
}
```

`decision_model` selects the MainAgent profile and `data_subagent_model`
selects the DataSubAgent profile. The launcher does not supply a second global
reasoning flag. Profile names such as `_think` are conventions only;
`is_reasoning` is authoritative.

V1 and V2 apply the selected role profile consistently to initial calls,
contract repairs, forced final decisions, tool selection, tool rounds, and
tool-limit summaries. MainAgent and DataSubAgent may therefore use independent
providers and independent reasoning modes.

The only intentional call-level override is the tool-free SubAgent in
`data-v2.2-v2-no-knowledge`. Its MainAgent follows the Main profile, while its
SubAgent always makes one non-reasoning call. If that SubAgent was configured
with a thinking profile and a matching non-thinking sibling exists, the runtime
resolves the call to that sibling and records both keys.

## Recorded identity

Logs distinguish configuration from execution:

| Field | Meaning |
|---|---|
| `configured_model_key` | profile requested by CLI/config |
| `model_key` | profile actually sent to the API caller |
| `profile_reasoning_mode` | `is_reasoning` read from the configured profile |
| `reasoning_override` | intentional per-call override, normally `null` |
| `reasoning_requested` | effective request mode after policy |
| `is_reasoning` | mode reported by the API call result |
| `reasoning_source` | where extracted reasoning was found |
| `raw_content` | raw provider content used to audit think tags |

The top-level `*.llm_calls.json` uses the resolved MainAgent `model_key` and
keeps the requested value under `configured_model_key`. Knowledge summaries
also list actual MainAgent and DataSubAgent model keys separately. Batch names
are never evidence of reasoning mode.

## Acceptance checks

A thinking experiment is valid only when all applicable role calls show:

- `configured_model_key` is the intended profile;
- `model_key` is not silently remapped to a non-thinking sibling;
- `profile_reasoning_mode`, `reasoning_requested`, and `is_reasoning` are true;
- provider reasoning is present when the provider/extraction mode exposes it,
  either as a reasoning field or think-tag content.

A non-thinking experiment must show false for the three mode fields, no
provider reasoning, and no think block in raw content. For no-knowledge mode,
apply the thinking checks to MainAgent and the non-thinking checks to its
SubAgent.

Do not classify an experiment from its batch name or configured key alone.
Any historical knowledge-mode batch whose trace reports
`reasoning_requested: false` is a non-thinking run even if its name contains
`think`; it cannot be used as a thinking ablation.
