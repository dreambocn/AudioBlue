# AudioBlue Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复本轮代码审查中确认的 5 个风险点，避免自动连接规则被误清、桥接初始化卡死、历史在线状态误判、历史查询退化和原生主题重复同步。

**Architecture:** 前端侧优先在 `ui/src/bridge/index.ts` 和 `ui/src/state/useControlCenterModel.ts` 收敛桥接契约与状态副作用；后端侧只优化 `SQLiteStorage.list_device_history()` 的 SQL 聚合和索引，不改变外部返回 shape。每个修复都先补回归测试，再做最小实现。

**Tech Stack:** Windows + PowerShell Core、React 19、TypeScript、Vitest、Python 3.12、pytest、SQLite。

---

## File Structure

- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\bridge\index.ts`
  - 修复 `toPythonRulePatch()` 对 `mode` 的隐式 startup 清零。
  - 修复历史设备 `isCurrentlyVisible` 的来源集合。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\bridge\index.test.ts`
  - 增加 bridge rule patch 和历史可见性回归测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\state\useControlCenterModel.ts`
  - 增加初始快照失败兜底。
  - 收窄原生主题同步 effect 的依赖。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\App.integration.test.tsx`
  - 增加初始化失败不再永久 Loading 的 UI 测试。
  - 增加主题同步不随普通状态事件重复触发的 UI 测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\storage.py`
  - 增加查询索引。
  - 将历史聚合下推到 SQLite。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_storage.py`
  - 增加 `limit` 生效与 presence 汇总的回归测试。

---

### Task 1: 保留启动自动连接规则

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\bridge\index.ts:377-407`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\bridge\index.test.ts`

- [ ] **Step 1: Write the failing bridge test**

Add this test under `describe('resolveBridge', () => { ... })` in `ui/src/bridge/index.test.ts`:

```ts
  it('keeps startup auto-connect untouched when toggling reappear rule', async () => {
    const updateDeviceRule = vi.fn(async () => ({
      devices: [],
      deviceRules: {
        'device-1': {
          auto_connect_on_startup: true,
          auto_connect_on_reappear: true,
        },
      },
      settings: {
        notification: { policy: 'failures' },
        startup: { reconnectOnNextStart: false },
        ui: { theme: 'system', language: 'system' },
      },
    }))
    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => ({})),
        update_device_rule: updateDeviceRule,
      },
    } as typeof window.pywebview

    const bridge = resolveBridge()

    await bridge.updateDeviceRule('device-1', {
      autoConnectOnAppear: true,
      mode: 'appear',
    })

    expect(updateDeviceRule).toHaveBeenCalledWith('device-1', {
      auto_connect_on_reappear: true,
    })
  })
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run from `E:\Development\Project\PythonProjects\AudioBlue\ui`:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\bridge\index.test.ts
```

Expected: the new test fails because the payload still contains `auto_connect_on_startup: false`.

- [ ] **Step 3: Remove implicit startup mutation from `toPythonRulePatch()`**

Replace the `mode` block in `ui/src/bridge/index.ts` with:

```ts
  if ('mode' in rulePatch && !('auto_connect_on_reappear' in nextPatch)) {
    const mode = String(rulePatch.mode)
    nextPatch.auto_connect_on_reappear = mode === 'appear'
  }
```

Keep the explicit `autoConnectOnStartup` branch above it unchanged so callers can still intentionally update startup behavior.

- [ ] **Step 4: Update the existing expectation**

In `ui/src/bridge/index.test.ts`, update the existing expectation around `update_device_rule` from:

```ts
    expect(pywebviewApi?.update_device_rule).toHaveBeenCalledWith('device-1', {
      auto_connect_on_reappear: true,
      auto_connect_on_startup: false,
    })
```

to:

```ts
    expect(pywebviewApi?.update_device_rule).toHaveBeenCalledWith('device-1', {
      auto_connect_on_reappear: true,
    })
```

- [ ] **Step 5: Verify Task 1**

