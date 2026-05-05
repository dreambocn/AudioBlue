# AudioBlue Global Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-05-05 全局审计确认的 13 个问题，降低连接链路被 UI/观测异常反向打断、WinRT worker 永久等待、托盘退出残留、离线设备误操作、托盘面板卡死和发布校验漏检的风险。

**Architecture:** 按风险面分 4 个批次推进：先把 Python runtime 的事件发布、worker、退出和观测链路改为 fail-open / bounded；再收敛前端 selector 与托盘错误兜底；随后修复发布版本和 WebView2 架构校验；最后补日常 CI、开源发布契约和开发文档。每个任务先补 focused regression test，再做最小实现，最后运行对应 focused verification。

**Tech Stack:** Windows + PowerShell Core、Python 3.12、pytest、SQLite、pywebview/WebView2、Win32 tray、React 19、TypeScript、Vitest、GitHub Actions、Inno Setup。

---

## Finding Map

- Finding 1 -> Task 1: 状态监听器异常隔离。
- Finding 2 -> Task 2: ConnectorService worker bounded wait。
- Finding 3 -> Task 4: 托盘退出清理 try/finally。
- Finding 4 -> Task 3: Observability fail-open。
- Finding 5 -> Task 5: 离线音频设备不可作为可连接目标。
- Finding 6 -> Task 6: 托盘快速面板初始化和操作失败兜底。
- Finding 7 -> Task 8: Inno AppVersion 绑定发布版本。
- Finding 8 -> Task 9: WebView2 打包校验按目标架构检查。
- Finding 9 -> Task 10: 新增日常 CI。
- Finding 10 -> Task 7: 全局错误上报自身失败时静默降级。
- Finding 11 -> Task 4: 托盘菜单 HMENU 释放。
- Finding 12 -> Task 11: 内部计划目录纳入开源发布契约。
- Finding 13 -> Task 12: DEVELOPMENT 打包校验命令补齐必填参数。

---

## File Structure

- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\session_state.py`
  - 隔离 `_publish_snapshot()` 中单个 listener 异常。
  - 在有 `observability` 时记录 listener 推送失败，但不影响其他 listener 和主流程。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_session_state.py`
  - 增加 listener 抛错不阻断后续 listener、连接事件仍发布的回归测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\desktop_host.py`
  - 让 `DesktopHost.push_state()` 在窗口不可用或 `evaluate_js()` 抛错时降级丢弃本次推送。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_desktop_host_runtime.py`
  - 增加 `push_state()` 遇到 `evaluate_js` 失败不抛出的测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py`
  - 为 `_run_on_worker()` 增加超时、worker 存活检查和 shutdown guard。
  - 增加结构化 worker timeout 错误。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_connector_service_backend.py`
  - 增加 worker job 超时、shutdown 后拒绝新任务的 focused tests。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\observability.py`
  - 观测存储写入失败时只记录 logger，不向业务调用方抛出。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_diagnostics.py`
  - 增加 observability 存储失败仍写 logger 且不抛错的测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\tray_host.py`
  - 托盘退出清理改为 `try/finally` 保底执行。
  - 托盘菜单显示后释放 HMENU。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_tray_menu_mapping.py`
  - 增加保存配置失败时仍 shutdown service / PostQuitMessage 的测试。
  - 增加菜单句柄释放测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\state\selectors.ts`
  - 拆分实时可连接设备与历史保留设备。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\App.integration.test.tsx`
  - 增加离线音频设备不作为 connect target 的集成测试。
  - 增加全局错误上报失败不递归的测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\tray\TrayQuickPanelView.tsx`
  - 初始化失败时进入最小 unavailable state。
  - 托盘操作失败时通过 `recordClientEvent` 记录并吞掉 Promise rejection。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\components\TrayQuickPanel.test.tsx`
  - 增加托盘面板失败兜底和操作失败被捕获的测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\state\useControlCenterModel.ts`
  - 新增 safe record helper，避免全局错误上报自身失败时制造二次 unhandled rejection。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\installer\AudioBlue.InstallerCore.iss`
  - `AppVersion` 改为 Inno 预处理变量。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\scripts\build-release.ps1`
  - 将 pyproject 版本传入 Inno 编译器。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\scripts\verify_packaging_assets.py`
  - 按传入 WebView2 installer 文件名检查安装器脚本引用。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_open_source_release_contract.py`
  - 增加版本绑定、WebView2 架构校验、日常 CI 和内部计划目录契约测试。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_packaging_verification_script.py`
  - 增加 x86/x64/arm64 WebView2 文件名 fixture。
- Create: `E:\Development\Project\PythonProjects\AudioBlue\.github\workflows\ci.yml`
  - pull_request 和主分支 push 的日常验证入口。
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\docs\DEVELOPMENT.md`
  - 更新打包校验命令，补齐 required 参数。

---

## Batch 1: Runtime Reliability

### Task 1: 隔离状态监听器和 WebView 推送异常

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\session_state.py:335-339`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\desktop_host.py:681-695`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_session_state.py`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_desktop_host_runtime.py`

- [ ] **Step 1: Add failing listener isolation test**

Add a focused test in `tests/test_session_state.py`:

```python
def test_publish_snapshot_continues_when_listener_fails(session_state):
    """单个监听器失败时，后续监听器仍应收到快照。"""
    received: list[dict] = []

    def broken_listener(_snapshot: dict) -> None:
        raise RuntimeError("webview is gone")

    def healthy_listener(snapshot: dict) -> None:
        received.append(snapshot)

    session_state.subscribe(broken_listener)
    session_state.subscribe(healthy_listener)

    snapshot = session_state.set_reconnect(True)

    assert received
    assert received[-1]["settings"]["startup"]["reconnectOnNextStart"] is True
    assert snapshot["settings"]["startup"]["reconnectOnNextStart"] is True
