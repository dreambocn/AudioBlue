from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from queue import Queue
from threading import Event, Lock, Thread
from typing import Awaitable, Callable, Protocol, TypeVar

from winrt.windows.devices.enumeration import DeviceInformation
from winrt.windows.media.audio import (
    AudioPlaybackConnection,
    AudioPlaybackConnectionOpenResultStatus,
    AudioPlaybackConnectionState,
)

from audio_blue.models import DeviceSummary

StateCallback = Callable[[dict[str, object]], None]
DeviceProvider = Callable[[], list[DeviceSummary]]
ConnectionStateCallback = Callable[[str], None]
AwaitableResult = TypeVar("AwaitableResult")


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


class ConnectorBackend(Protocol):
    def list_devices(self) -> list[DeviceSummary]: ...

    def connect(
        self,
        device_id: str,
        state_callback: ConnectionStateCallback,
    ) -> tuple[object | None, str]: ...

    def disconnect(self, handle: object) -> None: ...


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

    def connect(
        self,
        device_id: str,
        state_callback: ConnectionStateCallback,
    ) -> tuple[WinRTConnectionHandle | None, str]:
        connection = AudioPlaybackConnection.try_create_from_id(device_id)
        if connection is None:
            return None, "error"

        def on_state_changed(sender: AudioPlaybackConnection, _args: object) -> None:
            state_callback(map_connection_state(sender.state))

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

        if self._backend is not None:
            self._jobs = Queue()
            self._worker = Thread(target=self._worker_loop, name="audio-blue-connector", daemon=True)
            self._worker.start()

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

        self._emit({"event": "devices_refreshed", "device_ids": list(self.known_devices)})
        return list(self.known_devices.values())

    def connect(self, device_id: str, *, trigger: str = "manual") -> None:
        if self._device_provider is not None:
            device = self.known_devices[device_id]
            self.active_connections[device_id] = object()
            self.known_devices[device_id] = replace(device, connection_state="connected")
            self._emit({"event": "device_connected", "device_id": device_id, "trigger": trigger})
            return

        handle, state = self._run_on_worker(
            lambda: self._backend.connect(device_id, lambda mapped: self._handle_connection_state(device_id, mapped))  # type: ignore[union-attr]
        )

        with self._lock:
            device = self.known_devices[device_id]
            self.known_devices[device_id] = replace(device, connection_state=state)
            if handle is not None and state == "connected":
                self.active_connections[device_id] = handle
            else:
                self.active_connections.pop(device_id, None)

        if state == "connected":
            self._emit({"event": "device_connected", "device_id": device_id, "trigger": trigger})
        else:
            self._emit(
                {
                    "event": "device_connection_failed",
                    "device_id": device_id,
                    "state": state,
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

            self.known_devices[device_id] = replace(device, connection_state=state)
            if state != "connected":
                self.active_connections.pop(device_id, None)

        self._emit({"event": "device_state_changed", "device_id": device_id, "state": state})

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
