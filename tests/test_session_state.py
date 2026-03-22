from __future__ import annotations

from audio_blue.app_state import AppStateStore
from audio_blue.models import AppConfig, DeviceSummary
from audio_blue.notification_service import NotificationService
from audio_blue.session_state import SessionStateCoordinator


class ConnectorServiceStub:
    def __init__(self) -> None:
        self.known_devices = {
            "device-1": DeviceSummary(device_id="device-1", name="Headphones"),
            "device-2": DeviceSummary(device_id="device-2", name="Speaker"),
        }
        self.active_connections: dict[str, object] = {}
        self._state_callback = None

    def refresh_devices(self):
        if callable(self._state_callback):
            self._state_callback(
                {
                    "event": "devices_refreshed",
                    "device_ids": list(self.known_devices),
                }
            )
        return list(self.known_devices.values())

    def connect(self, device_id: str):
        self.active_connections[device_id] = object()
        self.known_devices[device_id].connection_state = "connected"
        if callable(self._state_callback):
            self._state_callback({"event": "device_connected", "device_id": device_id})

    def disconnect(self, device_id: str):
        self.active_connections.pop(device_id, None)
        self.known_devices[device_id].connection_state = "disconnected"
        if callable(self._state_callback):
            self._state_callback(
                {
                    "event": "device_disconnected",
                    "device_id": device_id,
                    "state": "disconnected",
                }
            )


class AutostartManagerStub:
    def __init__(self):
        self.enabled = False

    def set_enabled(self, enabled: bool):
        self.enabled = enabled


def test_session_state_registers_service_callback_and_tracks_external_events():
    service = ConnectorServiceStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=AppConfig()),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
    )

    assert callable(service._state_callback)

    session_state.refresh_devices()
    service.connect("device-1")
    snapshot = session_state.snapshot()

    target = next(device for device in snapshot["devices"] if device["deviceId"] == "device-1")
    assert target["connectionState"] == "connected"


def test_session_state_connect_disconnect_and_settings_share_single_snapshot_source():
    service = ConnectorServiceStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=AppConfig()),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
    )

    session_state.refresh_devices()
    session_state.connect_device("device-1")
    connected = session_state.snapshot()
    session_state.disconnect_device("device-1")
    disconnected = session_state.snapshot()
    after_theme = session_state.set_theme("dark")

    assert connected["devices"][0]["connectionState"] == "connected"
    assert disconnected["devices"][0]["connectionState"] == "disconnected"
    assert after_theme["settings"]["ui"]["theme"] == "dark"