```

- [ ] **Step 2: Add failing DesktopHost push_state test**

Add a focused test in `tests/test_desktop_host_runtime.py`:

```python
def test_push_state_ignores_evaluate_js_failure(tmp_path):
    """WebView 推送失败不应反向打断后端事件链。"""
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")

    class WindowStub:
        def evaluate_js(self, _script: str) -> None:
            raise RuntimeError("webview destroyed")

    host = DesktopHost(
        api=DesktopApiStub(),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.main_window = WindowStub()

    host.push_state({"devices": []})
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_session_state.py::test_publish_snapshot_continues_when_listener_fails tests\test_desktop_host_runtime.py::test_push_state_ignores_evaluate_js_failure -q
```

Expected before implementation: both tests fail because listener / `evaluate_js()` exceptions propagate.

- [ ] **Step 4: Implement listener isolation**

Change `_publish_snapshot()` in `src/audio_blue/session_state.py` to this shape:

```python
    def _publish_snapshot(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        for callback in list(self._listeners):
            try:
                callback(snapshot)
            except Exception as exc:
                self._record_exception(
                    area="runtime",
                    event_type="runtime.snapshot.listener_failed",
                    title="状态监听器推送失败",
                    exc=exc,
                    details={"listener": repr(callback)},
                )
        return snapshot
```

- [ ] **Step 5: Implement WebView push fail-open**

Wrap `evaluate_js()` in `src/audio_blue/desktop_host.py`:

```python
    def push_state(self, snapshot: dict[str, Any]) -> None:
        if self.main_window is None or not hasattr(self.main_window, "evaluate_js"):
            return
        runtime_snapshot = (
            self.api.attach_runtime_state(snapshot)
            if hasattr(self.api, "attach_runtime_state")
            else snapshot
        )
        payload = json.dumps(runtime_snapshot, ensure_ascii=False)
        script = (
            "window.dispatchEvent("
            f"new CustomEvent('audioblue:state', {{ detail: {payload} }})"
            ");"
        )
        try:
            self.main_window.evaluate_js(script)
        except Exception:
            return
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_session_state.py::test_publish_snapshot_continues_when_listener_fails tests\test_desktop_host_runtime.py::test_push_state_ignores_evaluate_js_failure -q
```

Expected after implementation: both tests pass.

- [ ] **Step 7: Commit runtime listener fix**

Run:

```powershell
git add -- src\audio_blue\session_state.py src\audio_blue\desktop_host.py tests\test_session_state.py tests\test_desktop_host_runtime.py
git commit -m "fix: 隔离状态推送监听器异常"
```

---

### Task 2: 为 ConnectorService worker 增加 bounded wait

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py:300-340`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py:1124-1135`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_connector_service_backend.py`

- [ ] **Step 1: Add failing worker timeout test**

Add a focused test in `tests/test_connector_service_backend.py`:

```python
def test_worker_call_times_out_when_backend_hangs():
    """WinRT worker 卡住时，调用方应收到有界失败而不是无限等待。"""
    service = ConnectorService(
        backend=BackendStub(list_devices=lambda: Event().wait()),
        worker_timeout_seconds=0.01,
    )

    with pytest.raises(ConnectorWorkerTimeoutError, match="list_devices"):
        service.refresh_devices()

    service.shutdown()
```

- [ ] **Step 2: Add failing shutdown guard test**

Add a second focused test in the same file:

```python
def test_worker_rejects_new_jobs_after_shutdown():
    """关闭开始后不再接受新的 worker job。"""
    service = ConnectorService(backend=BackendStub(list_devices=lambda: []))
    service.shutdown()

    with pytest.raises(ConnectorWorkerShutdownError):
        service.refresh_devices()
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_connector_service_backend.py::test_worker_call_times_out_when_backend_hangs tests\test_connector_service_backend.py::test_worker_rejects_new_jobs_after_shutdown -q
```

Expected before implementation: tests fail because timeout / shutdown error types do not exist.

- [ ] **Step 4: Add worker error types and constructor parameter**

In `src/audio_blue/connector_service.py`, add runtime errors near the worker dataclass definitions:

```python
class ConnectorWorkerTimeoutError(RuntimeError):
    """后台 WinRT worker 调用超时。"""


class ConnectorWorkerShutdownError(RuntimeError):
    """服务关闭后拒绝新的 worker 调用。"""
```

Add a constructor parameter and field:

```python
        worker_timeout_seconds: float = 15.0,
```

```python
        self._worker_timeout_seconds = max(0.0, float(worker_timeout_seconds))
```

- [ ] **Step 5: Update worker job to carry a name**

Extend `_WorkerJob` with an `action_name` field:

```python
@dataclass(slots=True)
class _WorkerJob:
    """封装提交到 WinRT worker 的同步任务。"""

    action: Callable[[], object]
    completed: Event
    action_name: str
    result: object | None = None
    error: BaseException | None = None
```

- [ ] **Step 6: Implement bounded wait**

Change `_run_on_worker()` to:

```python
    def _run_on_worker(self, action: Callable[[], object], *, action_name: str = "worker_job") -> object:
        if self._jobs is None:
            return action()
        if self.is_shutdown or self._worker is None or not self._worker.is_alive():
            raise ConnectorWorkerShutdownError("连接服务已关闭，无法执行后台任务。")

        job = _WorkerJob(action=action, completed=Event(), action_name=action_name)
        self._jobs.put(job)
        completed = job.completed.wait(self._worker_timeout_seconds)
        if not completed:
            raise ConnectorWorkerTimeoutError(f"{action_name} 超过 {self._worker_timeout_seconds:.1f} 秒未完成。")

        if job.error is not None:
            raise job.error

        return job.result
```

Update call sites with descriptive action names:

```python
self._run_on_worker(self._backend.list_devices, action_name="list_devices")
self._run_on_worker(lambda: self._backend.connect(...), action_name="connect")
self._run_on_worker(lambda: self._backend.disconnect(handle), action_name="disconnect")
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_connector_service_backend.py::test_worker_call_times_out_when_backend_hangs tests\test_connector_service_backend.py::test_worker_rejects_new_jobs_after_shutdown -q
```

Expected after implementation: tests pass.

- [ ] **Step 8: Commit worker bounded wait**

Run:

```powershell
git add -- src\audio_blue\connector_service.py tests\test_connector_service_backend.py
git commit -m "fix: 为连接 worker 增加超时保护"
```

---

### Task 3: 让 Observability 记录失败不影响主业务

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\observability.py:32-43`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_diagnostics.py`

- [ ] **Step 1: Add failing fail-open test**

Add this test in `tests/test_diagnostics.py`:

```python
def test_observability_record_event_fails_open(caplog):
    """观测写入失败只记录日志，不应打断业务调用方。"""

    class BrokenStorage:
        def record_activity_event(self, **_payload):
            raise PermissionError("database locked")

    logger = logging.getLogger("audio_blue.test.observability")
    service = ObservabilityService(storage=BrokenStorage(), logger=logger)

    with caplog.at_level(logging.WARNING):
        service.record_event(
            area="runtime",
            event_type="runtime.snapshot.listener_failed",
            level="warning",
            title="状态监听器推送失败",
            detail="RuntimeError: webview destroyed",
        )

    assert "观测事件写入失败" in caplog.text
```

- [ ] **Step 2: Run focused test and confirm failure**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_diagnostics.py::test_observability_record_event_fails_open -q
```

Expected before implementation: test fails because `PermissionError` propagates.

- [ ] **Step 3: Implement fail-open storage write**

Change `record_event()` in `src/audio_blue/observability.py`:

```python
        storage_method = getattr(self._storage, "record_activity_event", None)
        if callable(storage_method):
            try:
                storage_method(
                    area=area,
                    event_type=event_type,
                    level=level,
                    title=title,
                    detail=detail,
                    device_id=device_id,
                    error_code=error_code,
                    details=details,
                )
            except Exception as exc:
                if self._logger is not None:
                    self._logger.warning("观测事件写入失败：%s", exc)
```

- [ ] **Step 4: Run focused test**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_diagnostics.py::test_observability_record_event_fails_open -q
```

Expected after implementation: test passes.

- [ ] **Step 5: Commit observability fail-open**

Run:

```powershell
git add -- src\audio_blue\observability.py tests\test_diagnostics.py
git commit -m "fix: 观测写入失败时不阻断业务"
```

---

### Task 4: 托盘退出清理和菜单句柄释放

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\tray_host.py:247-270`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\tray_host.py:385-399`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_tray_menu_mapping.py`

- [ ] **Step 1: Add failing shutdown cleanup test**

Add this test in `tests/test_tray_menu_mapping.py`:

```python
def test_tray_destroy_always_shutdowns_service_when_config_save_fails(monkeypatch):
    """保存退出配置失败时，服务清理和消息循环退出仍应执行。"""
    service = ServiceStub()
    host = TrayHost(
        service=service,
        config=AppConfig(),
        logger=logging.getLogger("audio_blue.test.tray"),
        background=True,
    )
    posted_messages: list[int] = []

    monkeypatch.setattr("audio_blue.tray_host.save_config", lambda _config: (_ for _ in ()).throw(PermissionError("locked")))
    monkeypatch.setattr("audio_blue.tray_host.win32gui.PostQuitMessage", lambda code: posted_messages.append(code))

    host._on_destroy(1, 0, 0, 0)

    assert service.is_shutdown is True
    assert posted_messages == [0]
```

- [ ] **Step 2: Add failing menu destroy test**

Add this test in `tests/test_tray_menu_mapping.py`:

```python
def test_show_menu_destroys_popup_menu(monkeypatch):
    """每次托盘右键弹出的 HMENU 都应释放。"""
    created_menus: list[int] = []
    destroyed_menus: list[int] = []
    service = ServiceStub()
    host = TrayHost(
        service=service,
        config=AppConfig(),
        logger=logging.getLogger("audio_blue.test.tray"),
        background=True,
    )
    host._hwnd = 100

    monkeypatch.setattr("audio_blue.tray_host.win32gui.CreatePopupMenu", lambda: created_menus.append(200) or 200)
    monkeypatch.setattr("audio_blue.tray_host.win32gui.DestroyMenu", lambda menu: destroyed_menus.append(menu))
    monkeypatch.setattr("audio_blue.tray_host.win32gui.GetCursorPos", lambda: (10, 20))
    monkeypatch.setattr("audio_blue.tray_host.win32gui.SetForegroundWindow", lambda _hwnd: None)
    monkeypatch.setattr("audio_blue.tray_host.win32gui.TrackPopupMenu", lambda *_args: None)
    monkeypatch.setattr("audio_blue.tray_host.win32gui.AppendMenu", lambda *_args: None)

    host._show_menu()

    assert destroyed_menus == created_menus
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_tray_menu_mapping.py::test_tray_destroy_always_shutdowns_service_when_config_save_fails tests\test_tray_menu_mapping.py::test_show_menu_destroys_popup_menu -q
```

Expected before implementation: tests fail because save failure propagates and menu is not destroyed.

- [ ] **Step 4: Implement shutdown cleanup guard**

Change `_on_destroy()` in `src/audio_blue/tray_host.py`:

```python
    def _on_destroy(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        try:
            if self._notify_id is not None:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, self._notify_id)
            self._record_event(
                area="tray",
                event_type="tray.shutdown",
                level="info",
                title="托盘宿主已退出",
            )
            self._shutdown_ui()
            if self._session_state is not None and hasattr(self._session_state, "shutdown"):
                self._session_state.shutdown()
            try:
                save_config(build_exit_config(self._config, self._service))
            except Exception:
                self._logger.warning("保存退出配置失败。", exc_info=True)
        finally:
            self._service.shutdown()
            win32gui.PostQuitMessage(0)
        return 0
```

- [ ] **Step 5: Implement HMENU release**

Wrap menu tracking in `src/audio_blue/tray_host.py`:

```python
        menu = win32gui.CreatePopupMenu()
        try:
            self._command_map.clear()
            self._next_command_id = 1000
            devices = (
                self._session_state.list_devices()
                if self._session_state is not None
                else list(self._service.known_devices.values())
            )
            reconnect_enabled, selected_language = self._resolve_menu_preferences()
            for entry in build_menu_entries(
                devices,
                reconnect_enabled,
                language=selected_language,
                selected_language=selected_language,
            ):
                self._append_menu_entry(menu, entry)

            cursor_x, cursor_y = win32gui.GetCursorPos()
            try:
                win32gui.SetForegroundWindow(self._hwnd)
            except Exception:
                self._logger.debug("Failed to foreground tray host before opening menu.", exc_info=True)
            win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, cursor_x, cursor_y, 0, self._hwnd, None)
        finally:
            win32gui.DestroyMenu(menu)
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_tray_menu_mapping.py::test_tray_destroy_always_shutdowns_service_when_config_save_fails tests\test_tray_menu_mapping.py::test_show_menu_destroys_popup_menu -q
```

Expected after implementation: tests pass.

- [ ] **Step 7: Commit tray lifecycle fix**

Run:

```powershell
git add -- src\audio_blue\tray_host.py tests\test_tray_menu_mapping.py
git commit -m "fix: 保底清理托盘宿主资源"
```

---

## Batch 2: Frontend State And Error Boundaries

### Task 5: 排除离线音频设备作为实时可连接目标

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\state\selectors.ts:33-39`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\App.integration.test.tsx`

- [ ] **Step 1: Add failing integration test**

Add this test in `ui/src/App.integration.test.tsx`:

```tsx
  it('does not offer connect action for an absent disconnected audio device', async () => {
    const bridge = createMutableBridge({
      ...baseState,
      devices: [
        {
          ...baseState.devices[0],
          id: 'absent-audio',
          name: 'Absent Headphones',
          isConnected: false,
          isConnecting: false,
          supportsAudio: true,
          presentInLastScan: false,
        },
      ],
      deviceHistory: [],
    })

    render(<App bridge={bridge} />)

    expect(await screen.findByText('No matched A2DP source devices')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Connect' })).not.toBeInTheDocument()
  })
```

- [ ] **Step 2: Run focused test and confirm failure**

Run:

```powershell
Push-Location '.\ui'
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx -t "does not offer connect action for an absent disconnected audio device"
Pop-Location
```

Expected before implementation: test fails because absent audio device is still counted as available.

- [ ] **Step 3: Implement connectable device selector**

Change `ui/src/state/selectors.ts`:

```ts
const isRealtimeDevice = (device: DeviceViewModel) =>
  device.presentInLastScan || device.isConnected || device.isConnecting

export const selectAudioDevices = (state: AppState) =>
  selectOrderedDevices(state).filter(
    (device) => device.supportsAudio && isRealtimeDevice(device),
  )

export const selectVisibleDevices = (state: AppState) =>
  selectOrderedDevices(state).filter(
    (device) => isRealtimeDevice(device) && (device.isConnected || device.supportsAudio),
  )
```

- [ ] **Step 4: Run focused frontend test**

Run:

```powershell
Push-Location '.\ui'
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx -t "does not offer connect action for an absent disconnected audio device"
Pop-Location
```

Expected after implementation: test passes.

- [ ] **Step 5: Commit selector fix**

Run:

```powershell
git add -- ui\src\state\selectors.ts ui\src\App.integration.test.tsx
git commit -m "fix: 排除离线音频设备实时操作"
```

---

### Task 6: 托盘快速面板初始化和操作失败兜底

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\tray\TrayQuickPanelView.tsx:21-92`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\App.integration.test.tsx`

- [ ] **Step 1: Add failing quick panel initial failure test**

Add this test in `ui/src\App.integration.test.tsx`:

```tsx
  it('shows unavailable quick panel state when tray initial loading fails', async () => {
    const bridge = {
      ...createMutableBridge(baseState),
      getInitialState: vi.fn(async () => {
        throw new Error('托盘快照读取失败')
      }),
      recordClientEvent: vi.fn(async () => undefined),
    }

    render(<TrayQuickPanelView bridge={bridge} />)

    expect(await screen.findByText('Bridge unavailable')).toBeVisible()
    expect(bridge.recordClientEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        eventType: 'tray.initial_state.failed',
        title: '托盘快照读取失败',
      }),
    )
  })
