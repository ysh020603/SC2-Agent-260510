# Human-Skill SC2 高并发响应超时与退出故障记录

## 文档状态

- 记录日期：2026-08-10
- 服务器：`172.18.30.162`
- Human-Skill 项目：`/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill`
- 稳定参考项目：`/data2/shy_2608/SC2-Agent-knowlegde`
- 当前分支：`codex/human-skill-agent`
- 当前结论：**Python 异常退出闭环已修复；Human-Skill bot 被误判为真人实时模式的根因已修复**

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

## 2026-08-10 match-fatal 退出闭环修复与复测

进一步活体排查确认，超时局不能退出的直接原因是异常层级设计错误：

- `ProtocolResponseTimeoutError` 原来继承 `ProtocolError -> Exception`；
- `SC2ProcessExitedError` 原来继承
  `ConnectionAlreadyClosedError -> ProtocolError -> Exception`；
- python-sc2 的 action/debug 兼容逻辑和上层 manager/bot 存在按设计处理普通
  `ProtocolError` 或 broad `Exception` 的恢复边界；
- SC2 被精确回收后，同一传输上已排队或后续发起的请求因此可能被业务层吞掉，
  Python 主循环持续对死亡客户端快速请求，表现为日志停止、主线程高 CPU、runner
  永久等待。

修复内容：

1. 新增不继承 `Exception` 的 `SC2MatchFatalError(BaseException)`；
2. protocol timeout 和 owned SC2 process exit 改为该 match-fatal 的子类；
3. 单局入口显式捕获 match-fatal，在本局 context 清理完成后以退出码 70 结束；
4. 增加 broad `except Exception` 不可吞掉 match-fatal，以及入口确定非零退出的测试。

定向与完整测试：

- match-fatal/协议/进程清理测试：20 passed；
- `tools/tests`：237 passed，1 个既有 vendored checksum 用例排除；
- Python compile 和 `git diff --check` 通过。

Qwen3-32B non-thinking 1200 秒复测批次：

`human_skill_sc2_matchfatal_qwen32b_nothinking_1200s_20260810`

- 配置仍为 5 runner × 3、MediumHard、`full_v2`、1200 游戏秒、最多 3 次；
- 共运行 30 个 attempts：首轮 15、第二轮 9、第三轮 6；
- 12 个条件得到干净引擎结果（9 Defeat、3 Tie）；
- 3 个条件连续三次遇到 SC2 4.10 终局 observation stall，最终被明确报告为
  terminal failure：`PvT_O07`、`TvZ_O01`、`ZvP_O06`；
- 18 次 protocol timeout 与 18 次 `FATAL_SC2_MATCH_TRANSPORT` 一一对应，
  每次均在原生 SC2 回收后立即结束 Python 单局进程并推进 retry；
- 批次结束后该 PGID 下 0 个残留进程；
- 0 SIGSEGV，0 API error，613 次 Qwen3-32B 调用中 0 reasoning；
- 协调器自然结束并明确返回 3 个失败 shard，没有再次永久挂起。

因此，本次修复关闭的是导致整批实验失败的“致命传输异常被吞掉、Python 子进程
不退出”问题。压力测试同时证明，旧版原生 SC2 在我方接近被消灭的终局阶段仍会
随机不返回 observation；该引擎问题不能伪造成 Victory/Defeat，当前正确处理方式是
精确回收、非零退出、有限重试并在耗尽后明确失败。

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

## 2026-08-10 终局 observation 根因收敛与协议绕过

### 已排除的假设

1. **不是 Qwen 返回慢导致 observation 超时。** 故障现场唯一 pending 的 SC2
   request 是 `observation`，Qwen HTTP 没有 pending；SC2 进程仍存活。
2. **不是服务器 CPU/内存耗尽。** 单并发重试仍可复现，同机资源也未耗尽。
3. **不是一次跨 4 个 game loop 导致。** 将整个失败条件 `PvT_O07` 改为
   `game_step=1` 后，仍在 0～1 人口的终局阶段稳定复现 observation timeout。
4. **不能通过第二个 WebSocket 旁路读取结果。** 原连接有 observation pending
   时，SC2 4.10 会直接断开第二个 WebSocket 握手。
5. **Ping 不能提前发布终局状态。** 在每个 step 后增加 Ping 时，Ping 仍返回
   `in_game`，随后的终局 observation 仍会卡死。

### 能确认到的原生故障边界

