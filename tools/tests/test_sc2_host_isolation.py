import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "human_skill_suite_host_isolation",
    ROOT / "tools/run_human_skill_ablation_suite.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _proc(proc_root: Path, pid: int, ppid: int, command: bytes) -> None:
    proc_dir = proc_root / str(pid)
    proc_dir.mkdir()
    (proc_dir / "stat").write_text(
        f"{pid} (worker name) S {ppid} 0 0 0 0\n", encoding="utf-8"
    )
    (proc_dir / "cmdline").write_bytes(command.replace(b" ", b"\0") + b"\0")


def test_process_tree_and_native_sc2_detection(tmp_path: Path) -> None:
    _proc(tmp_path, 10, 1, b"python runner.py")
    _proc(tmp_path, 11, 10, b"python match.py")
    _proc(tmp_path, 12, 11, b"/data2/SC2/SC2_x64 -listen")
    _proc(tmp_path, 20, 1, b"/data2/SC2/SC2_x64 -listen")
    _proc(tmp_path, 30, 1, b"bash mentions_SC2_x64")

    assert MODULE._process_tree(10, tmp_path) == {10, 11, 12}
    assert MODULE._sc2_process_pids(tmp_path) == {12, 20}
    assert MODULE._sc2_process_pids(tmp_path) - MODULE._process_tree(10, tmp_path) == {20}