```

- [ ] **Step 2: Add failing quick panel action failure test**

Add this test in `ui/src\App.integration.test.tsx`:

```tsx
  it('records quick panel action failure without unhandled rejection', async () => {
    const bridge = {
      ...createMutableBridge(baseState),
      connectDevice: vi.fn(async () => {
        throw new Error('连接失败')
      }),
      recordClientEvent: vi.fn(async () => undefined),
    }
    const user = userEvent.setup()

    render(<TrayQuickPanelView bridge={bridge} />)

    await user.click(await screen.findByRole('button', { name: 'Connect' }))

    expect(bridge.recordClientEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        eventType: 'tray.action.failed',
        title: '托盘操作失败',
      }),
    )
  })
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```powershell
Push-Location '.\ui'
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx -t "quick panel"
Pop-Location
```

Expected before implementation: new quick panel failure tests fail.

- [ ] **Step 4: Implement minimal unavailable state helper**

In `ui/src/tray/TrayQuickPanelView.tsx`, add a local helper:

```ts
const createTrayFailureState = (detail: string): AppState => ({
  devices: [],
  deviceHistory: [],
  prioritizedDeviceIds: [],
  recentActivity: [
    {
      id: 'tray-initial-load-failed',
      area: 'tray',
      level: 'error',
      eventType: 'tray.initial_state.failed',
      title: '托盘快照读取失败',
      detail,
      happenedAt: new Date().toISOString(),
    },
  ],
  connection: { status: 'failed', lastFailure: detail },
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
  notifications: { policy: 'failures' },
  diagnostics: {
    logRetentionDays: 90,
    activityEventCount: 0,
    connectionAttemptCount: 0,
    logRecordCount: 0,
    recentErrors: [{ title: '托盘快照读取失败', detail }],
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

- [ ] **Step 5: Implement safe tray runner**

Wrap initialization and actions in `TrayQuickPanelView`:

```ts
  const recordTrayFailure = async (title: string, error: unknown, action: string) => {
    const detail = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
    try {
      await resolvedBridge.recordClientEvent({
        area: 'tray',
        eventType: action === 'getInitialState' ? 'tray.initial_state.failed' : 'tray.action.failed',
        level: 'error',
        title,
        detail,
        details: { action },
      })
    } catch {
      return
    }
  }

  const runTrayAction = (action: string, task: () => Promise<unknown>) => {
    void task().catch((error) => recordTrayFailure('托盘操作失败', error, action))
  }
