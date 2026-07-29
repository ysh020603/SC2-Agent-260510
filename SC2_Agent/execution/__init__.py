"""命令式执行层。

* :mod:`mapping`         — DB 标准名 -> AbilityId/UnitTypeId/UpgradeId/sharpy Act
* :mod:`command`         — ``PlannedAction`` 数据结构与状态机
* :mod:`producer_selector` — deterministic producer discovery and selection
* :mod:`scheduler`       — ``ExecutionScheduler``（每帧驱动整条序列）
"""
