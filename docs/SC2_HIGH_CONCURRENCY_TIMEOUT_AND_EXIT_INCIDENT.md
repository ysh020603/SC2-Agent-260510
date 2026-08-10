# Human-Skill SC2 高并发响应超时与退出故障记录

## 文档状态

- 记录日期：2026-08-10
- 服务器：`172.18.30.162`
- Human-Skill 项目：`/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill`
- 稳定参考项目：`/data2/shy_2608/SC2-Agent-knowlegde`
- 当前分支：`codex/human-skill-agent`
- 当前结论：**部分修复，尚未完全关闭问题**

## 问题摘要

Human-Skill 项目进行原生 SC2 高并发完整对局时，部分对局会在
`observation` 请求上长时间收不到 SC2 响应。旧实现会在仍有 WebSocket
响应挂起时进入不完整的清理流程，出现以下现象：

1. 原生 `SC2_x64` 发生 SIGSEGV、退出，或长时间高 CPU 不退出；
2. Python 对局进程继续存活并消耗 CPU；
3. runner 一直等待子进程，批次无法自然结束；
4. 过去使用全局 `wineserver -k` 清理时还可能误伤同账户的其他项目对局。

当前代码已经消除了全局 Wine 清理，并能在协议超时现场精确回收该局的
原生 SC2；但是最新压力测试证明，部分 Python 对局进程在原生 SC2 被回收后
仍然不能自然退出。因此不能把当前状态描述为“完全修复”。

## 为什么参考项目能够自然退出

两个项目共享相同的基础 SC2/python-sc2 代码来源，但实际运行路径并不相同。

### 1. 正常终局路径和异常超时路径不同

参考项目中的正常对局会收到 SC2 引擎的终局响应：

`observation -> engine result -> on_end -> leave/quit -> context close -> process exit`

Human-Skill 的问题局走的是另一条路径：

`observation pending -> 120 秒超时 -> 强制回收该局 SC2 -> Python 异常收尾`

参考项目没有进入 Human-Skill 后来增加的这条“有响应挂起时超时清理”路径，
所以“共享基座”并不意味着两者执行了同一段退出代码。

### 2. 批量启动拓扑不同

参考项目当前稳定的总并发 15 实际为：

- 5 个独立 sweep runner；
- 每个 runner 管理 3 个 SC2 子进程；
- 子进程启动间隔 2 秒；
- 使用 `subprocess.run` 自然等待；
- 单局无效后由 runner 重试。

Human-Skill 先前使用一个 runner 同时管理 15 局，启动间隔也更短。总并发数
虽然相同，但调度、启动尖峰和故障隔离边界不同。

### 3. 对局负载不同

参考矩阵覆盖 Easy、Medium、MediumHard、Hard、Harder，并从 Easy 条件开始。
本次 Human-Skill 压力组的 15 局全部为 MediumHard，且同时运行 Full-v2 的
LLM/Skill 决策链。它更容易让多局同时进入长局、失败终局或高单位数量阶段。

### 4. 不是服务器 CPU/内存耗尽的单一解释

故障检查时服务器有 255 个逻辑 CPU、约 393 GiB 可用内存，系统 load
约 43。资源占用会增加响应延迟，但没有达到 CPU 或物理内存耗尽状态；同时
参考项目在同一服务器持续运行，说明本故障主要与 Human-Skill 的协议和退出
路径有关。

## 已完成的修改

相关提交：

- `579226e`：修复 pending SC2 response 清理崩溃；
- `a71fafc`：禁止从传输故障推断胜负；
- `8666e3b`：采用自然等待的 SC2 批量生命周期；
- `797e6ac`：修复共享 WebSocket 超时清理循环；
- `5e2436c`：限制终局 observation stall；
- `722e377`：在超时现场回收 SC2 与 Client 接收任务，并采用参考启动拓扑。

`722e377` 的主要变化：

1. 所有共享 WebSocket 的 `Protocol` 实例向 `SC2Process` 注册；
2. `observation` 超时后，不再等待外层 context 最终清理；
3. 立即精确 SIGKILL 该局所属的 `SC2_x64`，不触碰其他局；
4. 原生进程退出后取消并 await 该 Protocol 唯一的 receive task；
5. 关闭 aiohttp transport 前回收所有已注册 Protocol 的 pending receiver；
6. 默认单 runner 并发改为 3、启动间隔改为 2 秒；
7. 新增 `tools/run_human_skill_reference_topology.py`，以 5×3 方式提供总并发 15；
8. 永久保持 `SC2_ALLOW_GLOBAL_WINESERVER_KILL=0`。