```

Use `.catch()` in initial load and change callbacks:

```tsx
onConnect={(id) => runTrayAction('connectDevice', () => resolvedBridge.connectDevice(id))}
onDisconnect={(id) => runTrayAction('disconnectDevice', () => resolvedBridge.disconnectDevice(id))}
onToggleReconnect={(enabled) => runTrayAction('setReconnect', () => resolvedBridge.setReconnect(enabled))}
onOpenBluetoothSettings={() => runTrayAction('openBluetoothSettings', () => resolvedBridge.openBluetoothSettings())}
onRefreshDevices={() => runTrayAction('refreshDevices', () => resolvedBridge.refreshDevices())}
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
Push-Location '.\ui'
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx -t "quick panel"
Pop-Location
```

Expected after implementation: quick panel tests pass.

- [ ] **Step 7: Commit quick panel fallback**

Run:

```powershell
git add -- ui\src\tray\TrayQuickPanelView.tsx ui\src\App.integration.test.tsx
git commit -m "fix: 增加托盘面板失败兜底"
```

---

### Task 7: 全局错误上报自身失败时静默降级

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\state\useControlCenterModel.ts:281-310`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\ui\src\App.integration.test.tsx`

- [ ] **Step 1: Add failing global error reporting test**

Add this test in `ui/src\App.integration.test.tsx`:

```tsx
  it('swallows recordClientEvent rejection from global error handlers', async () => {
    const bridge = {
      ...createMutableBridge(baseState),
      recordClientEvent: vi.fn(async () => {
        throw new Error('记录失败')
      }),
    }

    render(<App bridge={bridge} />)

    window.dispatchEvent(new ErrorEvent('error', { message: '界面异常' }))

    await waitFor(() => {
      expect(bridge.recordClientEvent).toHaveBeenCalledTimes(1)
    })
  })
