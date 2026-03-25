from __future__ import annotations

from datetime import UTC, datetime

import pytest

from audio_blue.app_state import AppStateStore
from audio_blue.models import AppConfig, DeviceRule, NotificationPreferences, DeviceSummary
from audio_blue.notification_service import NotificationMessage, NotificationService
from audio_blue.session_state import SessionStateCoordinator


class ConnectorServiceStub:
    def __init__(self) -> None:
        self.known_devices = {
            "device-1": DeviceSummary(device_id="device-1", name="Headphones"),
            "device-2": DeviceSummary(device_id="device-2", name="Speaker"),
        }
        self.active_connections: dict[str, object] = {}
        self._state_callback = None
        self.connect_calls: list[tuple[str, str]] = []

    def refresh_devices(self):
        if callable(self._state_callback):
            self._state_callback(
                {
                    "event": "devices_refreshed",
                    "device_ids": list(self.known_devices),
                }
            )
        return list(self.known_devices.values())

    def connect(self, device_id: str, trigger: str = "manual"):
        self.connect_calls.append((device_id, trigger))
        self.active_connections[device_id] = object()
        self.known_devices[device_id] = DeviceSummary(
            device_id=self.known_devices[device_id].device_id,
            name=self.known_devices[device_id].name,
            connection_state="connected",
            present_in_last_scan=self.known_devices[device_id].present_in_last_scan,
            last_seen_at=datetime(2026, 3, 23, 10, 0, tzinfo=UTC),
        )
        if callable(self._state_callback):
            self._state_callback(
                {
                    "event": "device_connected",
                    "device_id": device_id,
                    "trigger": trigger,
                }
            )

    def disconnect(self, device_id: str, trigger: str = "manual"):
        self.active_connections.pop(device_id, None)
        self.known_devices[device_id] = DeviceSummary(
            device_id=self.known_devices[device_id].device_id,
            name=self.known_devices[device_id].name,
            connection_state="disconnected",
            present_in_last_scan=self.known_devices[device_id].present_in_last_scan,
            last_seen_at=self.known_devices[device_id].last_seen_at,
        )
        if callable(self._state_callback):
            self._state_callback(
                {
                    "event": "device_disconnected",
                    "device_id": device_id,
                    "state": "disconnected",
                    "trigger": trigger,
                }
            )

    def emit_presence_event(
        self,
        device: DeviceSummary,
        *,
        previous_present: bool,
        change: str = "added",
    ) -> None:
        self.known_devices[device.device_id] = device
        if callable(self._state_callback):
            self._state_callback(
                {
                    "event": "device_presence_changed",
                    "device_id": device.device_id,
                    "present": device.present_in_last_scan,
                    "previous_present": previous_present,
                    "change": change,
                }
            )


class AutostartManagerStub:
    def __init__(self):
        self.enabled = False

    def set_enabled(self, enabled: bool):
        self.enabled = enabled


class StorageStub:
    def __init__(self):
        self.connection_attempts: list[dict] = []
        self.device_cache_updates: list[dict] = []

    def record_connection_attempt(self, **payload):
        self.connection_attempts.append(payload)

    def upsert_device_cache(self, **payload):
        self.device_cache_updates.append(payload)


@pytest.fixture(autouse=True)
def _patch_save_config(monkeypatch):
    monkeypatch.setattr("audio_blue.session_state.save_config", lambda _config: None)


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