## 测试结果

### 自动化测试

- 协议与进程清理定向测试：17 passed；
- `tools/tests`（排除已有无关 checksum 失败）：224 passed；
- Python compile 检查通过。

### Qwen3-32B 高并发压力测试

批次：

`human_skill_sc2_crashfix_reference_topology_qwen32b_20260810`

配置：

- 模型：`qwen3-32b`，non-thinking；
- 方法：`full_v2`；
- 难度：`MediumHard`；
- 条件数：15；
- 最大游戏时间：1200 秒；
- 拓扑：5 runner × 3，对局启动间隔 2 秒；
- 原始协调器 PGID：`201489`。

截至本次记录更新：

- 创建了 15 份 Human-Skill trace 产物，但这不等于 15 个干净有效结果；
- 6 个首轮日志出现 `SC2 protocol response timed out`；
- 6 个超时均执行了 `Aborting timed-out owned SC2 process immediately`；
- 未观察到 SIGSEGV/Segmentation fault；
- 超时对应的原生 SC2 能够被精确回收；
- 仍有部分 Python 对局进程在原生 SC2 退出后保持运行，说明异常传播/解释器收尾仍有缺口。

因此当前修复确认解决了“超时后原生 SC2 僵死或通过全局清理误伤其他实验”的
主要风险，但尚未解决“超时后 Python 子进程必须快速、确定地非零退出”的问题。

## 当前根因判断

已确认：

1. 问题首先表现为 SC2 对 `observation` 不返回，而不是 LLM API timeout；
2. 超时发生时 SC2 stderr 只包含正常启动和 `Sending ResponseJoinGame`，没有原生
   crash stack；
3. 精确 SIGKILL 后 SC2 return code 为 `-9`，没有 SIGSEGV；
4. Python 进程仍可能继续运行，且日志在记录 `SC2 client process exited` 后停止；
5. 残留 Python 仍持有 event loop socket、日志文件和 SC2 stderr 文件描述符。

待验证的下一级原因：

- `ProtocolResponseTimeoutError` 是否发生在 Bot/manager 的内部查询而不是主游戏循环；
- 是否有 broad `except Exception` 捕获传输终止异常后继续运行；
- `asyncio.run()` 是否在关闭默认 executor、后台 LLM 线程或 manager task 时等待；
- aiohttp session/websocket 是否仍有未注册的后台 task；
- 是否需要让传输终止异常继承专用 `BaseException`，避免被业务层 broad catch 吞掉；
- 是否需要由单局入口在捕获 transport-fatal 标记后执行确定的非零进程退出。

## 后续修复计划与验收标准

后续修改不得恢复全局 watchdog，不得调用全局 `wineserver -k`，也不得终止其他
项目的 SC2。推荐顺序：

1. 在单局入口、`_host_game`、`_play_game_ai` 和 manager 查询边界记录异常传播；
2. 将 protocol timeout/process exit 定义为不可被业务 manager 吞掉的 match-fatal；
3. 保证单局入口收到 match-fatal 后，关闭本局日志/recorder/session 并非零退出；
4. 对该退出路径增加集成测试，要求超时后 Python 进程在限定时间内退出；
5. 先跑 1 局故障注入，再跑 3 局并发，最后以 Qwen3-32B 运行 5×3、15 局完整压力测试。

最终验收必须同时满足：

- 15 个完整且干净的 Victory/Tie/Defeat；
- 0 SIGSEGV；
- 0 protocol response timeout；
- 0 SC2 process exit；
- 0 Python 残留子进程；
- 0 API error；
- 0 reasoning content；
- 0 对外部项目进程的信号或清理操作。

## 关键文件和日志

- 协议实现：`python-sc2/sc2/protocol.py`
- SC2 进程实现：`python-sc2/sc2/sc2process.py`
- 单 runner：`tools/run_human_skill_ablation_suite.py`
- 参考拓扑 wrapper：`tools/run_human_skill_reference_topology.py`
- 协议测试：`tools/tests/test_sc2_protocol_watchdog.py`
- 清理测试：`tools/tests/test_sc2_process_cleanup.py`
- 压力测试 manifest/log：
  `game_records/_human_skill_ablation/human_skill_sc2_crashfix_reference_topology_qwen32b_20260810/`
- 对局产物：
  `game_records/human_skill_sc2_crashfix_reference_topology_qwen32b_20260810_full_v2/`

