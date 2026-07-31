# Environment setup

## Python

Python 3.11 is the established runtime. A minimal environment needs the SC2
protocol/runtime packages, OpenAI client, Sharpy dependencies, and pytest:

```bash
pip install s2clientprotocol mpyq portpicker openai requests aiohttp \
  numpy scipy scikit-learn opencv-python-headless more-itertools six \
  "protobuf==3.20.3" loguru pytest pytest-asyncio
```

The repository loads its bundled `python-sc2/` snapshot through
`sc2_runtime.py`; do not rely on a different site-packages `sc2`.
The existing Sharpy `bot_loader/` remains the common startup layer for both
the retained demo bots and `UniversalLLMBot`.

## StarCraft II

Set `SC2PATH` to the StarCraft II root and make sure the requested map exists.

Windows PowerShell example:

```powershell
$env:SC2PATH='C:\Program Files (x86)\StarCraft II'
Get-ChildItem "$env:SC2PATH\Maps" -Recurse -Filter '*Kairos*'
```

Linux example:

```bash
export SC2PATH=/data2/SC2/StarCraftII/
find "$SC2PATH/Maps" -iname '*Kairos*'
```

On Windows, do not inject a Linux `SC2PATH` into child processes. The sweep
runner leaves discovery to the registry/default installation. Concurrent batch
launches use a two-second gap by default to avoid initializing several clients
in the same instant.

SC2 websocket startup waits up to 180 seconds by default. Override it for a
known slow host with either the sweep option or the child environment:

```powershell
python tools\run_kimi_nothink_strategy_sweep.py `
  --startup-timeout 240 `
  --launch-stagger-seconds 3 `
  --dry-run

$env:SC2_STARTUP_TIMEOUT='240'
```

If SC2 exits before its websocket is available, the runtime reports the exit
code immediately. If the process remains alive but never publishes the
endpoint, it reports a bounded timeout that the sweep runner can retry.

## LLM configuration

Create `API_config/config.json` from the repository's expected config shape.
The file is ignored by Git. The supported runtime accepts one model key:

```json
{
  "llm_agents_pool": {
    "Kimi-k2.5": {
      "api_url": "http://host/v1",
      "api_key": "replace-locally",
      "model_name": "kimi-k2.5",
      "temperature": 1,
      "top_p": null,
      "max_tokens": null,
      "is_reasoning": false,
      "reasoning_extract_mode": "none",
      "non_reasoning_temperature": 0.6,
      "non_reasoning_extra_body": {
        "thinking": {"type": "disabled"},
        "chat_template_kwargs": {"thinking": false}
      }
    }
  }
}
```

Never commit or echo the real credential.

## Verify without a match

```powershell
python run_vs_ai.py --help
python run_custom.py --help
python tools\run_experiment.py --help
python tools\run_kimi_nothink_strategy_sweep.py --dry-run
python -m pytest tools\tests -q
```

## First match

```powershell
$env:SC2_GAME_TIME_LIMIT='240'
python tools\run_experiment.py `
  --strategy marine_rush `
  --decision-model Kimi-k2.5 `
  --decision-interval 60 `
  --enemy-race terran `
  --enemy-difficulty medium `
  --batch-name first_summary_queue_test
```

See [test-run-workflow.md](test-run-workflow.md) for record validation.