Run:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\bridge\index.test.ts
```

Expected: all bridge tests pass.

---

### Task 2: 初始桥接失败时退出 Loading 并展示可诊断状态

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\state\useControlCenterModel.ts:185-193`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\App.integration.test.tsx`

- [ ] **Step 1: Write the failing UI test**

Add this test in `ui/src/App.integration.test.tsx`:

```tsx
  it('shows a diagnostic unavailable state when initial bridge loading fails', async () => {
    const recordClientEvent = vi.fn(async () => undefined)
    const failingBridge = {
      ...createStaticBridge(baseState),
      getInitialState: vi.fn(async () => {
        throw new Error('启动快照读取失败')
      }),
      recordClientEvent,
    }

    render(<App bridge={failingBridge} />)

    expect(await screen.findByText('Bridge unavailable')).toBeVisible()
    expect(screen.queryByText('Loading AudioBlue control center…')).not.toBeInTheDocument()
    expect(recordClientEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        area: 'ui',
        eventType: 'ui.action.failed',
        title: '加载初始状态失败',
        errorCode: 'Error',
      }),
    )
  })
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run from `E:\Development\Project\PythonProjects\AudioBlue\ui`:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx
```

Expected: the new test times out or still finds the loading shell.

- [ ] **Step 3: Add a local unavailable snapshot helper**

In `ui/src/state/useControlCenterModel.ts`, add this helper above `export function useControlCenterModel(...)`:

```ts
const createInitialLoadFailureState = (message: string): AppState => ({
  devices: [],
  deviceHistory: [],
  prioritizedDeviceIds: [],
  recentActivity: [],
  connection: {
    status: 'disconnected',
    currentPhase: 'failed',
    lastFailure: message,
    lastErrorMessage: message,
  },
  startup: {
    autostart: false,
    backgroundStart: false,
    delaySeconds: 0,
    reconnectOnNextStart: false,
  },
  ui: {
    themeMode: 'system',
    language: 'system',
    showAudioOnly: true,
    diagnosticsMode: true,
  },
  notifications: {
    policy: 'failures',
  },
  diagnostics: {
    lastProbe: 'Bridge unavailable',
    probeResult: message,
    logRetentionDays: 90,
    activityEventCount: 0,
    connectionAttemptCount: 0,
    logRecordCount: 0,
    recentErrors: [
      {
        title: '加载初始状态失败',
        detail: message,
        errorCode: 'InitialStateError',
      },
    ],
  },
  runtime: {
    bridgeMode: 'unavailable',
    chrome: 'custom',
    isMaximized: false,
    canMinimize: false,
    canMaximize: false,
    canClose: false,
  },
})
```

- [ ] **Step 4: Replace the initial loading effect**

Replace the first `useEffect` body in `useControlCenterModel()` with:

```ts
  useEffect(() => {
    let alive = true

    const loadInitialState = async () => {
      try {
        const initialState = await bridge.getInitialState()
        if (!alive) {
          return
        }
        setState(initialState)
      } catch (error) {
        const detail =
          error instanceof Error ? `${error.name}: ${error.message}` : String(error)
        await recordBridgeFailure('加载初始状态失败', error, {
          action: 'getInitialState',
        })
        if (!alive) {
          return
        }
        setState(createInitialLoadFailureState(detail))
      } finally {
        if (alive) {
          setIsLoading(false)
        }
      }
    }

    void loadInitialState()

    const unsubscribe = bridge.onEvent((event) => {
      setState((current) => (current ? applyBridgeEvent(current, event) : current))
    })

    return () => {
      alive = false
      unsubscribe()
    }
  }, [bridge])
```

- [ ] **Step 5: Verify Task 2**

Run:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx
```

Expected: the new test and existing integration tests pass.

---

### Task 3: 历史设备在线状态只由当前扫描可见性决定

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\bridge\index.ts:454`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\bridge\index.test.ts`

- [ ] **Step 1: Write the failing bridge test**

Add this test in `ui/src/bridge/index.test.ts`:

