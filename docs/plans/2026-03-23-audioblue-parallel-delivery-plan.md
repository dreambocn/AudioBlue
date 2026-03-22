# AudioBlue 三子代理并行开发执行计划（i18n + 真实设备 + 托盘/控制中心一致性）

## Summary
- 本轮采用 **主控代理 + 3 个子代理** 的并行模型，但不让子代理自由交叉改文件；通过 **冻结接口、隔离写入范围、分阶段合流** 来保证不会因为协作而引入“主界面打不开、托盘和控制中心状态不一致、假设备回流”这类严重问题。
- 当前仓库实际处于 `master`，且 `.worktrees/` **尚未被忽略**；因此正式开发前必须先做一次安全预处理：创建集成分支、把 `.worktrees/` 加入 `.gitignore`、再创建 3 个独立 worktree。任何实现都不能直接在 `master` 上开始。
- 三个子代理按功能域拆分：
  - **Agent A：后端配置/i18n/状态契约**
  - **Agent B：前端控制中心/i18n/真实设备展示**
  - **Agent C：桌面壳层/托盘行为/主界面实时同步**
- Quick Actions 不再是正式入口：**托盘左键固定为直接打开或激活 Control Center**；右键保留托盘菜单。托盘与控制中心必须共享同一个状态真源，并通过后端事件推送实现实时一致。

## Parallel Delivery Model
- **控制分支与 worktree**
  - 控制分支固定为 `codex/audio-blue-parallel-integration`。
  - 第一个提交只做安全基线：把 `.worktrees/` 加入 `.gitignore`，然后创建：
    - `codex/audio-blue-core-state-i18n`
    - `codex/audio-blue-control-center-i18n`
    - `codex/audio-blue-shell-sync`
  - 3 个子代理各自在自己的 worktree 开发，**不允许**直接改其他代理拥有的文件。
- **冻结接口，先定后做**
  - Python 共享快照固定包含：
    - `devices[]`：`deviceId`、`name`、`connectionState`、`capabilities.supportsAudioPlayback`、`lastSeenAt`、`lastConnectionAttempt`
    - `lastFailure`：`deviceId`、`state`、`code`
    - `settings.ui`：`theme`、`highContrast`、`language`
  - bridge 固定包含：
    - 现有命令接口
    - 新增 `set_language(language)`
    - 新增后端到前端的状态推送通道
  - 前端运行时固定包含：
    - `runtime.bridgeMode = 'native' | 'mock' | 'unavailable'`
    - 当前设备规则：只取**真实、已连接、支持音频**的设备；没有则显示本地化 `无` / `None`
- **合流规则**
  - 只允许主控代理合并，子代理只提交自己的分支。
  - 合流顺序固定：
    1. Agent A 先合并，建立配置、语言、状态契约
    2. Agent C 第二个合并，接上托盘/主界面共享状态与左键行为
    3. Agent B 最后合并，接入前端 i18n、bridge 推送、真实设备空状态
  - 每次合并后都要跑对应的聚焦测试；任何一个合流点失败都停止后续合并。

## Agent Task List
- **Task 0 — 主控代理安全预处理**
  - 新建 `codex/audio-blue-parallel-integration`，把 `.worktrees/` 加入 `.gitignore` 并单独提交。
  - 建立 3 个 worktree，并在集成分支记录本计划为执行基线。
  - 先跑基线验证：`pytest` 聚焦桌面/配置测试、`npm run test` 聚焦现有 bridge/UI 测试，记录现状后再分发。
- **Agent A — 后端配置、i18n、状态契约**
  - **写入范围**：`src/audio_blue/models.py`、`src/audio_blue/config.py`、`src/audio_blue/app_state.py`、新增 `src/audio_blue/localization.py`，以及对应 Python 测试文件。
  - **Task A1**：先写失败测试，给 `UiPreferences` 增加 `language: system | zh-CN | en-US`，确保旧配置兼容、新配置可持久化。
  - **Task A2**：先写失败测试，实现 Python 本地化层，覆盖托盘菜单文案、错误码到可读文案、通知文案；默认策略为 `system`，可解析到 `zh-CN` / `en-US`。
  - **Task A3**：先写失败测试，重构 `AppStateStore.snapshot()`：移除英文展示字符串作为真源，改为稳定 `state/code`、补齐 `lastSeenAt`、补齐 `settings.ui.language`。
  - **Task A4**：先写失败测试，给 `DesktopApi` 补 `set_language(language)`，所有设置变更都能回写共享快照。
  - **提交节奏**：A1/A2/A3/A4 各自一个 commit。
