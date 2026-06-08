# AudioBlue First-Connect No-Audio Recover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the case where the first Bluetooth audio connection opens successfully but Windows does not create a usable playback endpoint until the user manually disconnects and reconnects.

**Architecture:** Keep the existing WinRT `AudioPlaybackConnection` connection path. Change only the post-connect validation path so a connected-but-no-audio first attempt automatically disconnects and retries once through the existing `recover` trigger, then fails terminally with `connection.no_audio` if the retry still cannot confirm audio.

**Tech Stack:** Python 3.12, WinRT `AudioPlaybackConnection`, Windows Core Audio probing, pytest. All commands below are PowerShell commands run from `E:\Development\Project\PythonProjects\AudioBlue`.

---

## Current Evidence

- Manual connection succeeds at the WinRT layer in `src\audio_blue\connector_service.py` via `AudioPlaybackConnection.try_create_from_id()`, `start_async()`, and `open_async()`.
- After success, `_run_connection_validation()` checks remote AEP, local render endpoint, and audio flow.
- Current behavior intentionally keeps manual connections alive when local render stays inactive or audio flow is unconfirmed. These tests encode that old behavior:
  - `tests\test_connector_service_watcher.py::test_service_keeps_manual_connection_when_render_endpoint_never_becomes_ready_within_grace_window`
  - `tests\test_connector_service_watcher.py::test_service_treats_initial_audio_flow_warmup_as_diagnostics_only`
- The user-reported behavior matches that old behavior: UI sees `connected`, phone sees the PC as output, but Windows has not created the usable audio source until a manual disconnect/reconnect.

## File Map

- Modify: `src\audio_blue\connector_service.py`
  - Add one-shot no-audio recovery inside `_run_connection_validation()`.
  - Reuse `_ValidationChain.recover_used`, `pending_no_audio_recover`, and `last_recover_reason` to avoid infinite reconnects.
  - Reuse `_disconnect_for_no_audio_recover()` and `_handle_no_audio_condition()`.
- Modify: `tests\test_connector_service_watcher.py`
  - Replace old “diagnostics only” expectations for manual no-audio cases.
  - Add a success-after-recover test and keep terminal recover failure coverage.
- Optional modify only if test expectations require wording updates: `tests\test_session_state.py`
  - Existing diagnostic activity mapping already understands `nextAction="recover"`; no planned production change in `session_state.py`.

---

## Task 1: Add Failing Tests for One-Shot No-Audio Recovery

**Files:**
- Modify: `tests\test_connector_service_watcher.py`

- [ ] **Step 1: Replace manual inactive-endpoint old behavior test**

Rename `test_service_keeps_manual_connection_when_render_endpoint_never_becomes_ready_within_grace_window` to `test_service_recovers_manual_connection_when_render_endpoint_never_becomes_ready_within_grace_window` and replace its assertions with this behavior:

```python
def test_service_recovers_manual_connection_when_render_endpoint_never_becomes_ready_within_grace_window():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    route_probe = AudioRouteProbeStub(
        render_snapshots=[
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="inactive",
                is_active=False,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="inactive",
                is_active=False,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="inactive",
                is_active=False,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
        ],
        flow_observations=[
            AudioFlowObservation(
                observed=True,
                peak_max=0.31,
                sample_count=4,
                threshold=0.01,
            )
        ],
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0, 0.0),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("trigger") == "recover"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "observed"
            for item in published
        )
    )

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 1
    assert route_probe.render_snapshot_calls >= 4
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("trigger") == "manual"
        and item.get("details", {}).get("phase") == "audio_flow"
        and item.get("details", {}).get("nextAction") == "recover"
        for item in published
    )
    assert not any(item.get("event") == "device_connection_failed" for item in published)
```

- [ ] **Step 2: Replace manual audio-flow warmup old behavior test**

Rename `test_service_treats_initial_audio_flow_warmup_as_diagnostics_only` to `test_service_recovers_manual_connection_when_audio_flow_stays_unconfirmed` and replace it with:

