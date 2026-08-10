# 早期 Agent 验证归档（2026-07）

本目录保存朴素 Agent、V1 和早期知识模式完成回归验证时使用的指南、异常记录、矩阵
启动脚本与一次性分析脚本。它们已经完成历史任务，现按原样冻结，便于复查当时结论。

归档原则：

- 文件内容不再随当前 V2 架构更新；其中命令、路径和参数可能已经过时。
- `TESTING_GUIDE.md` 与 `ANOMALY_LOG.md` 的相对链接仍然有效。
- 旧脚本只用于复现实验考古，不是当前测试入口。
- 当前 V2 测试和 knowledge 消融分析从 [`../../README.md`](../../README.md) 进入。

归档包含：

- `TESTING_GUIDE.md`、`ANOMALY_LOG.md`
- `_run_15x3_matrix.py`、`_run_full_matrix.ps1`、`_run_full_matrix_concurrent.py`
- `_analyze_k15.py`、`_analyze_kn30.py`、`_dig_anomalies.py`