故障前最后一帧高度集中在我方被消灭阶段。顶层状态仍为 `in_game`；实时循环发出的
下一条带未来 `game_loop` 条件的 `RequestObservation` 被服务端接收，但没有任何响应字节。
现场线程状态显示 SC2 主线程和任务线程全部进入 futex wait，CivetWeb 线程停在
poll/eventfd；进程既未退出，也没有原生 crash stack。这把问题收窄为 Base75689
在等待目标帧与发布终局结果之间的内部状态同步问题。由于该二进制已 strip 且闭源，
无法在项目代码中修复其内部等待条件，只能避免把 bot 对局错误地送入该实时请求路径。

### 最终根因：bot 名称触发了真人模式的子串误判

继续核对调用分支后发现，所有 Human-Skill 实验实际都进入了 `realtime=True`：

```python
elif "human" in player1:
    args.real_time = True
```

机器人注册名为 `universal_llm_human_skill.<race>`，包含字符串 `human`，因此被误认为真人玩家。
这也解释了为什么非实时终局保护代码从未执行。

实时循环会发送带未来帧条件的 `RequestObservation(game_loop=last_loop + game_step)`。Base75689
若在到达目标帧之前进入终局，可能既不返回目标帧 observation，也不提前发布 `PlayerResult`，从而形成
永久 pending。非实时循环发送无目标帧的 `RequestObservation()`，不会等待一个终局后已不可达的未来帧。

修复后只在顶层 player key 严格等于 `human` 时启用真人模式：

```python
player_spec.split(".", 1)[0].strip().lower() == "human"
```

`universal_llm_human_skill.*` 因此恢复为命令行默认的 `realtime=False`。同时日志显式记录
`realtime`、player spec 和 human 判定，防止该配置再次静默漂移。

### 被否决的 replay probe

排查中曾尝试 `RequestSaveReplay + RequestReplayInfo` 读取终局结果，但活体实验推翻了它：SC2 对尚未结束的
临时 replay 也可能填充 Tie。它会把正在进行的对局误判为终局，不能作为权威终局信号。相关实现、环境变量
和测试已全部撤回；代码只接受正常 `ResponseObservation.player_result` 作为胜负依据。

协议 timeout、单局 SC2 精确回收、match-fatal 非零退出仍作为最后防线保留。

### 同步 Qwen HTTP 的独立上限

复测还发现一次与 SC2 无关的 Qwen HTTP 长读：OpenAI SDK 调用是同步函数，阻塞
event loop 时外层 `asyncio.wait_for(180s)` 不能及时取消。Human-Skill 默认调用现
显式传入 60 秒 SDK timeout，使 SDK 自身重试也保持有界，避免 API 长读伪装成整局
不退出。该限制不改变 `qwen3-32b` 的 non-thinking 配置。

### 最终 1200 秒验收

最终有效批次：

`human_skill_sc2_nonrealtime_final_qwen32b_nothinking_1200s_20260810`

配置为 Qwen3-32B non-thinking、`full_v2`、MediumHard、1200 游戏秒、5 runner × 3。
本批次未启用 replay probe，所有胜负都来自正常 SC2 observation：

- 15/15 启动日志为 `realtime=False`，三族各 5 局；
- 15/15 首轮完成，15 个 return code 均为 0，0 retry、0 failure；
- 结果为 14 Defeat、1 Tie；全部 15 份 artifact 完整；
- 0 protocol response timeout，其中 observation timeout 为 0；
- 0 match-fatal、0 SC2 unexpected exit、0 SIGSEGV；
- 0 API/AI-step timeout；15 份 LLM 日志共 339 次 Qwen3-32B 调用，
  `is_reasoning=true` 为 0，`reasoning_present=true` 为 0；
- 最慢单局墙钟 741.92 秒；协调器 5 个 shard 均返回 0，`failures=[]`；
- 验收进程组结束后无残留进程，也没有向外部项目进程发送信号。

自动化测试为 241 passed；另有 1 个本次修改前已存在、与该事故无关的 vendored dataset
checksum 用例失败。Python compile 与 `git diff --check` 均通过。

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
- 最终有效验收 manifest/log：
  `game_records/_human_skill_ablation/human_skill_sc2_nonrealtime_final_qwen32b_nothinking_1200s_20260810/`
- 最终有效验收对局产物：
  `game_records/human_skill_sc2_nonrealtime_final_qwen32b_nothinking_1200s_20260810_full_v2/`
