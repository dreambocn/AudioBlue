from __future__ import annotations

from dataclasses import replace
from typing import Callable

from audio_blue.models import DeviceSummary

StateCallback = Callable[[dict[str, object]], None]
DeviceProvider = Callable[[], list[DeviceSummary]]


class ConnectorService:
    def __init__(
        self,
        device_provider: DeviceProvider | None = None,
        state_callback: StateCallback | None = None,
    ) -> None:
        self._device_provider = device_provider or (lambda: [])
        self._state_callback = state_callback
        self.known_devices: dict[str, DeviceSummary] = {}
        self.active_connections: dict[str, object] = {}
        self.is_shutdown = False

    def refresh_devices(self) -> list[DeviceSummary]:
        devices = self._device_provider()
        self.known_devices = {device.device_id: device for device in devices}
        self._emit({"event": "devices_refreshed", "device_ids": list(self.known_devices)})
        return devices

    def connect(self, device_id: str) -> None:
        device = self.known_devices[device_id]
        self.active_connections[device_id] = object()
        self.known_devices[device_id] = replace(device, connection_state="connected")
        self._emit({"event": "device_connected", "device_id": device_id})

    def disconnect(self, device_id: str) -> None:
        device = self.known_devices[device_id]
        self.active_connections.pop(device_id, None)
        self.known_devices[device_id] = replace(device, connection_state="disconnected")
        self._emit({"event": "device_disconnected", "device_id": device_id})

    def shutdown(self) -> None:
        self.active_connections.clear()
        self.is_shutdown = True
        self._emit({"event": "service_shutdown"})

    def _emit(self, payload: dict[str, object]) -> None:
        if self._state_callback is not None:
            self._state_callback(payload)
