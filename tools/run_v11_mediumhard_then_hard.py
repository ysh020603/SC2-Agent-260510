"""Run executable-normalized v11 if v10 misses the MediumHard target."""
import sys
import run_v10_mediumhard_then_hard as runner

runner.PREVIOUS_BATCH = "human_skill_deepseek_flash_nothinking_fullv10_60_mediumhard_20260811"
runner.MEDIUM_BATCH = "human_skill_deepseek_flash_nothinking_fullv11_60_mediumhard_20260811"
runner.HARD_BATCH = "human_skill_deepseek_flash_nothinking_fullv11_60_hard_20260811"
runner.METHOD = "full_v11"
runner.VERSION = "v11"
runner.PREVIOUS_PROCESS_FRAGMENT = "run_v10_mediumhard_then_hard.py"

if __name__ == "__main__":
    parser_value = sys.argv[sys.argv.index("--v10-pid") + 1]
    sys.argv = [sys.argv[0], "--v9-pid", parser_value]
    raise SystemExit(runner.main())
