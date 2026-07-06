"""Migrate valid BO-exec records and delete invalid match folders."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_bo_list_strategy_sweep import cleanup_invalid_batch_records


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-name", required=True)
    parser.add_argument(
        "--migrate-from",
        default="",
        help="Comma-separated older batch folders to import valid records from.",
    )
    parser.add_argument(
        "--remove-old-batch-dir",
        action="store_true",
        help="Delete the source batch directory after migration/cleanup.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    migrate_from = [name.strip() for name in args.migrate_from.split(",") if name.strip()]
    migrated, kept, deleted = cleanup_invalid_batch_records(
        args.batch_name,
        migrate_from=migrate_from,
    )
    print(
        f"batch={args.batch_name} migrated={migrated} kept={kept} deleted_invalid={deleted}"
    )

    if args.remove_old_batch_dir:
        for source_name in migrate_from:
            source_dir = ROOT / "game_records" / source_name
            if source_dir.is_dir():
                shutil.rmtree(source_dir)
                print(f"removed_old_batch_dir={source_name}")

            for suffix in ("_stdout.log", "_stderr.log"):
                log_path = ROOT / "game_records" / f"{source_name}{suffix}"
                if log_path.exists():
                    log_path.unlink()
                    print(f"removed_old_log={log_path.name}")

            batch_log_dir = ROOT / "game_records" / "_batch_logs" / source_name
            if batch_log_dir.is_dir():
                shutil.rmtree(batch_log_dir)
                print(f"removed_old_batch_logs={source_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
