# Agent 本地 python-sc2 运行时

本 Agent 是独立仓库，必须使用仓库内的 `python-sc2/` 快照，不依赖父目录，也不接受 conda/site-packages 中安装的其他 `sc2` 版本。

## 目录与来源

```text
SC2-Agent-260510/
├── python-sc2/              # Agent 自己版本化的固定快照
│   ├── sc2/
│   ├── LICENSE
│   └── VENDORED_FROM.md     # 来源版本记录
├── sc2_runtime.py           # 统一加载与兼容性检查
└── run_vs_ai.py
```

`sc2_runtime.ensure_bundled_python_sc2()` 完成三件事：

1. 基于 `sc2_runtime.py` 的绝对位置定位 `python-sc2/`，与当前工作目录无关。
2. 把本地快照放到 `sys.path[0]`，并拒绝此前已经从其他目录导入的 `sc2`。
3. 检查 Raven 等 15 条关键升级映射；快照缺失或不兼容时立即抛出明确异常。

正式入口、`SC2_Agent`、`sharpy`、`bot_loader` 和 `dummies` 包都会先执行该检查。不要在业务代码中重新添加相对路径，也不要把 `pip install burnysc2` 当作 Agent 的运行时来源。

`dummy_ladder_zip.py` 生成源码包时也会保留 `python-sc2/sc2/` 目录结构并包含 `sc2_runtime.py`，因此打包产物继续使用同一加载规则。

## 自检

Linux/macOS：

```bash
python -c "
from sc2_runtime import ensure_bundled_python_sc2
print(ensure_bundled_python_sc2())
"
```

Windows PowerShell：

```powershell
@'
from sc2_runtime import ensure_bundled_python_sc2
print(ensure_bundled_python_sc2())
'@ | python -
```

输出必须位于当前 Agent 仓库的 `python-sc2/sc2/__init__.py`。

## SC2 客户端启动约定

本地 `SC2Process` 会把“进程已创建”和“WebSocket 已就绪”区分为两个状态：

1. 启动等待期间每秒检查 SC2 客户端是否已经退出；
2. 客户端提前退出时立即报告返回码，不再固定空等三分钟；
3. 使用 `SC2_STARTUP_TIMEOUT` 限制 WebSocket 等待时间，默认 180 秒；
4. 清理时关闭连接、终止残留进程并归还 `portpicker` 端口。

批量测试应使用受支持的 sweep 入口。普通策略矩阵使用
`tools/run_kimi_nothink_strategy_sweep.py`；Human-Skill 正式 15 条件实验使用
`tools/run_human_skill_reference_topology.py`。二者必须错峰启动并自然等待单局
子进程，只重试无效任务。有效结果、match-local 清理和永久禁止全局
`wineserver -k` 的完整约束见
[`SC2_BATCH_EXPERIMENT_POLICY.md`](SC2_BATCH_EXPERIMENT_POLICY.md)。

## 更新规则

更新本地快照时：

1. 从经过验证的 `python-sc2` 版本同步完整目录，不复制 `.git`、`__pycache__` 或 `.pyc`。
2. 更新 `python-sc2/VENDORED_FROM.md` 的来源 tree/commit 和包版本。
3. 运行 `tools/tests/test_sc2_runtime.py`、完整 `tools/tests`，以及至少一局包含 Raven 研究的 BO 冒烟测试。
4. 不允许解析不到研究建筑时继续运行；`Tech` 必须立即报告具体 Upgrade 名称。