```

- [ ] **Step 2: Run focused test and confirm failure**

Run:

```powershell
Push-Location '.\ui'
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx -t "swallows recordClientEvent rejection"
Pop-Location
```

Expected before implementation: test fails through unhandled rejection or repeated calls.

- [ ] **Step 3: Add safe record helper**

In `ui/src/state/useControlCenterModel.ts`, add:

```ts
  const safeRecordClientEvent = useCallback(
    (payload: Parameters<BackendBridge['recordClientEvent']>[0]) => {
      void bridge.recordClientEvent(payload).catch(() => undefined)
    },
    [bridge],
  )
```

Use `safeRecordClientEvent(...)` in the global `error` and `unhandledrejection` handlers instead of `void bridge.recordClientEvent(...)`.

- [ ] **Step 4: Run focused test**

Run:

```powershell
Push-Location '.\ui'
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx -t "swallows recordClientEvent rejection"
Pop-Location
```

Expected after implementation: test passes.

- [ ] **Step 5: Commit global error reporting guard**

Run:

```powershell
git add -- ui\src\state\useControlCenterModel.ts ui\src\App.integration.test.tsx
git commit -m "fix: 避免错误上报递归失败"
```

---

## Batch 3: Packaging And Release Verification

### Task 8: 将 Inno AppVersion 绑定到发布版本

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\installer\AudioBlue.InstallerCore.iss:30-34`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\scripts\build-release.ps1:303-309`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_open_source_release_contract.py`

