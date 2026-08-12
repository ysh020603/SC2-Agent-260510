import sys
import run_v10_mediumhard_then_hard as runner
runner.PREVIOUS_BATCH = "human_skill_deepseek_flash_nothinking_fullv11_60_mediumhard_20260811"
runner.MEDIUM_BATCH = "human_skill_deepseek_flash_nothinking_fullv12_60_mediumhard_20260811"
runner.HARD_BATCH = "human_skill_deepseek_flash_nothinking_fullv12_60_hard_20260811"
runner.METHOD = "full_v12"; runner.VERSION = "v12"; runner.PREVIOUS_PROCESS_FRAGMENT = "run_v11_mediumhard_then_hard.py"
if __name__ == "__main__":
    value = sys.argv[sys.argv.index("--v11-pid") + 1]; sys.argv = [sys.argv[0], "--v9-pid", value]
    raise SystemExit(runner.main())
