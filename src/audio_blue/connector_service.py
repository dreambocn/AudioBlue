"""封装 WinRT 设备枚举、连接与后台观察器调度。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from queue import Queue
from time import sleep
from threading import Event, Lock, Thread
from typing import Awaitable, Callable, Protocol, TypeVar

from winrt.windows.devices.enumeration import DeviceInformation, DeviceWatcherStatus
from winrt.windows.foundation import IPropertyValue, PropertyType
from winrt.windows.media.audio import (
    AudioPlaybackConnection,
    AudioPlaybackConnectionOpenResultStatus,
    AudioPlaybackConnectionState,
)

from audio_blue.audio_routing import (
    AudioFlowObservation,
    AudioRouteProbe,
    LocalRenderSnapshot,
    Win32AudioRouteProbe,
)
from audio_blue.models import DeviceSummary

StateCallback = Callable[[dict[str, object]], None]
DeviceProvider = Callable[[], list[DeviceSummary]]
ConnectionStateCallback = Callable[[str], None]
WatcherEventCallback = Callable[[dict[str, object]], None]
AwaitableResult = TypeVar("AwaitableResult")

_DEVICE_REQUESTED_PROPERTIES = (
    "System.Devices.ContainerId",
    "System.Devices.Aep.IsConnected",
    "System.Devices.Aep.IsPresent",
    "System.Devices.Aep.ContainerId",
)
_HEALTH_CHECK_INTERVAL_SECONDS = 2.0
_REMOTE_AEP_DELAY_SECONDS = 2.0
_ENDPOINT_PROBE_DELAY_SECONDS = 0.5
_ENDPOINT_READY_RETRY_DELAYS_SECONDS = (1.0,)
_AUDIO_FLOW_SAMPLE_COUNT = 8
_AUDIO_FLOW_SAMPLE_INTERVAL_SECONDS = 0.5
_AUDIO_FLOW_THRESHOLD = 0.01
_NO_AUDIO_FAILURE_CODE = "connection.no_audio"


@dataclass(slots=True)
class AudioRoutingDiagnosticsState:
    """保存最近一次连接验证得到的音频路由诊断。"""

    current_device_id: str | None = None
    remote_container_id: str | None = None
    remote_aep_connected: bool | None = None
    remote_aep_present: bool | None = None
    local_render_id: str | None = None
    local_render_name: str | None = None
    local_render_state: str | None = None
    audio_flow_observed: bool | None = None
    audio_flow_peak_max: float | None = None
    validation_phase: str | None = None
    last_validated_at: str | None = None
    last_recover_reason: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "currentDeviceId": self.current_device_id,
            "remoteContainerId": self.remote_container_id,
            "remoteAepConnected": self.remote_aep_connected,
            "remoteAepPresent": self.remote_aep_present,
            "localRenderId": self.local_render_id,
            "localRenderName": self.local_render_name,
            "localRenderState": self.local_render_state,
            "audioFlowObserved": self.audio_flow_observed,
            "audioFlowPeakMax": self.audio_flow_peak_max,
            "validationPhase": self.validation_phase,
            "lastValidatedAt": self.last_validated_at,
            "lastRecoverReason": self.last_recover_reason,
        }


@dataclass(slots=True)
class _ValidationChain:
    """跟踪单个设备当前连接验证链的恢复预算。"""

    validation_token: int
    outer_trigger: str
    recover_used: bool = False
    pending_no_audio_recover: bool = False
    last_recover_reason: str | None = None


def run_awaitable_blocking(awaitable: Awaitable[AwaitableResult]) -> AwaitableResult:
    """在同步调用栈中安全等待 WinRT 异步结果。"""

    async def runner() -> AwaitableResult:
        return await awaitable

    return asyncio.run(runner())


def map_open_result_status(status: AudioPlaybackConnectionOpenResultStatus) -> str:
    mapping = {
        AudioPlaybackConnectionOpenResultStatus.SUCCESS: "connected",
        AudioPlaybackConnectionOpenResultStatus.REQUEST_TIMED_OUT: "timeout",
        AudioPlaybackConnectionOpenResultStatus.DENIED_BY_SYSTEM: "denied",
        AudioPlaybackConnectionOpenResultStatus.UNKNOWN_FAILURE: "error",
    }
    return mapping.get(status, "error")


def map_connection_state(state: AudioPlaybackConnectionState) -> str:
    if state == AudioPlaybackConnectionState.OPENED:
        return "connected"
    return "disconnected"


def get_audio_playback_selector() -> str:
    return AudioPlaybackConnection.get_device_selector()


@dataclass(slots=True)
class WinRTConnectionHandle:
    """保存单个连接对象以及关联的 WinRT 事件令牌。"""

    device_id: str
    connection: AudioPlaybackConnection
    token: object


@dataclass(slots=True)
class WinRTWatcherHandle:
    """保存观察器本体和所有已注册事件令牌，方便统一释放。"""

    watcher: object
    added_token: object
    updated_token: object
    removed_token: object
    enumeration_completed_token: object
    stopped_token: object


class ConnectorBackend(Protocol):
    """定义连接服务依赖的后端能力，便于测试替身注入。"""

    def list_devices(self) -> list[DeviceSummary]: ...

    def connect(
        self,
        device_id: str,
        state_callback: ConnectionStateCallback,
    ) -> tuple[object | None, str]: ...

    def disconnect(self, handle: object) -> None: ...

    def probe_connection(self, handle: object) -> str: ...

    def start_watcher(self, callback: WatcherEventCallback) -> object: ...

    def stop_watcher(self, handle: object) -> None: ...


class WinRTConnectorBackend:
    """直接对接 WinRT API，负责真实设备枚举与连接。"""

    def list_devices(self) -> list[DeviceSummary]:
        selector = get_audio_playback_selector()
        devices = run_awaitable_blocking(
            DeviceInformation.find_all_async_aqs_filter_and_additional_properties(
                selector,
                list(_DEVICE_REQUESTED_PROPERTIES),
            )
        )
        return [
            _device_summary_from_winrt_device(device)
            for device in devices
        ]

    def start_watcher(self, callback: WatcherEventCallback) -> WinRTWatcherHandle:
        watcher = DeviceInformation.create_watcher_aqs_filter_and_additional_properties(
            get_audio_playback_selector(),
            list(_DEVICE_REQUESTED_PROPERTIES),
        )

        def on_added(_sender: object, device: object) -> None:
            callback(
                {
                    "change": "added",
                    "device": _device_summary_from_winrt_device(device),
                }
            )

        def on_updated(_sender: object, update: object) -> None:
            device_id = getattr(update, "id", None)
            if not isinstance(device_id, str):
                return
            device = _load_device_by_id(device_id)
            if device is None:
                callback({"change": "updated", "device_id": device_id})
                return
            callback({"change": "updated", "device": device})

        def on_removed(_sender: object, update: object) -> None:
            device_id = getattr(update, "id", None)
            if isinstance(device_id, str):
                callback({"change": "removed", "device_id": device_id})

        def on_enumeration_completed(_sender: object, _args: object) -> None:
            callback({"change": "enumeration_completed"})

        def on_stopped(_sender: object, _args: object) -> None:
            callback({"change": "stopped"})

        handle = WinRTWatcherHandle(
            watcher=watcher,
            added_token=watcher.add_added(on_added),
            updated_token=watcher.add_updated(on_updated),
            removed_token=watcher.add_removed(on_removed),
            enumeration_completed_token=watcher.add_enumeration_completed(on_enumeration_completed),
            stopped_token=watcher.add_stopped(on_stopped),
        )
        # 只有在所有回调都挂好之后再启动观察器，避免丢失首批事件。
        watcher.start()
        return handle

    def stop_watcher(self, handle: WinRTWatcherHandle) -> None:
        handle.watcher.remove_added(handle.added_token)
        handle.watcher.remove_updated(handle.updated_token)
        handle.watcher.remove_removed(handle.removed_token)
        handle.watcher.remove_enumeration_completed(handle.enumeration_completed_token)
        handle.watcher.remove_stopped(handle.stopped_token)
        status = getattr(handle.watcher, "status", None)
        if status not in {DeviceWatcherStatus.STOPPED, DeviceWatcherStatus.ABORTED}:
            handle.watcher.stop()

    def connect(
        self,
        device_id: str,
        state_callback: ConnectionStateCallback,
    ) -> tuple[WinRTConnectionHandle | None, str]:
        connection = AudioPlaybackConnection.try_create_from_id(device_id)
        if connection is None:
            return None, "error"

        def on_state_changed(sender: AudioPlaybackConnection, _args: object) -> None:
            mapped_state = map_connection_state(sender.state)
            state_callback(mapped_state)

        token = connection.add_state_changed(on_state_changed)

        async def start_and_open() -> str:
            await connection.start_async()
            open_result = await connection.open_async()
            return map_open_result_status(open_result.status)

        state_name = run_awaitable_blocking(start_and_open())
        if state_name != "connected":
            connection.remove_state_changed(token)
            connection.close()
            return None, state_name

        return WinRTConnectionHandle(device_id=device_id, connection=connection, token=token), state_name

    def disconnect(self, handle: WinRTConnectionHandle) -> None:
        handle.connection.remove_state_changed(handle.token)
        handle.connection.close()

    def probe_connection(self, handle: WinRTConnectionHandle) -> str:
        try:
            mapped_state = map_connection_state(handle.connection.state)
        except Exception:
            return "error"
        return "connected" if mapped_state == "connected" else "stale"


@dataclass(slots=True)
class _WorkerJob:
    action: Callable[[], object]
    completed: Event
    result: object | None = None
    error: BaseException | None = None


class ConnectorService:
    """向上层提供线程安全的设备刷新、连接和观察器事件整合能力。"""

    def __init__(
        self,
        device_provider: DeviceProvider | None = None,
        state_callback: StateCallback | None = None,
        backend: ConnectorBackend | None = None,
        endpoint_probe: object | None = None,
        audio_route_probe: AudioRouteProbe | None = None,
        health_check_interval_seconds: float = _HEALTH_CHECK_INTERVAL_SECONDS,
        endpoint_ready_retry_delays_seconds: tuple[float, ...] = _ENDPOINT_READY_RETRY_DELAYS_SECONDS,
        endpoint_probe_delay_seconds: float = _ENDPOINT_PROBE_DELAY_SECONDS,
        remote_aep_delay_seconds: float = _REMOTE_AEP_DELAY_SECONDS,
        audio_flow_sample_count: int = _AUDIO_FLOW_SAMPLE_COUNT,
        audio_flow_sample_interval_seconds: float = _AUDIO_FLOW_SAMPLE_INTERVAL_SECONDS,
        audio_flow_threshold: float = _AUDIO_FLOW_THRESHOLD,
    ) -> None:
        self._device_provider = device_provider
        self._state_callback = state_callback
        self._backend = None if device_provider is not None else (backend or WinRTConnectorBackend())
        # 兼容旧调用方保留参数，但新的连接判断不再使用名称端点探测。
        self._legacy_endpoint_probe = endpoint_probe
        self._audio_route_probe = audio_route_probe or Win32AudioRouteProbe()
        self._health_check_interval_seconds = max(0.0, float(health_check_interval_seconds))
        self._endpoint_ready_retry_delays_seconds = tuple(endpoint_ready_retry_delays_seconds)
        self._endpoint_probe_delay_seconds = float(endpoint_probe_delay_seconds)
        self._remote_aep_delay_seconds = max(0.0, float(remote_aep_delay_seconds))
        self._audio_flow_sample_count = max(0, int(audio_flow_sample_count))
        self._audio_flow_sample_interval_seconds = max(
            0.0,
            float(audio_flow_sample_interval_seconds),
        )
        self._audio_flow_threshold = max(0.0, float(audio_flow_threshold))
        self._lock = Lock()
        self.known_devices: dict[str, DeviceSummary] = {}
        self.active_connections: dict[str, object] = {}
        self.is_shutdown = False
        self._jobs: Queue[_WorkerJob | None] | None = None
        self._worker: Thread | None = None
        self._health_check_thread: Thread | None = None
        self._health_check_shutdown = Event()
        self._watcher_handle: object | None = None
        self._initial_enumeration_completed = Event()
        self._transient_connection_states: dict[str, str] = {}
        self._validation_token_sequence = 0
        self._validation_chains: dict[str, _ValidationChain] = {}
        self._audio_routing_state = AudioRoutingDiagnosticsState()

        if self._backend is not None:
            self._jobs = Queue()
            self._worker = Thread(target=self._worker_loop, name="audio-blue-connector", daemon=True)
            self._worker.start()
            self._start_device_watcher()
            self._start_health_check_loop()
        else:
            self._initial_enumeration_completed.set()

    def refresh_devices(self) -> list[DeviceSummary]:
        if self._device_provider is not None:
            devices = self._device_provider()
        else:
            devices = self._run_on_worker(self._backend.list_devices)  # type: ignore[union-attr]
        seen_at = datetime.now(UTC)

        with self._lock:
            existing_devices = self.known_devices
            next_devices: dict[str, DeviceSummary] = {}
            for device in devices:
                existing = existing_devices.get(device.device_id)
                merged = replace(
                    device,
                    connection_state="connected"
                    if device.device_id in self.active_connections
                    else device.connection_state,
                    present_in_last_scan=True,
                    container_id=device.container_id or (existing.container_id if existing else None),
                    aep_is_connected=(
                        device.aep_is_connected
                        if device.aep_is_connected is not None
                        else existing.aep_is_connected if existing else None
                    ),
                    aep_is_present=(
                        device.aep_is_present
                        if device.aep_is_present is not None
                        else existing.aep_is_present if existing else None
                    ),
                    last_seen_at=seen_at,
                    last_connection_attempt=(
                        device.last_connection_attempt
                        or (existing.last_connection_attempt if existing else None)
                    ),
                )
                next_devices[device.device_id] = merged

            for device_id in self.active_connections:
                if device_id in next_devices:
                    continue
                existing = existing_devices.get(device_id)
                if existing is None:
                    continue
                next_devices[device_id] = replace(
                    existing,
                    connection_state="connected",
                    present_in_last_scan=False,
                    aep_is_present=False,
                )

            self.known_devices = next_devices

        self._initial_enumeration_completed.set()
        self._emit({"event": "devices_refreshed", "device_ids": list(self.known_devices)})
        return list(self.known_devices.values())

    def connect(self, device_id: str, *, trigger: str = "manual") -> None:
        if self._device_provider is not None:
            device = self.known_devices[device_id]
            self.active_connections[device_id] = object()
            self.known_devices[device_id] = replace(device, connection_state="connected")
            self._emit({"event": "device_connected", "device_id": device_id, "trigger": trigger})
            return

        with self._lock:
            device = self.known_devices[device_id]
            self.known_devices[device_id] = replace(device, connection_state="connecting")
            self._transient_connection_states.pop(device_id, None)
            validation_token = self._prepare_validation_chain_locked(device_id, trigger)
            self._audio_routing_state.current_device_id = device_id
            self._audio_routing_state.validation_phase = "connecting"
            self._audio_routing_state.last_recover_reason = (
                self._validation_chains[device_id].last_recover_reason
            )

        self._emit({"event": "device_state_changed", "device_id": device_id, "state": "connecting"})
        handle, state = self._run_on_worker(
            lambda: self._backend.connect(  # type: ignore[union-attr]
                device_id,
                lambda mapped: self._handle_connection_state(device_id, mapped),
            )
        )
        transient_state = self._transient_connection_states.pop(device_id, None)
        final_state = state
        if state == "connected" and transient_state not in {None, "connected", "connecting"}:
            final_state = "failed"
            if handle is not None:
                self._run_on_worker(lambda: self._backend.disconnect(handle))  # type: ignore[union-attr]

        with self._lock:
            device = self.known_devices[device_id]
            self.known_devices[device_id] = replace(
                device,
                connection_state=final_state,
                aep_is_connected=True if final_state == "connected" else device.aep_is_connected,
                aep_is_present=True if final_state == "connected" else device.aep_is_present,
            )
            if handle is not None and final_state == "connected":
                self.active_connections[device_id] = handle
            else:
                self.active_connections.pop(device_id, None)
                self._clear_validation_chain_locked(device_id)

        if final_state == "connected":
            self._emit({"event": "device_connected", "device_id": device_id, "trigger": trigger})
            if handle is not None:
                self._schedule_connection_validation(
                    device_id=device_id,
                    handle=handle,
                    trigger=trigger,
                    validation_token=validation_token,
                )
            return

        self._emit(
            {
                "event": "device_connection_failed",
                "device_id": device_id,
                "state": final_state,
                "trigger": trigger,
            }
        )

    def disconnect(self, device_id: str, *, trigger: str = "manual") -> None:
        if self._device_provider is not None:
            device = self.known_devices[device_id]
            self.active_connections.pop(device_id, None)
            self.known_devices[device_id] = replace(device, connection_state="disconnected")
            self._emit({"event": "device_disconnected", "device_id": device_id, "trigger": trigger})
            return

        handle = self.active_connections.pop(device_id, None)
        if handle is not None:
            self._run_on_worker(lambda: self._backend.disconnect(handle))  # type: ignore[union-attr]

        with self._lock:
            self._clear_validation_chain_locked(device_id)
            if device_id in self.known_devices:
                device = self.known_devices[device_id]
                self.known_devices[device_id] = replace(
                    device,
                    connection_state="disconnected",
                    aep_is_connected=False,
                )
                if self._audio_routing_state.current_device_id == device_id:
                    self._audio_routing_state.validation_phase = "disconnected"
                    if trigger == "manual":
                        self._audio_routing_state.current_device_id = None

        self._emit({"event": "device_disconnected", "device_id": device_id, "trigger": trigger})

    def poll_connection_health(self) -> None:
        if self._device_provider is not None or self._backend is None:
            return

        for device_id, handle in list(self.active_connections.items()):
            state = self._run_on_worker(lambda handle=handle: self._backend.probe_connection(handle))
            if state == "connected":
                continue
            self._mark_connection_stale(device_id, handle)

    def shutdown(self) -> None:
        if self._backend is not None:
            self._health_check_shutdown.set()
            if self._health_check_thread is not None:
                self._health_check_thread.join(timeout=5)
            for device_id in list(self.active_connections):
                self.disconnect(device_id)

            if self._watcher_handle is not None:
                self._run_on_worker(self._stop_device_watcher)
            if self._jobs is not None:
                self._jobs.put(None)
            if self._worker is not None:
                self._worker.join(timeout=5)

        self.active_connections.clear()
        self.is_shutdown = True
        self._emit({"event": "service_shutdown"})

    def _handle_connection_state(self, device_id: str, state: str) -> None:
        with self._lock:
            device = self.known_devices.get(device_id)
            if device is None:
                return

            self._transient_connection_states[device_id] = state
            self.known_devices[device_id] = replace(
                device,
                connection_state=state,
                aep_is_connected=True if state == "connected" else False,
            )
            if state != "connected":
                self.active_connections.pop(device_id, None)
                self._clear_validation_chain_locked(device_id)
                if self._audio_routing_state.current_device_id == device_id:
                    self._audio_routing_state.validation_phase = state

        self._emit({"event": "device_state_changed", "device_id": device_id, "state": state})

    def _mark_connection_stale(
        self,
        device_id: str,
        handle: object,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        with self._lock:
            existing_handle = self.active_connections.get(device_id)
            if existing_handle is not handle:
                return

        self._run_on_worker(lambda: self._backend.disconnect(handle))  # type: ignore[union-attr]

        with self._lock:
            self.active_connections.pop(device_id, None)
            self._clear_validation_chain_locked(device_id)
            device = self.known_devices.get(device_id)
            if device is not None:
                self.known_devices[device_id] = replace(
                    device,
                    connection_state="stale",
                    aep_is_connected=False,
                )
            if self._audio_routing_state.current_device_id == device_id:
                self._audio_routing_state.validation_phase = "stale"

        payload: dict[str, object] = {
            "event": "device_state_changed",
            "device_id": device_id,
            "state": "stale",
            "trigger": "health_check",
        }
        if details:
            payload["details"] = details
        self._emit(payload)

    def wait_for_initial_enumeration(self, timeout: float = 5.0) -> bool:
        if self._device_provider is not None:
            return True
        return self._initial_enumeration_completed.wait(timeout=max(timeout, 0))

    def has_completed_initial_enumeration(self) -> bool:
        if self._device_provider is not None:
            return True
        return self._initial_enumeration_completed.is_set()

    def _start_device_watcher(self) -> None:
        start_watcher = getattr(self._backend, "start_watcher", None)
        if not callable(start_watcher):
            self._initial_enumeration_completed.set()
            return
        self._watcher_handle = self._run_on_worker(
            lambda: start_watcher(self._handle_device_watcher_event)
        )

    def _start_health_check_loop(self) -> None:
        if self._health_check_interval_seconds <= 0:
            return
        self._health_check_thread = Thread(
            target=self._health_check_loop,
            name="audio-blue-health-check",
            daemon=True,
        )
        self._health_check_thread.start()

    def _health_check_loop(self) -> None:
        while not self._health_check_shutdown.wait(self._health_check_interval_seconds):
            if self.is_shutdown:
                return
            try:
                self.poll_connection_health()
            except Exception:
                continue

    def get_audio_routing_diagnostics(self) -> dict[str, object]:
        with self._lock:
            return dict(self._audio_routing_state.to_payload())

    def _schedule_connection_validation(
        self,
        *,
        device_id: str,
        handle: object,
        trigger: str,
        validation_token: int,
    ) -> None:
        def runner() -> None:
            self._run_connection_validation(
                device_id=device_id,
                handle=handle,
                trigger=trigger,
                validation_token=validation_token,
            )

        Thread(
            target=runner,
            name=f"audio-blue-connection-validation-{device_id}",
            daemon=True,
        ).start()

    def _run_connection_validation(
        self,
        *,
        device_id: str,
        handle: object,
        trigger: str,
        validation_token: int,
    ) -> None:
        if self._remote_aep_delay_seconds > 0:
            sleep(self._remote_aep_delay_seconds)
        if not self._is_validation_current(device_id, handle, validation_token):
            return
        attempt_delays = self._build_validation_attempt_delays()

        for attempt_index, delay_seconds in enumerate(attempt_delays):
            if delay_seconds > 0:
                sleep(delay_seconds)
            if not self._is_validation_current(device_id, handle, validation_token):
                return

            remote_details = self._build_remote_aep_details(device_id)
            remote_confirmed = (
                remote_details["aepConnected"] is True and remote_details["aepPresent"] is True
            )
            remote_status = "confirmed" if remote_confirmed else "unconfirmed"
            self._update_audio_routing_state(
                device_id=device_id,
                phase="remote_aep",
                remote_details=remote_details,
            )
            self._emit_connection_diagnostics(
                device_id=device_id,
                trigger=trigger,
                phase="remote_aep",
                status=remote_status,
                details=remote_details,
            )
            if not self._is_validation_current(device_id, handle, validation_token):
                return

            try:
                render_snapshot = self._audio_route_probe.get_default_render_snapshot()
            except Exception as exc:
                render_snapshot = LocalRenderSnapshot(
                    render_id=None,
                    render_name=None,
                    render_state="error",
                    is_active=False,
                    error=f"render_snapshot:{type(exc).__name__}",
                )
            local_status = "active" if render_snapshot.is_active else (
                "error" if render_snapshot.render_state == "error" else "inactive"
            )
            self._update_audio_routing_state(
                device_id=device_id,
                phase="local_render",
                render_snapshot=render_snapshot,
            )
            self._emit_connection_diagnostics(
                device_id=device_id,
                trigger=trigger,
                phase="local_render",
                status=local_status,
                details=render_snapshot.to_details(),
            )
            if not self._is_validation_current(device_id, handle, validation_token):
                return

            if render_snapshot.is_active and render_snapshot.render_id:
                try:
                    flow_observation = self._audio_route_probe.sample_audio_flow(
                        render_id=render_snapshot.render_id,
                        sample_count=self._audio_flow_sample_count,
                        sample_interval_seconds=self._audio_flow_sample_interval_seconds,
                        threshold=self._audio_flow_threshold,
                    )
                except Exception as exc:
                    flow_observation = AudioFlowObservation(
                        observed=False,
                        peak_max=0.0,
                        sample_count=0,
                        threshold=self._audio_flow_threshold,
                        error=f"audio_flow:{type(exc).__name__}",
                    )
            else:
                flow_observation = AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=0,
                    threshold=self._audio_flow_threshold,
                    error="render_inactive",
                )

            strong_state = self._run_on_worker(
                lambda handle=handle: self._backend.probe_connection(handle)  # type: ignore[union-attr]
            )
            has_more_attempts = attempt_index < len(attempt_delays) - 1
            audio_ready = render_snapshot.is_active and flow_observation.observed
            should_wait = strong_state == "connected" and not (remote_confirmed and audio_ready)
            flow_status = (
                "observed"
                if flow_observation.observed
                else "error"
                if flow_observation.error is not None and not render_snapshot.is_active
                else "unconfirmed"
                if flow_observation.error is None
                else "error"
            )
            flow_details = {
                **flow_observation.to_details(),
                "renderId": render_snapshot.render_id,
                "renderName": render_snapshot.render_name,
                "renderState": render_snapshot.render_state,
            }
            if should_wait and has_more_attempts:
                flow_details["nextAction"] = "wait"

            self._update_audio_routing_state(
                device_id=device_id,
                phase="audio_flow",
                flow_observation=flow_observation,
            )
            self._emit_connection_diagnostics(
                device_id=device_id,
                trigger=trigger,
                phase="audio_flow",
                status=flow_status,
                details=flow_details,
            )
            if not self._is_validation_current(device_id, handle, validation_token):
                return

            if strong_state != "connected":
                break
            if remote_confirmed and audio_ready:
                with self._lock:
                    if self._audio_routing_state.current_device_id == device_id:
                        self._audio_routing_state.validation_phase = "completed"
                    self._clear_validation_chain_locked(device_id)
                return
            if has_more_attempts:
                continue
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

        with self._lock:
            if self._audio_routing_state.current_device_id == device_id:
                self._audio_routing_state.validation_phase = "completed"
            self._clear_validation_chain_locked(device_id)

    def _stop_device_watcher(self) -> None:
        stop_watcher = getattr(self._backend, "stop_watcher", None)
        if not callable(stop_watcher) or self._watcher_handle is None:
            return
        stop_watcher(self._watcher_handle)
        self._watcher_handle = None

    def _handle_device_watcher_event(self, payload: dict[str, object]) -> None:
        change = payload.get("change")
        if change == "enumeration_completed":
            self._initial_enumeration_completed.set()
            self._emit({"event": "device_watcher_enumeration_completed"})
            return
        if change == "stopped":
            return
        if change == "removed":
            device_id = payload.get("device_id")
            if isinstance(device_id, str):
                self._mark_device_absent(device_id, change="removed")
            return

        device = payload.get("device")
        if isinstance(device, DeviceSummary):
            self._merge_watcher_device(device, change=str(change or "updated"))
            return

        device_id = payload.get("device_id")
        if isinstance(device_id, str):
            resolved = self._resolve_device_by_id(device_id)
            if resolved is not None:
                self._merge_watcher_device(resolved, change=str(change or "updated"))

    def _resolve_device_by_id(self, device_id: str) -> DeviceSummary | None:
        devices = self._backend.list_devices() if self._backend is not None else []
        for device in devices:
            if device.device_id == device_id:
                return device
        return None

    def _merge_watcher_device(self, device: DeviceSummary, *, change: str) -> None:
        seen_at = datetime.now(UTC)
        with self._lock:
            existing = self.known_devices.get(device.device_id)
            previous_present = bool(existing.present_in_last_scan) if existing is not None else False
            connection_state = (
                "connected"
                if device.device_id in self.active_connections
                else (
                    existing.connection_state
                    if existing is not None and existing.connection_state in {"connecting", "failed"}
                    else device.connection_state
                )
            )
            self.known_devices[device.device_id] = replace(
                device,
                connection_state=connection_state,
                present_in_last_scan=True,
                container_id=device.container_id or (existing.container_id if existing is not None else None),
                aep_is_connected=(
                    True
                    if device.device_id in self.active_connections
                    else device.aep_is_connected
                    if device.aep_is_connected is not None
                    else existing.aep_is_connected if existing is not None else None
                ),
                aep_is_present=(
                    True
                    if device.aep_is_present is None
                    else device.aep_is_present
                ),
                last_seen_at=seen_at,
                last_connection_attempt=(
                    device.last_connection_attempt
                    or (existing.last_connection_attempt if existing is not None else None)
                ),
            )

        self._emit(
            {
                "event": "device_presence_changed",
                "device_id": device.device_id,
                "present": True,
                "previous_present": previous_present,
                "change": change,
            }
        )

    def _mark_device_absent(self, device_id: str, *, change: str) -> None:
        with self._lock:
            existing = self.known_devices.get(device_id)
            if existing is None:
                return
            previous_present = existing.present_in_last_scan
            had_active_connection = device_id in self.active_connections
            self.active_connections.pop(device_id, None)
            self._clear_validation_chain_locked(device_id)
            self.known_devices[device_id] = replace(
                existing,
                connection_state="disconnected" if had_active_connection else existing.connection_state,
                present_in_last_scan=False,
                aep_is_present=False,
                aep_is_connected=False if had_active_connection else existing.aep_is_connected,
            )
            if self._audio_routing_state.current_device_id == device_id:
                self._audio_routing_state.validation_phase = "disconnected"

        self._emit(
            {
                "event": "device_presence_changed",
                "device_id": device_id,
                "present": False,
                "previous_present": previous_present,
                "change": change,
            }
        )
        if had_active_connection:
            self._emit({"event": "device_state_changed", "device_id": device_id, "state": "disconnected"})

    def _prepare_validation_chain_locked(self, device_id: str, trigger: str) -> int:
        self._validation_token_sequence += 1
        validation_token = self._validation_token_sequence
        existing = self._validation_chains.get(device_id)
        if trigger == "recover" and existing is not None and existing.pending_no_audio_recover:
            existing.pending_no_audio_recover = False
            existing.validation_token = validation_token
            return validation_token
        self._validation_chains[device_id] = _ValidationChain(
            validation_token=validation_token,
            outer_trigger=trigger,
        )
        return validation_token

    def _clear_validation_chain_locked(self, device_id: str) -> None:
        self._validation_chains.pop(device_id, None)

    def _is_validation_current(self, device_id: str, handle: object, validation_token: int) -> bool:
        with self._lock:
            if self.is_shutdown:
                return False
            current_handle = self.active_connections.get(device_id)
            chain = self._validation_chains.get(device_id)
            return (
                current_handle is handle
                and chain is not None
                and chain.validation_token == validation_token
            )

    def _build_remote_aep_details(self, device_id: str) -> dict[str, object]:
        with self._lock:
            device = self.known_devices.get(device_id)
            if device is None:
                return {
                    "containerId": None,
                    "aepConnected": None,
                    "aepPresent": None,
                }
            return {
                "containerId": device.container_id,
                "aepConnected": (
                    device.aep_is_connected
                    if device.aep_is_connected is not None
                    else device.device_id in self.active_connections
                ),
                "aepPresent": (
                    device.aep_is_present
                    if device.aep_is_present is not None
                    else device.present_in_last_scan
                ),
            }

    def _update_audio_routing_state(
        self,
        *,
        device_id: str,
        phase: str,
        remote_details: dict[str, object] | None = None,
        render_snapshot: LocalRenderSnapshot | None = None,
        flow_observation: AudioFlowObservation | None = None,
    ) -> None:
        with self._lock:
            self._audio_routing_state.current_device_id = device_id
            self._audio_routing_state.validation_phase = phase
            self._audio_routing_state.last_validated_at = datetime.now(UTC).isoformat()
            if remote_details is not None:
                self._audio_routing_state.remote_container_id = _string_or_none(
                    remote_details.get("containerId")
                )
                self._audio_routing_state.remote_aep_connected = _bool_or_none(
                    remote_details.get("aepConnected")
                )
                self._audio_routing_state.remote_aep_present = _bool_or_none(
                    remote_details.get("aepPresent")
                )
            if render_snapshot is not None:
                self._audio_routing_state.local_render_id = render_snapshot.render_id
                self._audio_routing_state.local_render_name = render_snapshot.render_name
                self._audio_routing_state.local_render_state = render_snapshot.render_state
            if flow_observation is not None:
                self._audio_routing_state.audio_flow_observed = flow_observation.observed
                self._audio_routing_state.audio_flow_peak_max = round(
                    flow_observation.peak_max,
                    6,
                )

    def _build_validation_attempt_delays(self) -> tuple[float, ...]:
        """构建连接成功后的验证轮询窗口，至少执行一次本地验证。"""
        delays = [self._endpoint_probe_delay_seconds, *self._endpoint_ready_retry_delays_seconds]
        if not delays:
            return (0.0,)
        return tuple(max(0.0, float(delay)) for delay in delays)

    def _emit_connection_diagnostics(
        self,
        *,
        device_id: str,
        trigger: str,
        phase: str,
        status: str,
        details: dict[str, object],
    ) -> None:
        self._emit(
            {
                "event": "device_connection_diagnostics",
                "device_id": device_id,
                "trigger": trigger,
                "details": {
                    "phase": phase,
                    "status": status,
                    **details,
                },
            }
        )

    def _handle_no_audio_condition(
        self,
        *,
        device_id: str,
        handle: object,
        trigger: str,
        validation_token: int,
        details: dict[str, object],
    ) -> None:
        with self._lock:
            chain = self._validation_chains.get(device_id)
            current_handle = self.active_connections.get(device_id)
            if (
                chain is None
                or current_handle is not handle
                or chain.validation_token != validation_token
            ):
                return
            self._audio_routing_state.current_device_id = device_id
            self._audio_routing_state.last_recover_reason = "no_audio"
            chain.last_recover_reason = "no_audio"
            self._clear_validation_chain_locked(device_id)
            self._audio_routing_state.validation_phase = "failed"

        self._emit_connection_diagnostics(
            device_id=device_id,
            trigger=trigger,
            phase="audio_flow",
            status="error",
            details={
                **details,
                "nextAction": "fail",
            },
        )
        self._finalize_no_audio_failure(device_id=device_id, handle=handle, trigger=trigger)

    def _disconnect_for_no_audio_recover(self, device_id: str, handle: object) -> None:
        with self._lock:
            current_handle = self.active_connections.get(device_id)
            if current_handle is not handle:
                return
        self._run_on_worker(lambda: self._backend.disconnect(handle))  # type: ignore[union-attr]
        with self._lock:
            self.active_connections.pop(device_id, None)
            device = self.known_devices.get(device_id)
            if device is not None:
                self.known_devices[device_id] = replace(
                    device,
                    connection_state="disconnected",
                    aep_is_connected=False,
                )
        self._emit(
            {
                "event": "device_disconnected",
                "device_id": device_id,
                "trigger": "no_audio_validation",
            }
        )

    def _finalize_no_audio_failure(self, *, device_id: str, handle: object, trigger: str) -> None:
        with self._lock:
            current_handle = self.active_connections.get(device_id)
            if current_handle is not handle:
                return
        self._run_on_worker(lambda: self._backend.disconnect(handle))  # type: ignore[union-attr]
        with self._lock:
            self.active_connections.pop(device_id, None)
            device = self.known_devices.get(device_id)
            if device is not None:
                self.known_devices[device_id] = replace(
                    device,
                    connection_state="failed",
                    aep_is_connected=False,
                )
            self._audio_routing_state.current_device_id = device_id
            self._audio_routing_state.validation_phase = "failed"
        self._emit(
            {
                "event": "device_connection_failed",
                "device_id": device_id,
                "state": "failed",
                "trigger": trigger,
                "failure_code": _NO_AUDIO_FAILURE_CODE,
                "suppress_recover": True,
            }
        )

    def _run_on_worker(self, action: Callable[[], object]) -> object:
        if self._jobs is None:
            return action()

        job = _WorkerJob(action=action, completed=Event())
        self._jobs.put(job)
        job.completed.wait()

        if job.error is not None:
            raise job.error

        return job.result

    def _worker_loop(self) -> None:
        assert self._jobs is not None

        while True:
            job = self._jobs.get()
            if job is None:
                break

            try:
                job.result = job.action()
            except BaseException as exc:
                job.error = exc
            finally:
                job.completed.set()

    def _emit(self, payload: dict[str, object]) -> None:
        if self._state_callback is not None:
            self._state_callback(payload)


def _device_summary_from_winrt_device(device: object) -> DeviceSummary:
    properties = _coerce_device_properties(getattr(device, "properties", None))
    container_id = _read_guid_property(
        properties,
        "System.Devices.Aep.ContainerId",
        fallback_key="System.Devices.ContainerId",
    )
    return DeviceSummary(
        device_id=str(getattr(device, "id")),
        name=str(getattr(device, "name", getattr(device, "id"))),
        container_id=container_id,
        aep_is_connected=_read_bool_property(properties, "System.Devices.Aep.IsConnected"),
        aep_is_present=_read_bool_property(properties, "System.Devices.Aep.IsPresent"),
    )


def _load_device_by_id(device_id: str) -> DeviceSummary | None:
    try:
        device = run_awaitable_blocking(
            DeviceInformation.create_from_id_async_additional_properties(
                device_id,
                list(_DEVICE_REQUESTED_PROPERTIES),
            )
        )
    except Exception:
        return None
    return _device_summary_from_winrt_device(device)


def _coerce_device_properties(value: object) -> dict[str, object]:
    try:
        return dict(value) if value is not None else {}
    except Exception:
        return {}


def _read_bool_property(properties: dict[str, object], key: str) -> bool | None:
    raw_value = properties.get(key)
    if raw_value is None:
        return None
    property_value = _as_property_value(raw_value)
    if property_value is None:
        if isinstance(raw_value, bool):
            return raw_value
        return None
    if property_value.type == PropertyType.BOOLEAN:
        return bool(property_value.get_boolean())
    return None


def _read_guid_property(
    properties: dict[str, object],
    key: str,
    *,
    fallback_key: str | None = None,
) -> str | None:
    raw_value = properties.get(key)
    if raw_value is None and fallback_key is not None:
        raw_value = properties.get(fallback_key)
    if raw_value is None:
        return None
    property_value = _as_property_value(raw_value)
    if property_value is None:
        return _string_or_none(raw_value)
    if property_value.type == PropertyType.GUID:
        return str(property_value.get_guid())
    if property_value.type == PropertyType.STRING:
        return property_value.get_string()
    return None


def _as_property_value(value: object):
    try:
        return value.as_(IPropertyValue)
    except Exception:
        return None


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None
