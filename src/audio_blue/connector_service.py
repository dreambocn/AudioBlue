from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from queue import Queue
from threading import Event, Lock, Thread
from time import monotonic, sleep
from typing import Awaitable, Callable, Protocol, TypeVar

from winrt.windows.devices.enumeration import DeviceInformation, DeviceWatcherStatus
from winrt.windows.media.audio import (
    AudioPlaybackConnection,
    AudioPlaybackConnectionOpenResultStatus,
    AudioPlaybackConnectionState,
)

from audio_blue.models import DeviceSummary

StateCallback = Callable[[dict[str, object]], None]
DeviceProvider = Callable[[], list[DeviceSummary]]
ConnectionStateCallback = Callable[[str], None]
WatcherEventCallback = Callable[[dict[str, object]], None]
AwaitableResult = TypeVar("AwaitableResult")
_STABLE_CONNECTION_WINDOW_SECONDS = 1.5


def run_awaitable_blocking(awaitable: Awaitable[AwaitableResult]) -> AwaitableResult:
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
    device_id: str
    connection: AudioPlaybackConnection
    token: object


@dataclass(slots=True)
class WinRTWatcherHandle:
    watcher: object
    added_token: object
    updated_token: object
    removed_token: object
    enumeration_completed_token: object
    stopped_token: object


class ConnectorBackend(Protocol):
    def list_devices(self) -> list[DeviceSummary]: ...

    def connect(
        self,
        device_id: str,
        state_callback: ConnectionStateCallback,
    ) -> tuple[object | None, str]: ...

    def disconnect(self, handle: object) -> None: ...

    def start_watcher(self, callback: WatcherEventCallback) -> object: ...

    def stop_watcher(self, handle: object) -> None: ...


class WinRTConnectorBackend:
    def list_devices(self) -> list[DeviceSummary]:
        selector = get_audio_playback_selector()
        devices = run_awaitable_blocking(
            DeviceInformation.find_all_async_aqs_filter(selector)
        )
        return [
            DeviceSummary(device_id=device.id, name=device.name)
            for device in devices
        ]

    def start_watcher(self, callback: WatcherEventCallback) -> WinRTWatcherHandle:
        watcher = DeviceInformation.create_watcher_aqs_filter(get_audio_playback_selector())

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

        unstable_connection = Event()

        def on_state_changed(sender: AudioPlaybackConnection, _args: object) -> None:
            mapped_state = map_connection_state(sender.state)
            if mapped_state != "connected":
                unstable_connection.set()
            state_callback(mapped_state)

        token = connection.add_state_changed(on_state_changed)

        async def start_and_open() -> str:
            await connection.start_async()
            open_result = await connection.open_async()
            return map_open_result_status(open_result.status)

        state_name = run_awaitable_blocking(start_and_open())
        if state_name == "connected":
            deadline = monotonic() + _STABLE_CONNECTION_WINDOW_SECONDS
            while monotonic() < deadline:
                if unstable_connection.is_set():
                    state_name = "failed"
                    break
                if connection.state != AudioPlaybackConnectionState.OPENED:
                    state_name = "failed"
                    break
                sleep(0.05)

        if state_name != "connected":
            connection.remove_state_changed(token)
            connection.close()
            return None, state_name

        return WinRTConnectionHandle(device_id=device_id, connection=connection, token=token), state_name

    def disconnect(self, handle: WinRTConnectionHandle) -> None:
        handle.connection.remove_state_changed(handle.token)
        handle.connection.close()


@dataclass(slots=True)
class _WorkerJob:
    action: Callable[[], object]
    completed: Event
    result: object | None = None
    error: BaseException | None = None


class ConnectorService:
    def __init__(
        self,
        device_provider: DeviceProvider | None = None,
        state_callback: StateCallback | None = None,
        backend: ConnectorBackend | None = None,
    ) -> None:
        self._device_provider = device_provider
        self._state_callback = state_callback
        self._backend = None if device_provider is not None else (backend or WinRTConnectorBackend())
        self._lock = Lock()
        self.known_devices: dict[str, DeviceSummary] = {}
        self.active_connections: dict[str, object] = {}
        self.is_shutdown = False
        self._jobs: Queue[_WorkerJob | None] | None = None
        self._worker: Thread | None = None
        self._watcher_handle: object | None = None
        self._initial_enumeration_completed = Event()
        self._transient_connection_states: dict[str, str] = {}

        if self._backend is not None:
            self._jobs = Queue()
            self._worker = Thread(target=self._worker_loop, name="audio-blue-connector", daemon=True)
            self._worker.start()
            self._start_device_watcher()
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

        self._emit({"event": "device_state_changed", "device_id": device_id, "state": "connecting"})
        handle, state = self._run_on_worker(
            lambda: self._backend.connect(device_id, lambda mapped: self._handle_connection_state(device_id, mapped))  # type: ignore[union-attr]
        )
        transient_state = self._transient_connection_states.pop(device_id, None)
        final_state = state
        if state == "connected" and transient_state not in {None, "connected", "connecting"}:
            final_state = "failed"
            if handle is not None:
                self._run_on_worker(lambda: self._backend.disconnect(handle))  # type: ignore[union-attr]

        with self._lock:
            device = self.known_devices[device_id]
            self.known_devices[device_id] = replace(device, connection_state=final_state)
            if handle is not None and final_state == "connected":
                self.active_connections[device_id] = handle
            else:
                self.active_connections.pop(device_id, None)

        if final_state == "connected":
            self._emit({"event": "device_connected", "device_id": device_id, "trigger": trigger})
        else:
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
            if device_id in self.known_devices:
                device = self.known_devices[device_id]
                self.known_devices[device_id] = replace(device, connection_state="disconnected")

        self._emit({"event": "device_disconnected", "device_id": device_id, "trigger": trigger})

    def shutdown(self) -> None:
        if self._backend is not None:
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
            self.known_devices[device_id] = replace(device, connection_state=state)
            if state != "connected":
                self.active_connections.pop(device_id, None)

        self._emit({"event": "device_state_changed", "device_id": device_id, "state": state})

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
            self.known_devices[device_id] = replace(
                existing,
                connection_state="disconnected" if had_active_connection else existing.connection_state,
                present_in_last_scan=False,
            )

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
    return DeviceSummary(
        device_id=str(getattr(device, "id")),
        name=str(getattr(device, "name", getattr(device, "id"))),
    )


def _load_device_by_id(device_id: str) -> DeviceSummary | None:
    try:
        device = run_awaitable_blocking(DeviceInformation.create_from_id_async(device_id))
    except Exception:
        return None
    return _device_summary_from_winrt_device(device)