```ts
  it('marks history entries offline when the matching device is absent from the latest scan', async () => {
    window.pywebview = {
      api: {
        get_initial_state: vi.fn(async () => ({
          devices: [
            {
              deviceId: 'device-absent',
              name: 'Absent Headset',
              connectionState: 'disconnected',
              presentInLastScan: false,
              capabilities: { supports_audio_playback: true },
            },
          ],
          deviceRules: {},
          deviceHistory: [
            {
              deviceId: 'device-absent',
              name: 'Absent Headset',
              supportsAudioPlayback: true,
              lastSeenAt: '2026-04-28T10:00:00+08:00',
            },
          ],
          settings: {
            notification: { policy: 'failures' },
            startup: { reconnectOnNextStart: false },
            ui: { theme: 'system', language: 'system' },
          },
        })),
      },
    } as typeof window.pywebview

    const state = await resolveBridge().getInitialState()

    expect(state.deviceHistory[0].isCurrentlyVisible).toBe(false)
  })
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\bridge\index.test.ts
```

Expected: the new test fails because `isCurrentlyVisible` is currently true.

- [ ] **Step 3: Use only present devices for visible history matching**

Replace:

```ts
  const visibleDeviceIds = new Set(devices.map((device) => device.id))
```

with:

```ts
  const visibleDeviceIds = new Set(
    devices
      .filter((device) => device.presentInLastScan)
      .map((device) => device.id),
  )
```

- [ ] **Step 4: Verify Task 3**

Run:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\bridge\index.test.ts
```

Expected: all bridge tests pass.

---

### Task 4: 优化历史页 SQLite 查询

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\storage.py:86-186`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\storage.py:575-725`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_storage.py`

- [ ] **Step 1: Write the focused storage regression test**

Add this test to `tests/test_storage.py`:

```python
def test_list_device_history_limits_after_sql_aggregation(tmp_path):
    """历史列表应在数据库侧聚合后再按业务排序截断。"""
    storage = SQLiteStorage(db_path=tmp_path / "audioblue.db")
    storage.initialize()

    for index in range(25):
        device_id = f"device-{index:02d}"
        happened_at = datetime(2026, 4, 28, 10, index, tzinfo=UTC)
        storage.upsert_device_cache(
            device_id=device_id,
            name=f"Device {index:02d}",
            connection_state="disconnected",
            supports_audio_playback=True,
            supports_microphone=False,
            last_seen_at=happened_at,
        )
        storage.record_connection_attempt(
            device_id=device_id,
            trigger="manual",
            succeeded=index % 2 == 0,
            state="connected" if index % 2 == 0 else "failed",
            failure_reason=None if index % 2 == 0 else "连接失败",
            failure_code=None if index % 2 == 0 else "connection.failed",
            happened_at=happened_at,
        )
        storage.record_activity_event(
            area="device",
            event_type="device.absent" if index == 24 else "device.present",
            level="info",
            title="设备状态变化",
            device_id=device_id,
            details={"change": "removed" if index == 24 else "added"},
            happened_at=happened_at,
        )

    history = storage.list_device_history(limit=5)

    assert len(history) == 5
    assert history[0]["device_id"] == "device-24"
    assert history[0]["last_absent_reason"] == "removed"
    assert history[0]["failure_count"] == 1
```

- [ ] **Step 2: Run storage tests before implementation**

