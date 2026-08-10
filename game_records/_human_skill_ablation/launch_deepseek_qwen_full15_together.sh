#!/usr/bin/env bash
set -uo pipefail

repo=/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill
python=/home/wyq/miniconda3/envs/SC2_0615/bin/python
deep_prefix=human_skill_ablation_1200_medium_release_v6_20260809
deep_state="$repo/game_records/_human_skill_ablation/$deep_prefix"
qwen_prefix=human_skill_guarded_qwen32b_medium_1200_20260810
qwen_state="$repo/game_records/_human_skill_ablation/$qwen_prefix"
log="$repo/game_records/_human_skill_ablation/deepseek_qwen_full15_together.log"
deep_dev_log="$repo/game_records/_human_skill_ablation/release_v6_full_v2_dev6_recovered.log"
deep_log="$repo/game_records/_human_skill_ablation/release_v6_full_v2_all15_c15.log"
qwen_log="$repo/game_records/_human_skill_ablation/${qwen_prefix}_full_v2.log"
qwen_positive_log="$repo/game_records/_human_skill_ablation/${qwen_prefix}_positive_only.log"
qwen_probe="$repo/game_records/_human_skill_ablation/qwen3_32b_nonthinking_probe.json"

cd "$repo" || exit 1

"$python" API_Tools/probe_reasoning_extraction.py \
  --model-key qwen3-32b \
  --config-path ../API_config/config.json \
  --max-tokens 256 > "$qwen_probe"
probe_ok=$("$python" -c \
  'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); print(d.get("is_reasoning") is False and d.get("reasoning_length")==0 and not d.get("error"))' \
  "$qwen_probe")
if [[ "$probe_ok" != "True" ]]; then
  printf 'Qwen nonthinking probe failed; refusing cross-model launch at %s\n' "$(date -Is)" >> "$log"
  exit 3
fi

# Every formal runner is a child of this coordinator. The foreign-SC2 guard
# therefore trusts sibling DeepSeek/Qwen clients, while clients outside this
# exact process forest remain foreign and are never terminated by this job.
owner_pid=$$
common=(
  --phase all --difficulty medium --concurrency 15 --retry-concurrency 1
  --max-attempts 5 --retry-backoff 15 --game-time-limit 1200
  --wall-timeout 3000 --protocol-response-timeout 90 --ai-step-timeout 360
  --game-info-refresh-game-loops 0 --foreign-sc2-wait-timeout 21600
  --launch-stagger 3
)

printf 'launching Qwen Full15 immediately with recovered DeepSeek dev6 owner=%s at %s\n' \
  "$owner_pid" "$(date -Is)" >> "$log"

SC2_TRUSTED_OWNER_PID="$owner_pid" "$python" tools/run_human_skill_ablation_suite.py \
  "${common[@]}" --method full_v2 --indices 0-14 \
  --batch-prefix "$qwen_prefix" --manifest-name full_v2.json \
  --model qwen3-32b > "$qwen_log" 2>&1 &
qwen_pid=$!

SC2_TRUSTED_OWNER_PID="$owner_pid" "$python" tools/run_human_skill_ablation_suite.py \
  "${common[@]}" --method full_v2 --indices 5,6,7,12,13,14 \
  --batch-prefix "$deep_prefix" --manifest-name full_v2_dev6.json \
  --model DeepSeek-V4-flash > "$deep_dev_log" 2>&1 &
deep_dev_pid=$!

# The all-15 DeepSeek run may begin as soon as the six-condition gate is clean;
# it does not wait for Qwen. Completed dev conditions are skipped by artifact.
wait "$deep_dev_pid"
deep_dev_status=$?
printf 'DeepSeek dev6 exited status=%s at %s\n' "$deep_dev_status" "$(date -Is)" >> "$log"
deep_pid=0
if [[ "$deep_dev_status" == "0" ]]; then
  SC2_TRUSTED_OWNER_PID="$owner_pid" "$python" tools/run_human_skill_ablation_suite.py \
    "${common[@]}" --method full_v2 --indices 0-14 \
    --batch-prefix "$deep_prefix" --manifest-name full_v2_all15.json \
    --model DeepSeek-V4-flash > "$deep_log" 2>&1 &
  deep_pid=$!
else
  printf 'DeepSeek all15 not launched because dev6 was not clean\n' >> "$log"
fi

# Qwen Positive Only is paired on the same conditions and model, and starts as
# soon as Qwen Full finishes instead of waiting for any DeepSeek run.
wait "$qwen_pid"
qwen_status=$?
printf 'Qwen Full15 exited status=%s at %s\n' "$qwen_status" "$(date -Is)" >> "$log"
qwen_positive_pid=0
if [[ "$qwen_status" == "0" ]]; then
  SC2_TRUSTED_OWNER_PID="$owner_pid" "$python" tools/run_human_skill_ablation_suite.py \
    "${common[@]}" --method positive_only --indices 0-14 \
    --batch-prefix "$qwen_prefix" --manifest-name positive_only.json \
    --model qwen3-32b > "$qwen_positive_log" 2>&1 &
  qwen_positive_pid=$!
else
  printf 'Qwen Positive Only not launched because Qwen Full was not clean\n' >> "$log"
fi

deep_status=1
qwen_positive_status=1
if [[ "$deep_pid" != "0" ]]; then
  wait "$deep_pid"
  deep_status=$?
  printf 'DeepSeek Full15 exited status=%s at %s\n' "$deep_status" "$(date -Is)" >> "$log"
fi
if [[ "$qwen_positive_pid" != "0" ]]; then
  wait "$qwen_positive_pid"
  qwen_positive_status=$?
  printf 'Qwen Positive Only exited status=%s at %s\n' "$qwen_positive_status" "$(date -Is)" >> "$log"
fi

if [[ "$deep_status" == "0" && "$qwen_status" == "0" && "$qwen_positive_status" == "0" ]]; then
  "$python" tools/analyze_human_skill_ablation.py \
    --batch-prefix "$deep_prefix" --methods positive_only,full_v2 \
    --baseline positive_only --output "$deep_state/full_v2_deepseek_all15_report.json" > /dev/null
  "$python" tools/analyze_human_skill_ablation.py \
    --batch-prefix "$qwen_prefix" --methods positive_only,full_v2 \
    --baseline positive_only --output "$qwen_state/qwen_cross_model_report.json" > /dev/null
  printf 'cross-model reports generated at %s\n' "$(date -Is)" >> "$log"
  exit 0
fi
exit 1