```python
def test_service_recovers_manual_connection_when_audio_flow_stays_unconfirmed():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    route_probe = AudioRouteProbeStub(
        render_snapshots=[
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
        ],
        flow_observations=[
            AudioFlowObservation(
                observed=False,
                peak_max=0.0,
                sample_count=4,
                threshold=0.01,
            ),
            AudioFlowObservation(
                observed=False,
                peak_max=0.0,
                sample_count=4,
                threshold=0.01,
            ),
            AudioFlowObservation(
                observed=True,
                peak_max=0.27,
                sample_count=4,
                threshold=0.01,
            ),
        ],
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("trigger") == "recover"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "observed"
            for item in published
        )
    )

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 1
    assert route_probe.sampled_render_ids == ["render-1", "render-1", "render-1"]
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("trigger") == "manual"
        and item.get("details", {}).get("phase") == "audio_flow"
        and item.get("details", {}).get("nextAction") == "recover"
        for item in published
    )
    assert not any(item.get("event") == "device_connection_failed" for item in published)
```

- [ ] **Step 3: Add terminal failure test for manual connection after one automatic recover**

Add this test after the previous manual recovery tests:

```python
def test_service_manual_no_audio_recover_fails_terminally_after_one_retry():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=AudioRouteProbeStub(
            render_snapshots=[
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="active",
                    is_active=True,
                ),
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="active",
                    is_active=True,
                ),
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="active",
                    is_active=True,
                ),
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="active",
                    is_active=True,
                ),
            ],
            flow_observations=[
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
            ],
        ),
        remote_aep_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_failed"
            and item.get("failure_code") == "connection.no_audio"
            for item in published
        )
    )

    assert "device-1" not in service.active_connections
    assert service.known_devices["device-1"].connection_state == "failed"
    assert backend.disconnect_calls == 2
    assert sum(1 for item in published if item.get("event") == "device_connection_failed") == 1
    assert published[-1] == {
        "event": "device_connection_failed",
        "device_id": "device-1",
        "state": "failed",
        "trigger": "recover",
        "failure_code": "connection.no_audio",
        "suppress_recover": True,
    }
```

- [ ] **Step 4: Run focused tests and verify failure first**

Run:

```powershell
uv run pytest tests\test_connector_service_watcher.py -q
```

Expected before implementation: the new/changed manual recovery tests fail because current production code does not emit `nextAction="recover"`, does not disconnect, and does not reconnect automatically for manual no-audio validation.

---

## Task 2: Implement One-Shot Recovery in Connector Validation

**Files:**
- Modify: `src\audio_blue\connector_service.py`

- [ ] **Step 1: Add helper to decide and start no-audio recovery**

Add this method near `_handle_no_audio_condition()`:

```python
    def _try_start_no_audio_recover(
        self,
        *,
        device_id: str,
        handle: object,
        trigger: str,
        validation_token: int,
        details: dict[str, object],
    ) -> bool:
        """首次连接无音频时自动断开并重连一次，避免界面停留在假成功状态。"""
        with self._lock:
            chain = self._validation_chains.get(device_id)
            current_handle = self.active_connections.get(device_id)
            if (
                chain is None
                or current_handle is not handle
                or chain.validation_token != validation_token
            ):
                return False
            if trigger == "recover" or chain.recover_used:
                return False
            chain.recover_used = True
            chain.pending_no_audio_recover = True
            chain.last_recover_reason = "no_audio"
            self._audio_routing_state.current_device_id = device_id
            self._audio_routing_state.last_recover_reason = "no_audio"
            self._audio_routing_state.validation_phase = "recovering"

        self._emit_connection_diagnostics(
            device_id=device_id,
            trigger=trigger,
            phase="audio_flow",
            status="unconfirmed",
            details={
                **details,
                "nextAction": "recover",
            },
        )
        self._disconnect_for_no_audio_recover(device_id, handle)
        self.connect(device_id, trigger="recover")
        return True
```

- [ ] **Step 2: Change final no-audio branch in `_run_connection_validation()`**

Replace the existing branch:

```python
            if remote_confirmed and trigger == "recover":
                self._handle_no_audio_condition(
                    device_id=device_id,
                    handle=handle,
                    trigger=trigger,
                    validation_token=validation_token,
                    details=flow_details,
                )
                return
            break
```

with:

```python
            if remote_confirmed:
                if self._try_start_no_audio_recover(
                    device_id=device_id,
                    handle=handle,
                    trigger=trigger,
                    validation_token=validation_token,
                    details=flow_details,
                ):
                    return
                self._handle_no_audio_condition(
                    device_id=device_id,
                    handle=handle,
                    trigger=trigger,
                    validation_token=validation_token,
                    details=flow_details,
                )
                return
            break
```