- [ ] **Step 1: Add failing release version contract test**

Add this test in `tests/test_open_source_release_contract.py`:

```python
def test_inno_app_version_is_injected_from_release_script():
    """安装器版本必须由发布脚本注入，避免与 pyproject 版本漂移。"""
    core = (REPO_ROOT / "installer" / "AudioBlue.InstallerCore.iss").read_text(encoding="utf-8")
    release_script = RELEASE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "AppVersion={#AppVersion}" in core
    assert "AppVersion = $projectVersion" in release_script
```

- [ ] **Step 2: Run focused test and confirm failure**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_open_source_release_contract.py::test_inno_app_version_is_injected_from_release_script -q
```

Expected before implementation: test fails because `AppVersion=0.1.2` is hardcoded.

- [ ] **Step 3: Update Inno template**

Change `installer/AudioBlue.InstallerCore.iss`:

```iss
#ifndef AppVersion
#define AppVersion "0.0.0"
#endif

[Setup]
AppVersion={#AppVersion}
```

- [ ] **Step 4: Pass version from release script**

Add to `$preprocessorDefinitions` in `scripts/build-release.ps1`:

```powershell
        AppVersion = $projectVersion
```

- [ ] **Step 5: Run focused test**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_open_source_release_contract.py::test_inno_app_version_is_injected_from_release_script -q
```

Expected after implementation: test passes.

- [ ] **Step 6: Commit installer version binding**

Run:

```powershell
git add -- installer\AudioBlue.InstallerCore.iss scripts\build-release.ps1 tests\test_open_source_release_contract.py
git commit -m "fix: 绑定安装器发布版本"
```

---

### Task 9: WebView2 打包校验按 runtime 文件名检查

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\scripts\verify_packaging_assets.py:49-57`
- Test: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_packaging_verification_script.py`

- [ ] **Step 1: Add failing x86/arm64 packaging verification tests**

Add this parametrized test in `tests/test_packaging_verification_script.py`:

```python
@pytest.mark.parametrize(
    "runtime_name",
    [
        "MicrosoftEdgeWebView2RuntimeInstallerX86.exe",
        "MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
        "MicrosoftEdgeWebView2RuntimeInstallerARM64.exe",
    ],
)
def test_collect_packaging_report_requires_matching_webview2_runtime_name(tmp_path, runtime_name):
    """校验脚本必须按传入的 WebView2 安装器文件名检查脚本引用。"""
    dist_root = tmp_path / "dist"
    app_dir = dist_root / "AudioBlue"
    app_dir.mkdir(parents=True)
    (app_dir / "audioblue.exe").write_text("exe", encoding="utf-8")
    (app_dir / "ui").mkdir()
    (app_dir / "ui" / "index.html").write_text("<html></html>", encoding="utf-8")
    webview2_dir = dist_root / "webview2"
    webview2_dir.mkdir()
    runtime_path = webview2_dir / runtime_name
    runtime_path.write_text("runtime", encoding="utf-8")

    installer = tmp_path / "AudioBlue.iss"
    installer.write_text("#include \"AudioBlue.InstallerCore.iss\"", encoding="utf-8")
    core = tmp_path / "AudioBlue.InstallerCore.iss"
    core.write_text(
        f"""
Software\\Microsoft\\Windows\\CurrentVersion\\Run
--background
IsWebView2RuntimeInstalled
Source: "..\\dist\\webview2\\{runtime_name}"; DestDir: "{{tmp}}"
""",
        encoding="utf-8",
    )

    report = collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[installer],
        installer_core_script=core,
        webview2_runtime_installer=runtime_path,
    )

    assert report["ok"] is True
```

- [ ] **Step 2: Add mismatch test**

Add this test:

```python
def test_collect_packaging_report_rejects_mismatched_webview2_runtime_name(tmp_path):
    """传入 arm64 runtime 时，core 脚本不能只引用 x64 文件名。"""
    dist_root, installer, core, runtime_path = build_packaging_fixture(
        tmp_path,
        runtime_name="MicrosoftEdgeWebView2RuntimeInstallerARM64.exe",
        core_runtime_name="MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
    )

    report = collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[installer],
        installer_core_script=core,
        webview2_runtime_installer=runtime_path,
    )

    assert report["ok"] is False
    assert any("MicrosoftEdgeWebView2RuntimeInstallerARM64.exe" in issue for issue in report["issues"])
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_packaging_verification_script.py -q
```

Expected before implementation: x86/arm64 matching tests fail because the script checks only X64.

- [ ] **Step 4: Implement runtime-name validation**

Change `scripts/verify_packaging_assets.py`:

```python
        if webview2_runtime_installer is not None:
            expected_runtime_name = webview2_runtime_installer.name
            if not webview2_runtime_installer.exists():
                issues.append(
                    f"Missing bundled WebView2 runtime installer: {webview2_runtime_installer}"
                )
            if expected_runtime_name not in content:
                issues.append(
                    "Installer core scaffold is missing the bundled WebView2 runtime "
                    f"installer reference: {expected_runtime_name}"
                )
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_packaging_verification_script.py -q
```

Expected after implementation: packaging verification tests pass.

- [ ] **Step 6: Commit WebView2 verification fix**

Run:

```powershell
git add -- scripts\verify_packaging_assets.py tests\test_packaging_verification_script.py
git commit -m "fix: 按架构校验 WebView2 打包资源"
```

---

### Task 10: 新增 pull_request 和主分支 push 日常 CI

**Files:**
- Create: `E:\Development\Project\PythonProjects\AudioBlue\.github\workflows\ci.yml`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_open_source_release_contract.py`

- [ ] **Step 1: Add failing CI contract test**

Add this test in `tests/test_open_source_release_contract.py`:

```python
def test_daily_ci_workflow_runs_on_pull_request_and_push():
    """日常 CI 应在 PR 和主分支 push 阶段运行测试与前端构建。"""
    workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.exists()

    content = workflow.read_text(encoding="utf-8")
    assert "pull_request:" in content
    assert "push:" in content
    assert "uv run pytest -q" in content
    assert "npm test" in content
    assert "npm run lint" in content
    assert "npm run build" in content
```

- [ ] **Step 2: Run focused test and confirm failure**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_open_source_release_contract.py::test_daily_ci_workflow_runs_on_pull_request_and_push -q
```

Expected before implementation: test fails because `ci.yml` is missing.

- [ ] **Step 3: Create CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches:
      - main
      - master

permissions:
  contents: read

jobs:
  verify:
    runs-on: windows-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          architecture: 'x64'

      - name: Set up uv
        uses: astral-sh/setup-uv@v5

      - name: Sync Python dependencies
        run: uv sync --frozen --all-groups

      - name: Run Python tests
        run: uv run pytest -q

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: ui/package-lock.json

      - name: Install frontend dependencies
        working-directory: ui
        run: npm ci

      - name: Run frontend tests
        working-directory: ui
        run: npm test

      - name: Run frontend lint
        working-directory: ui
        run: npm run lint

      - name: Build frontend
        working-directory: ui
        run: npm run build
```

- [ ] **Step 4: Run focused test**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_open_source_release_contract.py::test_daily_ci_workflow_runs_on_pull_request_and_push -q
```

Expected after implementation: test passes.

- [ ] **Step 5: Commit CI workflow**

Run:

```powershell
git add -- .github\workflows\ci.yml tests\test_open_source_release_contract.py
git commit -m "ci: 增加日常验证工作流"
```

---

## Batch 4: Open Source Contract And Documentation

### Task 11: 将内部计划目录纳入开源发布契约

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_open_source_release_contract.py:22-27`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\.gitignore`
- Delete or move: `E:\Development\Project\PythonProjects\AudioBlue\docs\superpowers\plans\2026-04-28-audioblue-review-fixes.md`
- Keep current plan file during local remediation until release cleanup is intentionally executed.

- [ ] **Step 1: Decide release policy for `docs\superpowers\plans`**

For open-source release, treat `docs\superpowers\plans` as internal agent execution material. The cleanup task should remove tracked plan files before publishing an external release branch. During local remediation, keep this plan file and old plan file available.

- [ ] **Step 2: Add failing contract test**

Change the existing test in `tests/test_open_source_release_contract.py`:

```python
def test_open_source_files_exist_and_internal_plans_are_removed():
    """开源发布分支不应包含内部 agent 执行计划。"""
    assert (REPO_ROOT / "README.md").exists()
    assert (REPO_ROOT / "LICENSE").exists()
    assert not (REPO_ROOT / "AGENTS.md").exists()
    assert not (REPO_ROOT / "docs" / "plans").exists()
    assert not (REPO_ROOT / "docs" / "superpowers" / "plans").exists()
```

- [ ] **Step 3: Add ignore rule**

Add this line to `.gitignore`:

```gitignore
docs/superpowers/plans/
```

- [ ] **Step 4: Run focused test on a release-clean branch**

Run after removing tracked internal plans from the release-clean branch:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_open_source_release_contract.py::test_open_source_files_exist_and_internal_plans_are_removed -q
```

Expected on a local remediation branch before cleanup: fails while internal plan files are intentionally present. Expected on release-clean branch: passes after internal plans are removed from tracked files.

- [ ] **Step 5: Commit release-clean contract when preparing external release**

Run on the release-clean branch:

```powershell
git rm -- docs\superpowers\plans\2026-04-28-audioblue-review-fixes.md docs\superpowers\plans\2026-05-05-audioblue-global-audit-fixes.md
git add -- .gitignore tests\test_open_source_release_contract.py
git commit -m "chore: 清理开源发布内部计划"
```

---

### Task 12: 修正文档中的打包校验命令

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\docs\DEVELOPMENT.md:90`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\docs\DEVELOPMENT.md:120`

- [ ] **Step 1: Locate current broken commands**

Run:

```powershell
Select-String -LiteralPath '.\docs\DEVELOPMENT.md' -Pattern 'verify_packaging_assets.py' -Context 1,2
```

Expected before implementation: both documented commands are missing `--installer-core-script`.

- [ ] **Step 2: Replace with thin-package verification command**

Use this command in `docs/DEVELOPMENT.md` where WebView2 bundled runtime is not being checked:

```powershell
uv run python scripts\verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --installer-script installer\AudioBlue.WithWebView2.iss --installer-core-script installer\AudioBlue.InstallerCore.iss --format text
```

- [ ] **Step 3: Add bundled WebView2 verification command**

Use this command in the release troubleshooting section:

```powershell
uv run python scripts\verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --installer-script installer\AudioBlue.WithWebView2.iss --installer-core-script installer\AudioBlue.InstallerCore.iss --webview2-runtime-installer dist\webview2\MicrosoftEdgeWebView2RuntimeInstallerX64.exe --format text
```

- [ ] **Step 4: Verify docs no longer contain broken command**

Run:

```powershell
Select-String -LiteralPath '.\docs\DEVELOPMENT.md' -Pattern 'verify_packaging_assets.py' -Context 0,1
```

Expected after implementation: every shown command includes `--installer-core-script installer\AudioBlue.InstallerCore.iss`.

- [ ] **Step 5: Commit docs correction**

Run:

```powershell
git add -- docs\DEVELOPMENT.md
git commit -m "docs: 修正打包校验命令"
```

---

## Final Verification

After completing Tasks 1-12 on an implementation branch, run the verification set below.

- [ ] **Python focused runtime tests**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_session_state.py tests\test_desktop_host_runtime.py tests\test_connector_service_backend.py tests\test_diagnostics.py tests\test_tray_menu_mapping.py -q
```

Expected: all selected Python tests pass.

- [ ] **Python packaging and release contract tests**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_packaging_verification_script.py tests\test_open_source_release_contract.py -q
```

Expected: pass on release-clean branch. On local remediation branch, the internal plan directory assertion can fail until Task 11 cleanup is intentionally applied.

- [ ] **Frontend focused tests**

Run:

```powershell
Push-Location '.\ui'
& '.\node_modules\.bin\vitest.cmd' run --configLoader native --pool threads src\App.integration.test.tsx src\components\TrayQuickPanel.test.tsx
Pop-Location
```

Expected: focused Vitest suites pass.

- [ ] **Frontend full checks**

Run:

```powershell
Push-Location '.\ui'
npm test
npm run lint
npm run build
Pop-Location
```

Expected: Vitest, ESLint and Vite build complete successfully.

- [ ] **Full Python suite**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
```

Expected: full Python suite passes. If local temp permission blocks full pytest on this machine, report the exact `PermissionError` and include the focused passing suites as product-level evidence.

---

## Suggested Commit Batches

- Commit 1: `fix: 隔离状态推送监听器异常`
  - Task 1 files only.
- Commit 2: `fix: 为连接 worker 增加超时保护`
  - Task 2 files only.
- Commit 3: `fix: 观测写入失败时不阻断业务`
  - Task 3 files only.
- Commit 4: `fix: 保底清理托盘宿主资源`
  - Task 4 files only.
- Commit 5: `fix: 收敛离线设备与托盘错误状态`
  - Tasks 5-7 frontend files only.
- Commit 6: `fix: 强化发布版本与 WebView2 校验`
  - Tasks 8-9 files only.
- Commit 7: `ci: 增加日常验证工作流`
  - Task 10 files only.
- Commit 8: `chore: 清理开源发布内部计划`
  - Task 11 on release-clean branch only.
- Commit 9: `docs: 修正打包校验命令`
  - Task 12 files only.

---

## Self-Review

- Spec coverage: all 13 findings are mapped in `Finding Map` and covered by Tasks 1-12.
- Placeholder scan: this plan avoids deferred placeholder wording and includes concrete file paths, commands, test intent and implementation snippets.
- Type consistency: Python tasks use existing `SessionStateCoordinator`, `DesktopHost`, `ConnectorService`, `ObservabilityService`, `TrayHost`; frontend tasks use existing `AppState`, `BackendBridge`, `TrayQuickPanelView`, `useControlCenterModel`; release tasks use existing `build-release.ps1`, Inno template and packaging verification script.
- Execution boundary: this document is planning-only. No runtime fix should be applied until the user explicitly starts implementation.
