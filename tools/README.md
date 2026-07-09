# 测试与运行工具目录

`tools/` 是本仓库可复用测试、运行、回归和结果检查脚本的统一归档位置。测试完成后，需要复跑或支撑正式测试结论的脚本应整理到这里，不要散落在仓库根目录、`docs/`、`game_records/` 或系统临时目录。

**查找入口**：需要启动对局、批量 sweep 或复现实验时，优先在本目录搜索 `start_*.sh`（tmux 批量包装）、`run_*.py`（Python 入口）和 `run_*.sh`（Shell 批量引擎）。

## 目录约定

```text
tools/
├── start_*.sh                # 预设参数的 sweep / 批量 tmux 启动器
├── run_vs_ai_batch.sh        # 通用批量并发引擎（调用根目录 run_vs_ai.py）
├── start_experiments.sh      # 预设环境变量 + 调用 run_vs_ai_batch.sh
├── run_*.py / run_*.sh       # 单局、批量和实验入口
├── check_*.py / verify_*.py  # 结果检查与回归验证
├── tests/                    # 不启动 SC2 的 pytest 测试
└── archive/                  # 已废弃、仅供历史追溯的 launcher
```

- 新实验优先复用 `run_experiment.py` 或现有批量入口。
- 只有确实具有独立用途的脚本才新增到 `tools/`，避免为每次参数变化复制一个 launcher。
- `tools/archive/` 中的脚本可能包含过期参数或旧路径，不应作为新测试入口。
- 对局产物统一写入 `game_records/`，不应提交到本目录。

## 新增或归档脚本要求

1. 使用 `Path(__file__).resolve()` 定位仓库，不依赖当前工作目录。
2. 将策略、地图、模型、对手、批次名、并发数和时限参数化。
3. 默认保留已有结果，除非用户明确要求，否则不得清理或覆盖历史批次。
4. 不写入 API 密钥、Token、个人凭据或机器专用绝对路径。
5. 文件头写明用途、示例、输出目录，以及是否启动 SC2 或访问模型 API。
6. 移入本目录后运行 `--help`、dry-run 或相应测试，验证路径和导入仍然有效。

## 测试交付检查

测试结束并汇报前确认：

- 临时 launcher 和检查脚本已经归档到正确目录。
- 最终复现命令引用 `tools/` 中的正式脚本，而不是 `/tmp` 文件或终端历史。
- 结果目录、模型名、地图、策略、对手和时限已经记录。
- 日志中已检查退出码、Traceback、关键动作和轨迹文件完整性。

完整运行流程见 [`../docs/test-run-workflow.md`](../docs/test-run-workflow.md)。
