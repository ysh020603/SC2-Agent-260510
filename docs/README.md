# 文档索引

这个目录存放比根目录 README 更细的项目说明。改代码、跑对局、复现实验或排查问题前，可以先按用途选择对应文档。

**测试与启动脚本不在 `docs/` 里。** 可复用的单局、批量、sweep 脚本统一放在 [`../tools/`](../tools/)；新建脚本测试结束后请归档到 `tools/`，需要复跑时在 `tools/` 中查找 `start_*.sh`、`run_*.py` 或 `run_*.sh`。归档规则见 [test-run-workflow.md](test-run-workflow.md)。

| 文档 | 可以用来做什么 |
|---|---|
| [environment-setup.md](environment-setup.md) | 搭建 Linux / Windows 环境，创建 `SC2_0615` conda 环境，配置 `SC2PATH`，安装依赖，并完成第一次冒烟对局。 |
| [python-sc2-runtime.md](python-sc2-runtime.md) | 理解 Agent 为什么只加载仓库内 `python-sc2`，以及如何自检和更新固定快照。 |
| [system-architecture.md](system-architecture.md) | 理解当前 LLM 宏观流水线、按对手种族加载策略 md、DATA_TOOLS 映射、`ExecutionScheduler`、BO list 模式和对局记录格式。 |
| [bot-inheritance.md](bot-inheritance.md) | 查看 `dummies/` 下 Bot 的继承关系、各类 Bot 的职责，以及 `UniversalLLMBot` 在 Sharpy 体系里的位置。 |
| [sharpy-overview.md](sharpy-overview.md) | 阅读 Sharpy 框架总览，了解 plans、managers、build orders 和通用 Bot 结构。 |
| [sharpy-modules-and-config.md](sharpy-modules-and-config.md) | 查询 Sharpy 模块职责和配置文件行为，适合修改 `config.ini`、manager 或 plan 前参考。 |
| [direct-build-executor-notes-20260617.md](direct-build-executor-notes-20260617.md) | 回顾 DirectBuild、资源预留、同类建筑多 PA、deferred 机制和 SCV target 处理经验。 |
| [test-run-workflow.md](test-run-workflow.md) | 查找测试命令、运行流程、实验复现线索和测试脚本归档规则，适合检查输出文件或复跑对局时使用。 |

本目录中的 `life-cycle.png`、`combat-micro-phases.png` 和 Sharpy `.pptx` 文件是 Sharpy 相关文档的辅助素材。
