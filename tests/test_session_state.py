"""验证会话协调器如何把服务事件、存储与通知折叠成单一快照。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from audio_blue.app_state import AppStateStore
from audio_blue.models import AppConfig, DeviceRule, NotificationPreferences, DeviceSummary
from audio_blue.notification_service import NotificationMessage, NotificationService
from audio_blue.session_state import SessionStateCoordinator


class ConnectorServiceStub:
    """模拟连接服务的刷新、连接和 presence 事件入口。"""

    def __init__(self) -> None:
        self.known_devices = {
            "device-1": DeviceSummary(device_id="device-1", name="Headphones"),
            "device-2": DeviceSummary(device_id="device-2", name="Speaker"),
        }
        self.active_connections: dict[str, object] = {}
        self._state_callback = None
        self.connect_calls: list[tuple[str, str]] = []
        self.connect_outcomes: dict[str, list[str]] = {}
        self.initial_enumeration_completed = False

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
        outcomes = self.connect_outcomes.get(device_id)
        outcome = outcomes.pop(0) if outcomes else "connected"
        if outcome != "connected":
            self.active_connections.pop(device_id, None)
            self.known_devices[device_id] = DeviceSummary(
                device_id=self.known_devices[device_id].device_id,
                name=self.known_devices[device_id].name,
                connection_state="failed",
                present_in_last_scan=self.known_devices[device_id].present_in_last_scan,
                last_seen_at=self.known_devices[device_id].last_seen_at,
            )
            if callable(self._state_callback):
                self._state_callback(
                    {
                        "event": "device_connection_failed",
                        "device_id": device_id,
                        "state": outcome,
                        "trigger": trigger,
                    }
                )
            return
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

    def emit_state_event(
        self,
        device_id: str,
        *,
        state: str,
        trigger: str = "runtime",
    ) -> None:
        """模拟连接层上报状态变化，但不修改 presence。"""
        existing = self.known_devices[device_id]
        self.known_devices[device_id] = DeviceSummary(
            device_id=existing.device_id,
            name=existing.name,
            connection_state=state,
            present_in_last_scan=existing.present_in_last_scan,
            last_seen_at=existing.last_seen_at,
        )
        if state != "connected":
            self.active_connections.pop(device_id, None)
        if callable(self._state_callback):
            self._state_callback(
                {
                    "event": "device_state_changed",
                    "device_id": device_id,
                    "state": state,
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

    def has_completed_initial_enumeration(self) -> bool:
        return self.initial_enumeration_completed


class AutostartManagerStub:
    """记录随系统启动设置是否被协调器正确更新。"""

    def __init__(self):
        self.enabled = False

    def set_enabled(self, enabled: bool):
        self.enabled = enabled


class StorageStub:
    """收集写入存储的连接尝试与设备缓存，便于断言副作用。"""

    def __init__(self):
        self.connection_attempts: list[dict] = []
        self.device_cache_updates: list[dict] = []
        self.activity_events: list[dict] = []

    def record_connection_attempt(self, **payload):
        self.connection_attempts.append(payload)

    def upsert_device_cache(self, **payload):
        self.device_cache_updates.append(payload)

    def record_activity_event(self, **payload):
        self.activity_events.append(payload)


class ScheduledCallStub:
    """模拟可取消的延迟任务句柄。"""

    def __init__(self, delay: float, callback) -> None:
        self.delay = delay
        self._callback = callback
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        if self.cancelled:
            return
        self._callback()


class RetrySchedulerStub:
    """收集 recovery 重试调度，测试时手动触发。"""

    def __init__(self) -> None:
        self.calls: list[ScheduledCallStub] = []

    def __call__(self, delay: float, callback):
        handle = ScheduledCallStub(delay, callback)
        self.calls.append(handle)
        return handle


@pytest.fixture(autouse=True)
def _patch_save_config(monkeypatch):
    """屏蔽真实配置落盘，确保测试只关注协调逻辑本身。"""
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


def test_session_state_reappear_auto_connect_still_works_when_startup_enumeration_finished_before_binding():
    service = ConnectorServiceStub()
    service.initial_enumeration_completed = True
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


def test_session_state_disconnect_recover_starts_immediately_when_device_stays_present():
    service = ConnectorServiceStub()
    service.initial_enumeration_completed = True
    service.active_connections["device-1"] = object()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="connected",
        present_in_last_scan=True,
    )
    scheduler = RetrySchedulerStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                reconnect=False,
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)},
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="disconnected")

    assert service.connect_calls == [("device-1", "recover")]
    assert scheduler.calls == []


def test_session_state_recover_retries_until_terminal_failure_and_only_notifies_once():
    service = ConnectorServiceStub()
    service.initial_enumeration_completed = True
    service.active_connections["device-1"] = object()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="connected",
        present_in_last_scan=True,
    )
    service.connect_outcomes["device-1"] = ["timeout", "timeout", "timeout"]
    scheduler = RetrySchedulerStub()
    storage = StorageStub()
    published_notifications: list[NotificationMessage] = []
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                reconnect=False,
                notification=NotificationPreferences(policy="all"),
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)},
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="all", sink=published_notifications.append),
        storage=storage,
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="disconnected")

    assert service.connect_calls == [("device-1", "recover")]
    assert [call.delay for call in scheduler.calls] == [1.0]
    assert published_notifications == []

    scheduler.calls[0].fire()

    assert service.connect_calls == [("device-1", "recover"), ("device-1", "recover")]
    assert [call.delay for call in scheduler.calls] == [1.0, 2.0]
    assert published_notifications == []

    scheduler.calls[1].fire()

    assert service.connect_calls == [
        ("device-1", "recover"),
        ("device-1", "recover"),
        ("device-1", "recover"),
    ]
    assert [message.level for message in published_notifications] == ["error"]
    assert sum(1 for item in storage.connection_attempts if item["trigger"] == "recover") == 3
    assert sum(1 for item in storage.activity_events if item["event_type"] == "automation.recover.retrying") == 2
    assert any(item["event_type"] == "connection.recover.exhausted" for item in storage.activity_events)


def test_session_state_recover_success_on_second_attempt_stops_future_retries():
    service = ConnectorServiceStub()
    service.initial_enumeration_completed = True
    service.active_connections["device-1"] = object()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="connected",
        present_in_last_scan=True,
    )
    service.connect_outcomes["device-1"] = ["timeout", "connected"]
    scheduler = RetrySchedulerStub()
    storage = StorageStub()
    published_notifications: list[NotificationMessage] = []
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                notification=NotificationPreferences(policy="all"),
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)},
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="all", sink=published_notifications.append),
        storage=storage,
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="disconnected")
    scheduler.calls[0].fire()

    assert service.connect_calls == [("device-1", "recover"), ("device-1", "recover")]
    assert [message.level for message in published_notifications] == ["info"]
    assert sum(1 for item in storage.activity_events if item["event_type"] == "connection.recover.succeeded") == 1


def test_session_state_manual_disconnect_suppresses_recover_and_reappear_until_manual_connect():
    service = ConnectorServiceStub()
    service.initial_enumeration_completed = True
    service.active_connections["device-1"] = object()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="connected",
        present_in_last_scan=True,
    )
    scheduler = RetrySchedulerStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)}
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
        retry_scheduler=scheduler,
    )

    session_state.disconnect_device("device-1")
    service.emit_presence_event(
        DeviceSummary(
            device_id="device-1",
            name="Headphones",
            connection_state="disconnected",
            present_in_last_scan=True,
        ),
        previous_present=False,
    )

    assert service.connect_calls == []

    session_state.connect_device("device-1")
    service.active_connections.clear()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="disconnected",
        present_in_last_scan=True,
    )
    service.connect_calls.clear()
    service.emit_presence_event(
        DeviceSummary(
            device_id="device-1",
            name="Headphones",
            connection_state="disconnected",
            present_in_last_scan=True,
        ),
        previous_present=False,
    )

    assert ("device-1", "reappear") in service.connect_calls


def test_session_state_recover_cancels_pending_retry_when_device_becomes_absent():
    service = ConnectorServiceStub()
    service.initial_enumeration_completed = True
    service.active_connections["device-1"] = object()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="connected",
        present_in_last_scan=True,
    )
    service.connect_outcomes["device-1"] = ["timeout"]
    scheduler = RetrySchedulerStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)}
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="disconnected")
    service.emit_presence_event(
        DeviceSummary(
            device_id="device-1",
            name="Headphones",
            connection_state="disconnected",
            present_in_last_scan=False,
        ),
        previous_present=True,
        change="removed",
    )
    scheduler.calls[0].fire()

    assert scheduler.calls[0].cancelled is True
    assert service.connect_calls == [("device-1", "recover")]


def test_session_state_recover_replaces_old_retry_when_new_disconnect_arrives():
    service = ConnectorServiceStub()
    service.initial_enumeration_completed = True
    service.active_connections["device-1"] = object()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="connected",
        present_in_last_scan=True,
    )
    service.connect_outcomes["device-1"] = ["timeout", "timeout", "connected"]
    scheduler = RetrySchedulerStub()
    published_notifications: list[NotificationMessage] = []
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                notification=NotificationPreferences(policy="all"),
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)},
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="all", sink=published_notifications.append),
        storage=StorageStub(),
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="disconnected")
    first_retry = scheduler.calls[0]
    service.emit_state_event("device-1", state="disconnected")
    second_retry = scheduler.calls[1]
    first_retry.fire()
    second_retry.fire()

    assert first_retry.cancelled is True
    assert service.connect_calls == [
        ("device-1", "recover"),
        ("device-1", "recover"),
        ("device-1", "recover"),
    ]
    assert [message.level for message in published_notifications] == ["info"]


def test_session_state_recover_ignores_global_startup_reconnect_toggle():
    service = ConnectorServiceStub()
    service.initial_enumeration_completed = True
    service.active_connections["device-1"] = object()
    service.known_devices["device-1"] = DeviceSummary(
        device_id="device-1",
        name="Headphones",
        connection_state="connected",
        present_in_last_scan=True,
    )
    scheduler = RetrySchedulerStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                reconnect=False,
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)},
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="disconnected")

    assert service.connect_calls == [("device-1", "recover")]


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