Run from repo root:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_storage.py -q
```

Expected: existing tests pass; the new test may pass functionally before optimization, but it locks returned shape before refactor.

- [ ] **Step 3: Add SQLite indexes during initialization**

In `SQLiteStorage.initialize()`, after the table creation script and before `_ensure_column(...)`, add:

```python
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_connection_history_device_time
                    ON connection_history(device_id, happened_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_connection_history_time
                    ON connection_history(happened_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_activity_events_presence
                    ON activity_events(event_type, device_id, happened_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_device_cache_last_seen
                    ON device_cache(last_seen_at DESC, device_id);
                """
            )
```

- [ ] **Step 4: Replace full-row history loading with SQL aggregation**

In `SQLiteStorage.list_device_history()`, replace the current `connection_rows` and `presence_rows` full scans with aggregate queries. Use these query blocks inside the existing `with self._connect() as connection:`:

```python
            latest_connection_rows = connection.execute(
                """
                WITH ranked AS (
                    SELECT
                        device_id,
                        trigger,
                        state,
                        failure_reason,
                        failure_code,
                        happened_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY device_id
                            ORDER BY happened_at DESC, id DESC
                        ) AS row_number
                    FROM connection_history
                )
                SELECT
                    device_id,
                    happened_at AS last_connection_at,
                    state AS last_connection_state,
                    trigger AS last_connection_trigger,
                    failure_reason AS last_failure_reason,
                    failure_code AS last_failure_code
                FROM ranked
                WHERE row_number = 1
                """
            ).fetchall()
            connection_summary_rows = connection.execute(
                """
                SELECT
                    device_id,
                    SUM(CASE WHEN succeeded = 1 THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN succeeded = 0 THEN 1 ELSE 0 END) AS failure_count,
                    MAX(CASE WHEN succeeded = 1 THEN happened_at ELSE NULL END) AS last_success_at,
                    MAX(CASE WHEN succeeded = 0 THEN happened_at ELSE NULL END) AS last_failure_at
                FROM connection_history
                GROUP BY device_id
                """
            ).fetchall()
            latest_failure_rows = connection.execute(
                """
                WITH ranked AS (
                    SELECT
                        device_id,
                        failure_code,
                        ROW_NUMBER() OVER (
                            PARTITION BY device_id
                            ORDER BY happened_at DESC, id DESC
                        ) AS row_number
                    FROM connection_history
                    WHERE succeeded = 0
                )
                SELECT device_id, failure_code AS last_error_code
                FROM ranked
                WHERE row_number = 1
                """
            ).fetchall()
            presence_rows = connection.execute(
                """
                WITH parsed AS (
                    SELECT
                        device_id,
                        event_type,
                        happened_at,
                        json_extract(details_json, '$.change') AS change_reason,
                        ROW_NUMBER() OVER (
                            PARTITION BY device_id, event_type
                            ORDER BY happened_at DESC, id DESC
                        ) AS row_number
                    FROM activity_events
                    WHERE event_type IN ('device.present', 'device.absent')
                )
                SELECT device_id, event_type, happened_at, change_reason
                FROM parsed
                WHERE row_number = 1
                """
            ).fetchall()
```

Then build dictionaries from these row sets:

```python
        latest_connection_by_id = {
            row["device_id"]: {
                "last_connection_at": row["last_connection_at"],
                "last_connection_state": row["last_connection_state"],
                "last_connection_trigger": row["last_connection_trigger"],
                "last_failure_reason": row["last_failure_reason"],
                "last_failure_code": row["last_failure_code"],
            }
            for row in latest_connection_rows
        }
        connection_counts_by_id = {
            row["device_id"]: {
                "success_count": int(row["success_count"] or 0),
                "failure_count": int(row["failure_count"] or 0),
                "last_success_at": row["last_success_at"],
                "last_failure_at": row["last_failure_at"],
                "last_error_code": None,
            }
            for row in connection_summary_rows
        }
        for row in latest_failure_rows:
            summary = connection_counts_by_id.setdefault(
                row["device_id"],
                {
                    "success_count": 0,
                    "failure_count": 0,
                    "last_success_at": None,
                    "last_failure_at": None,
                    "last_error_code": None,
                },
            )
            summary["last_error_code"] = row["last_error_code"]
```

Replace the current Python JSON parsing presence loop with:

```python
        presence_by_id: dict[str, dict[str, Any]] = {}
        for row in presence_rows:
            device_id = row["device_id"]
            if not isinstance(device_id, str):
                continue
            entry = presence_by_id.setdefault(
                device_id,
                {
                    "last_present_at": None,
                    "last_absent_at": None,
                    "last_present_reason": None,
                    "last_absent_reason": None,
                },
            )
            if row["event_type"] == "device.present":
                entry["last_present_at"] = row["happened_at"]
                entry["last_present_reason"] = row["change_reason"]
            elif row["event_type"] == "device.absent":
                entry["last_absent_at"] = row["happened_at"]
                entry["last_absent_reason"] = row["change_reason"]
```

- [ ] **Step 5: Verify Task 4**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_storage.py tests\test_runtime_storage_exports.py tests\test_app_state.py -q
```

Expected: all selected storage and snapshot tests pass.

---

### Task 5: 主题同步只在主题变化时触发

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\state\useControlCenterModel.ts:246-252`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\App.integration.test.tsx`

- [ ] **Step 1: Write the failing integration test**

Add this test in `ui/src/App.integration.test.tsx`:

```tsx
  it('does not resync native window theme for non-theme state events', async () => {
    const listeners = new Set<(event: BridgeEvent) => void>()
    const syncWindowTheme = vi.fn(async () => undefined)
    const bridge: BackendBridge = {
      ...createStaticBridge(baseState),
      syncWindowTheme,
      onEvent(handler) {
        listeners.add(handler)
        return () => {
          listeners.delete(handler)
        }
      },
    }

    render(<App bridge={bridge} />)

    await screen.findByTestId('window-shell')
    await waitFor(() => expect(syncWindowTheme).toHaveBeenCalledTimes(1))

    listeners.forEach((listener) =>
      listener({
        type: 'activity_changed',
        recentActivity: [
          {
            id: 'evt-theme-noop',
            area: 'runtime',
            level: 'info',
            eventType: 'runtime.event',
            title: '普通状态刷新',
            detail: '',
            happenedAt: '',
          },
        ],
      }),
    )

    await waitFor(() => expect(screen.getByText('普通状态刷新')).toBeVisible())
    expect(syncWindowTheme).toHaveBeenCalledTimes(1)
  })
```

Ensure the file imports `BridgeEvent` if it does not already:

```ts
import type { BackendBridge, BridgeEvent } from './bridge/types'
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx
```

Expected: the new test fails because activity updates cause another `syncWindowTheme()` call.

- [ ] **Step 3: Narrow the theme sync effect dependency**

Replace:

```ts
  useEffect(() => {
    if (!state) {
      return
    }
    document.documentElement.setAttribute('data-theme', resolvedTheme)
    void bridge.syncWindowTheme(resolvedTheme)
  }, [bridge, resolvedTheme, state])
```

with:

```ts
  useEffect(() => {
    if (!state) {
      return
    }
    document.documentElement.setAttribute('data-theme', resolvedTheme)
    void bridge.syncWindowTheme(resolvedTheme)
  }, [bridge, resolvedTheme, state !== null])
```

This keeps the initial post-load sync, but normal state object replacement no longer retriggers native theme work.

- [ ] **Step 4: Verify Task 5**

Run:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx
```

Expected: all integration tests pass.

---

## Final Verification

- [ ] **Run Python focused suites**

Run from `E:\Development\Project\PythonProjects\AudioBlue`:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_connector_service_backend.py tests\test_connector_service_watcher.py tests\test_session_state.py tests\test_audio_routing.py tests\test_desktop_host_runtime.py tests\test_desktop_host_api.py tests\test_storage.py tests\test_runtime_storage_exports.py tests\test_app_state.py -q
```

Expected: all selected Python tests pass.

- [ ] **Run frontend focused suites**

Run from `E:\Development\Project\PythonProjects\AudioBlue\ui`:

```powershell
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\bridge\index.test.ts src\App.integration.test.tsx
```

Expected: all selected frontend tests pass.

- [ ] **Run lint**

Run from `E:\Development\Project\PythonProjects\AudioBlue\ui`:

```powershell
npm run lint
```

Expected: ESLint exits with code 0.

- [ ] **Run build**

Run from `E:\Development\Project\PythonProjects\AudioBlue\ui`:

```powershell
npm run build
```

Expected: TypeScript and Vite build complete successfully.

- [ ] **Review git diff**

Run from `E:\Development\Project\PythonProjects\AudioBlue`:

```powershell
git diff -- ui\src\bridge\index.ts ui\src\bridge\index.test.ts ui\src\state\useControlCenterModel.ts ui\src\App.integration.test.tsx src\audio_blue\storage.py tests\test_storage.py
```

Expected: diff only contains the 5 scoped repairs and their tests.

---

## Implementation Notes

- 当前工作区已有未提交的 `ThemedSelect`/theme 相关改动，实施时不要回退这些文件。
- Task 1、2、3、5 都在前端侧，可按顺序连续实施，但每个 task 都应先看失败测试再改实现。
- Task 4 是唯一后端性能优化，注意保持 `list_device_history()` 的返回 key 不变。
- 全量 `pytest -q` 在这台机器上历史上可能被 Temp 权限污染；最终报告要区分 focused suites 结果和环境性全量阻塞。
- 所有命令都按 Windows PowerShell 写法执行。
