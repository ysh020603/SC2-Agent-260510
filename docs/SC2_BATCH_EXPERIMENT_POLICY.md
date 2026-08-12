# SC2 批量实验启动与结果计数规范

本文档是仓库内原生 SC2 批量实验的唯一现行规范。其他 README、事故记录和历史
测试报告只提供背景；如有冲突，以本文档和当前代码为准。

## 1. 不可变约束

1. **只使用仓库内置 python-sc2。** 所有入口必须先通过
   `sc2_runtime.ensure_bundled_python_sc2()`，解析到当前仓库的
   `python-sc2/sc2/__init__.py`。禁止混用父目录、conda 或 site-packages 中的
   其他 `sc2` 实现。
2. **错峰启动。** 正式并发实验不得同时瞬时拉起所有客户端。Human-Skill 的标准
   30 局评估拓扑是 10 个隔离 runner × 每个 3 局，runner 和子局均采用 2 秒级
   错峰。每个方法固定运行 15 条件 × 2 重复；不得把单个 runner 的并发直接改为 30。
3. **自然等待子进程。** runner 使用 `subprocess.run` 等待每个单局自然返回，不得
   用外层 wall-clock watchdog、轮询 killpg 或周期性全局清理代替正常生命周期。
4. **只计干净、可解析结果。** 只有引擎明确报告的 `Victory`、`Tie`、`Defeat`
   才能计入样本；目录存在、trace 部分写入或进程返回 0 都不能单独证明有效。
5. **失败任务单独重试。** 首轮完成项不得重跑或重复计数。无效项进入有限重试，
   推荐 `retry_concurrency=1`；达到 `max_attempts` 后必须报告 terminal failure。
6. **永久禁止全局 `wineserver -k`。** `SC2_ALLOW_GLOBAL_WINESERVER_KILL` 必须为
   `0` 或未设置。只允许回收当前 match 明确拥有的 `SC2_x64`，不得按进程名、用户
   或 Wine server 清理，也不得向其他项目的进程发送信号。

## 2. 支持的启动入口

普通策略矩阵使用：

```bash
python tools/run_kimi_nothink_strategy_sweep.py --dry-run
```

Human-Skill 的标准 30 局正式实验使用：

```bash
python tools/run_human_skill_reference_topology.py \
  --phase all \
  --model DeepSeek-V4-flash \
  --batch-prefix <unique-batch-name> \
  --difficulty mediumhard \
  --game-time-limit 1200
```

正式启动前先对同一命令追加 `--dry-run`，确认 10 个 shard、总并发 30、每方法
30 局及精确命令。该 wrapper 固定拆分为 10 个 shard，每个 shard
`concurrency=3`、`retry_concurrency=1`、`launch_stagger=2.0`。`--phase all`
运行已注册的消融组和 full/full_v2/full_v3；单方法可改用 `--method <name>`。
单局诊断可以直接使用
`tools/run_experiment.py` 或 `run_vs_ai_human_skill.py`，但不得把临时 shell 循环
当作正式实验记录。

## 3. 有效样本判定

一个正式样本必须同时满足：

- `match.json` 可解析，`metadata.result` 属于 `Victory/Tie/Defeat`；
- 方法要求的 trace、skill-read 和 LLM call 文件均可解析；
- 无 protocol watchdog/timeout recovery、SC2 unexpected exit、AI-step timeout、
  foreign overlap 或 process-disappeared 标记；
- 无 API error；non-thinking 实验中 `is_reasoning=false` 且无 reasoning content；
- 方法、模型、Skill ID、难度、地图、种族、run index 与 manifest 一致。

`tools/run_human_skill_ablation_suite.py` 的 `completed_skill_ids()` 和
`record_has_watchdog()` 是 Human-Skill 当前的机器判定边界。统计脚本不得绕过该
边界直接按目录数、日志数或进程退出码计数。

## 4. 重试与退出语义

- protocol timeout/process exit 是 match-fatal，不得被业务层 `except Exception`
  吞掉；单局以明确非零退出码返回 runner；
- runner 只重试未产生干净 artifact 的条件，并记录每次 attempt；
- retry 不得覆盖首轮日志；manifest 必须保留 attempt、return code、artifact
  validity 和最终 failure count；
- 不得把 transport failure 推断成 Victory、Tie 或 Defeat；
- runner 结束后应不存在属于该批次的残留 Python 或 SC2 进程。

## 5. 启动前与结束后检查

启动前：记录 Git commit、配置 hash、模型/non-thinking 门禁；用 `--dry-run`
核对条件、唯一 batch name、总并发和 API 负载；确认 python-sc2 路径、
`SC2PATH`、地图和启动 timeout；识别同机实验但不得终止或修改它们。

结束后：按 manifest 核对条件数、干净结果、attempt 和 terminal failure；单列
胜平负、重试、timeout、process exit、API/reasoning error；检查批次进程树自然
清空；只有满足预注册有效样本数时才进行胜率和配对显著性分析。

## 6. 相关记录

- 当前根因与最终修复：
  [`SC2_OBSERVATION_NOT_RETURNING_ROOT_CAUSE_AND_FIX.md`](SC2_OBSERVATION_NOT_RETURNING_ROOT_CAUSE_AND_FIX.md)
- 完整历史排障时间线：
  [`archive/SC2_HIGH_CONCURRENCY_TIMEOUT_AND_EXIT_INCIDENT.md`](archive/SC2_HIGH_CONCURRENCY_TIMEOUT_AND_EXIT_INCIDENT.md)
- 环境：[`environment-setup.md`](environment-setup.md)
- 批量工作流：[`test-run-workflow.md`](test-run-workflow.md)
- 配置与 manifest：[`experiment-configuration.md`](experiment-configuration.md)