This keeps remote-unconfirmed cases as diagnostics-only, because those do not prove Windows has accepted the device as the expected audio route.

- [ ] **Step 3: Preserve validation chain across the no-audio recover call**

Update `_prepare_validation_chain_locked()` so a pending no-audio recover keeps the original chain and marks it as used:

```python
    def _prepare_validation_chain_locked(self, device_id: str, trigger: str) -> int:
        self._validation_token_sequence += 1
        validation_token = self._validation_token_sequence
        existing = self._validation_chains.get(device_id)
        if trigger == "recover" and existing is not None and existing.pending_no_audio_recover:
            existing.pending_no_audio_recover = False
            existing.validation_token = validation_token
            existing.outer_trigger = trigger
            return validation_token
        self._validation_chains[device_id] = _ValidationChain(
            validation_token=validation_token,
            outer_trigger=trigger,
        )
        return validation_token
```

- [ ] **Step 4: Run focused connector tests**

Run:

```powershell
uv run pytest tests\test_connector_service_watcher.py -q
```

Expected: all connector watcher tests pass.

---

## Task 3: Verify Session-Level Activity and Failure Recording

**Files:**
- Usually no production change.
- Modify tests only if current assertions need a new focused case: `tests\test_session_state.py`

- [ ] **Step 1: Confirm existing activity mapping covers recovery diagnostics**

Run:

```powershell
uv run pytest tests\test_session_state.py::test_session_state_records_connection_diagnostics_activity_without_marking_failure -q
```

Expected: pass. This confirms manual `audio_flow` diagnostics still do not mark last failure by themselves.

- [ ] **Step 2: Add focused session test only if needed**

If implementation changes produce a session-level regression, add this focused test near `test_session_state_records_connection_diagnostics_activity_without_marking_failure`:

```python
def test_session_state_records_no_audio_recovering_activity_without_failure():
    storage = StorageStub()
    service = ConnectorServiceStub()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="connected",
    )
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=AppConfig()),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=storage,
    )

    service._state_callback(
        {
            "event": "device_connection_diagnostics",
            "device_id": "device-1",
            "trigger": "manual",
            "details": {
                "phase": "audio_flow",
                "status": "unconfirmed",
                "nextAction": "recover",
                "peakMax": 0.0,
                "sampleCount": 8,
                "threshold": 0.01,
            },
        }
    )
    snapshot = session_state.snapshot()

    assert snapshot["devices"][0]["connectionState"] == "connected"
    assert snapshot["lastFailure"] is None
    assert any(
        item["event_type"] == "connection.audio_flow.recovering"
        for item in storage.activity_events
    )
```

- [ ] **Step 3: Run session/app-state focused tests**

Run:

```powershell
uv run pytest tests\test_session_state.py tests\test_app_state.py -q
```

Expected: pass.

---

## Task 4: Full Verification and Commit

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run focused backend suite**

Run:

```powershell
uv run pytest tests\test_connector_service_watcher.py tests\test_session_state.py tests\test_app_state.py -q
```

Expected: pass.

- [ ] **Step 2: Run full Python test suite**

Run:

```powershell
uv run pytest -q
```

Expected: pass. If this is too slow, record the focused command output and explain that full suite was not run.

- [ ] **Step 3: Inspect diff**

Run:

```powershell
git diff -- src\audio_blue\connector_service.py tests\test_connector_service_watcher.py tests\test_session_state.py
```

Expected: diff only changes no-audio validation recovery behavior and tests.

- [ ] **Step 4: Commit if requested**

Only commit if the user asks for a commit. Use:

```powershell
git add src\audio_blue\connector_service.py tests\test_connector_service_watcher.py tests\test_session_state.py docs\superpowers\plans\2026-06-08-audioblue-first-connect-no-audio-recover.md
git commit -m "fix: 自动恢复首次连接无音频端点"
```

---

## Acceptance Criteria

- First manual connection that opens WinRT successfully but cannot confirm local render/audio flow automatically disconnects and reconnects once.
- If the automatic retry creates a usable endpoint/audio flow, UI remains connected and no failure notification is emitted.
- If retry still cannot confirm audio, service disconnects and emits `connection.no_audio` terminal failure.
- Existing startup/reappear connection behavior remains routed through the same validation and one-shot recovery logic.
- Existing abnormal disconnect `recover` loop does not become infinite.
- All new or updated tests pass with PowerShell commands listed above.