def test_session_state_startup_auto_connect_uses_rules_order_and_stops_after_success():
    service = ConnectorServiceStub()
    service.known_devices["device-3"] = DeviceSummary(device_id="device-3", name="Receiver")
    storage = StorageStub()
    published_notifications: list[NotificationMessage] = []
    config = AppConfig(
        reconnect=True,
        last_devices=["device-3", "device-2", "device-1"],
        notification=NotificationPreferences(policy="all"),
        device_rules={
            "device-1": DeviceRule(
                is_favorite=True,
                priority=2,
            ),
            "device-2": DeviceRule(
                priority=1,
            ),
            "device-3": DeviceRule(auto_connect_on_startup=True),
        },
    )
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=config),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="all", sink=published_notifications.append),
        storage=storage,
    )

    def connect_with_first_failure(device_id: str, trigger: str = "manual"):
        if device_id == "device-1":
            service.connect_calls.append((device_id, trigger))
            service._state_callback(
                {
                    "event": "device_connection_failed",
                    "device_id": "device-1",
                    "state": "timeout",
                    "trigger": trigger,
                }
            )
            return
        ConnectorServiceStub.connect(service, device_id, trigger=trigger)

    service.connect = connect_with_first_failure

    session_state.refresh_devices()

    assert service.connect_calls == [("device-1", "startup"), ("device-2", "startup")]
    assert any(item["trigger"] == "startup" and item["state"] == "timeout" for item in storage.connection_attempts)
    assert any(item["trigger"] == "startup" and item["succeeded"] is True for item in storage.connection_attempts)
    assert [message.level for message in published_notifications] == ["error", "info"]


def test_session_state_reappear_auto_connect_triggers_when_device_returns():
    service = ConnectorServiceStub()
    service.known_devices = {
        "device-1": DeviceSummary(
            device_id="device-1",
            name="Headphones",
            present_in_last_scan=False,
        )
    }
    config = AppConfig(
        device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)}
    )
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=config),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
    )

    present_now = False

    def refresh_with_presence():
        service.known_devices["device-1"] = DeviceSummary(
            device_id="device-1",
            name="Headphones",
            present_in_last_scan=present_now,
        )
        if callable(service._state_callback):
            service._state_callback(
                {
                    "event": "devices_refreshed",
                    "device_ids": list(service.known_devices),
                }
            )
        return list(service.known_devices.values())

    service.refresh_devices = refresh_with_presence
    session_state.refresh_devices()
    present_now = True
    session_state.refresh_devices()

    assert ("device-1", "reappear") in service.connect_calls


def test_session_state_reappear_auto_connect_triggers_from_presence_event():
    service = ConnectorServiceStub()
    service.known_devices = {}
    config = AppConfig(
        device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)}
    )
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=config),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
    )

    session_state.refresh_devices()
    service.emit_presence_event(
        DeviceSummary(
            device_id="device-1",
            name="Headphones",
            present_in_last_scan=True,
        ),
        previous_present=False,
    )

    assert ("device-1", "reappear") in service.connect_calls


def test_session_state_does_not_startup_connect_when_reconnect_disabled_even_with_legacy_rule():
    service = ConnectorServiceStub()
    config = AppConfig(
        reconnect=False,
        last_devices=["device-1"],
        device_rules={
            "device-1": DeviceRule(auto_connect_on_startup=True),
        },
    )
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=config),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
    )

    session_state.refresh_devices()

    assert service.connect_calls == []


def test_session_state_set_reconnect_persists_and_emits_snapshot_field():
    service = ConnectorServiceStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=AppConfig(reconnect=False)),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
    )

    snapshot = session_state.set_reconnect(True)

    assert session_state.app_state.config.reconnect is True
    assert snapshot["settings"]["startup"]["reconnectOnNextStart"] is True


def test_session_state_writes_device_cache_on_refresh():
    service = ConnectorServiceStub()
    storage = StorageStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=AppConfig()),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
        storage=storage,
    )

    session_state.refresh_devices()

    assert {item["device_id"] for item in storage.device_cache_updates} == {"device-1", "device-2"}
    assert all(set(item) == {
        "device_id",
        "name",
        "connection_state",
        "supports_audio_playback",
        "supports_microphone",
        "last_seen_at",
    } for item in storage.device_cache_updates)
    assert all(item["supports_audio_playback"] is True for item in storage.device_cache_updates)
    assert all(item["supports_microphone"] is False for item in storage.device_cache_updates)


def test_session_state_emits_single_state_channel_for_refresh_connection_rules_and_settings():
    service = ConnectorServiceStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(config=AppConfig()),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
    )
    observed: list[dict] = []
    session_state.subscribe(lambda snapshot: observed.append(snapshot))

    session_state.refresh_devices()
    session_state.connect_device("device-1")
    session_state.update_device_rule("device-1", {"is_favorite": True})
    session_state.set_theme("dark")

    assert len(observed) >= 4
    assert all("devices" in item for item in observed)