- **Agent C — 桌面壳层、托盘行为、状态同步**
  - **写入范围**：`src/audio_blue/desktop_host.py`、`src/audio_blue/tray_host.py`、`src/audio_blue/main.py`、新增 `src/audio_blue/session_state.py`（共享状态协调器），以及桌面/托盘相关 Python 测试、`README.md`。
  - **Task C1**：先写失败测试，新增 `session_state.py` 作为唯一状态协调器，统一承接 `ConnectorService` 事件、配置更新、托盘动作、`DesktopApi` 命令。
  - **Task C2**：先写失败测试，把 `ConnectorService.state_callback` 接入协调器；托盘菜单和 `DesktopApi.get_initial_state()` 都从协调器读同一份状态，而不是各自直接读散落对象。
  - **Task C3**：先写失败测试，托盘左键行为改为 `show_main_window()`，右键仍保留菜单；Quick Actions 从正式运行链路移除，`DesktopHost` 不再创建或展示 quick panel 窗口。
  - **Task C4**：先写失败测试，实现 Python → WebView 的状态推送：协调器状态变化后，`DesktopHost` 通过 `evaluate_js` 向已打开主窗口广播最新快照；Control Center 运行时不再只能靠手动刷新。
  - **Task C5**：先写失败测试，更新 `README.md`：托盘左/右键行为、状态同步模型、无 quick panel 的正式入口、开发调试方式。
  - **提交节奏**：C1/C2、C3、C4、C5 分 4 个 commit。
- **Agent B — 前端控制中心、i18n、真实设备展示**
  - **写入范围**：`ui/src/` 下的 `types`、`bridge`、`App.tsx`、`pages`、`components`、新增前端 i18n 目录与对应 Vitest 测试。
  - **Task B1**：先写失败测试，新增轻量 i18n provider/hook 与 `zh-CN` / `en-US` 消息表，支持 `system` 解析与手动切换。
  - **Task B2**：先写失败测试，收紧 `resolveBridge()`：只有 `import.meta.env.DEV && VITE_AUDIOBLUE_ENABLE_MOCK_BRIDGE === 'true'` 才允许 mock；其他无 bridge 情况返回 `unavailable bridge`，不能再显示假设备。
  - **Task B3**：先写失败测试，接入新 bridge 契约：支持 `setLanguage()`、接收 Python 推送快照、维护 `runtime.bridgeMode`。
  - **Task B4**：先写失败测试，统一真实设备规则：Overview、Devices、Automation、右侧状态区都只基于**真实且支持音频**的设备；没有当前设备时显示本地化 `无`；没有候选设备时显示空状态卡片。
  - **Task B5**：先写失败测试，从 `App.tsx` 移除 `#quick-panel` 正式路由，主程序只保留 Control Center 壳；所有按钮状态只从共享 bridge state 派生，不做本地伪真源。
  - **提交节奏**：B1、B2/B3、B4、B5 分 4 个 commit。

## Integration & Verification Gates
- **Gate 1 — 合并 Agent A 后**
  - 跑 Python 聚焦测试：配置兼容、语言映射、`AppStateStore` 快照契约。
  - 只有当 `language`、`state/code`、`lastSeenAt` 契约稳定后，Agent C 和 Agent B 的实现结果才允许合并。
- **Gate 2 — 合并 Agent C 后**
  - 跑桌面聚焦测试：托盘左键打开主界面、右键菜单仍可用、Quick Actions 不再进入正式路径、共享状态协调器能让托盘和 API 读取同一状态。
  - 做一次人工烟测：启动应用，左键打开 Control Center，关闭窗口后进程仍在托盘，右键菜单正常。
- **Gate 3 — 合并 Agent B 后**
  - 跑前端聚焦测试：i18n provider、bridge fallback、真实设备过滤、无已连接设备显示 `无`、无候选设备空状态。
  - 跑一次 `npm run build`，确保 Control Center 正常打包。
- **Final Gate — 全量验收**
  - 跑完整 `pytest`
  - 跑 `ui` 下完整 `npm run test`
  - 跑 `ui` 下 `npm run build`
  - 手工验收固定场景：
    - 托盘左键直接打开或激活 Control Center
    - 托盘右键连接/断开设备后，Control Center 状态即时一致
    - Control Center 连接/断开设备后，托盘菜单条目即时一致
    - 无真实支持音频设备时，不显示假设备，当前设备显示 `无`
    - 切换中文/英文后，托盘菜单与主界面保持同语言
    - 无 bridge 的生产运行下，只显示空状态或桥接不可用提示

## Assumptions
- 这次执行按 **主控代理 + 3 个子代理** 组织；主控代理负责接口冻结、分支/worktree、安全合流、回归验证，不把这些职责交给子代理。
- 为了降低风险，Quick Actions 本轮**退出正式交互链路**；相关源文件可以暂时保留，但运行时不再创建和显示该窗口。
- 默认语言策略固定为 `system`；前端和 Python 都只支持 `zh-CN` / `en-US`。
- 生产环境不允许任何 fake/mock 设备数据；mock bridge 仅限显式开发开关。
- 每个 task 都坚持 TDD：先失败测试，再最小实现，再聚焦验证，再本地 commit；任何代理若需触碰非自己写入范围，必须停止并由主控代理重新分派。
