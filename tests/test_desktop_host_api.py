from pathlib import Path

from audio_blue.app_state import AppStateStore
from audio_blue.desktop_host import DesktopApi
from audio_blue.models import AppConfig, DeviceSummary, UiPreferences
from audio_blue.notification_service import NotificationService


class ServiceStub:
    def __init__(self):
        self.known_devices = {
            "device-1": DeviceSummary(device_id="device-1", name="Headphones"),
            "device-2": DeviceSummary(device_id="device-2", name="Speaker"),
        }
        self.active_connections = {}
        self.calls: list[str] = []

    def refresh_devices(self):
        self.calls.append("refresh")
        return list(self.known_devices.values())

    def connect(self, device_id: str):
        self.calls.append(f"connect:{device_id}")
        self.active_connections[device_id] = object()
        self.known_devices[device_id].connection_state = "connected"

    def disconnect(self, device_id: str):
        self.calls.append(f"disconnect:{device_id}")
        self.active_connections.pop(device_id, None)
        self.known_devices[device_id].connection_state = "disconnected"


class AutostartManagerStub:
    def __init__(self):
        self.enabled = False

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def is_enabled(self):
        return self.enabled


def test_desktop_api_refreshes_devices_and_updates_snapshot(tmp_path):
    service = ServiceStub()
    api = DesktopApi(
        service=service,
        app_state=AppStateStore(config=AppConfig(ui=UiPreferences(language="zh-CN"))),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
        diagnostics_exporter=lambda snapshot, path: path,
        open_bluetooth_settings=lambda: None,
        diagnostics_output_dir=tmp_path,
    )

    snapshot = api.refresh_devices()

    assert service.calls == ["refresh"]
    assert [device["deviceId"] for device in snapshot["devices"]] == ["device-1", "device-2"]
    assert snapshot["settings"]["ui"]["language"] == "zh-CN"


def test_desktop_api_updates_rules_settings_and_exports_diagnostics(tmp_path):
    exported_paths: list[Path] = []
    service = ServiceStub()
    app_state = AppStateStore(config=AppConfig())
    api = DesktopApi(
        service=service,
        app_state=app_state,
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
        diagnostics_exporter=lambda snapshot, path: exported_paths.append(path) or path,
        open_bluetooth_settings=lambda: None,
        diagnostics_output_dir=tmp_path,
    )
    api.refresh_devices()

    snapshot = api.update_device_rule(
        "device-1",
        {"is_favorite": True, "auto_connect_on_startup": True},
    )
    snapshot = api.reorder_device_priority(["device-1", "device-2"])
    snapshot = api.set_theme("dark")
    snapshot = api.set_notification_policy("all")
    snapshot = api.set_autostart(True)
    export_path = api.export_diagnostics()

    assert snapshot["deviceRules"]["device-1"]["isFavorite"] is True
    assert snapshot["deviceRules"]["device-1"]["priority"] == 1
    assert snapshot["settings"]["ui"]["theme"] == "dark"
    assert snapshot["settings"]["notification"]["policy"] == "all"
    assert api.autostart_manager.is_enabled() is True
    assert export_path.endswith(".zip")
    assert exported_paths and exported_paths[0].parent.name == "support-bundles"


def test_desktop_api_set_language_updates_config_and_returns_snapshot(tmp_path):
    service = ServiceStub()
    app_state = AppStateStore(config=AppConfig())
    api = DesktopApi(
        service=service,
        app_state=app_state,
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
        diagnostics_exporter=lambda snapshot, path: path,
        open_bluetooth_settings=lambda: None,
        diagnostics_output_dir=tmp_path,
    )
    api.refresh_devices()

    snapshot = api.set_language("zh-CN")

    assert getattr(app_state.config.ui, "language", None) == "zh-CN"
    assert snapshot["settings"]["ui"].get("language") == "zh-CN"


def test_desktop_api_exports_support_bundle_and_records_client_events(tmp_path):
    exported_paths: list[Path] = []
    observed_events: list[dict] = []
    service = ServiceStub()
    app_state = AppStateStore(config=AppConfig())
    api = DesktopApi(
        service=service,
        app_state=app_state,
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(),
        diagnostics_exporter=lambda snapshot, path: exported_paths.append(path) or path,
        open_bluetooth_settings=lambda: None,
        diagnostics_output_dir=tmp_path,
        session_state=type(
            "SessionStateStub",
            (),
            {
                "snapshot": lambda _self: {"devices": []},
                "record_client_event": lambda _self, payload: observed_events.append(payload),
            },
        )(),
    )

    support_bundle_path = api.export_support_bundle()
    alias_path = api.export_diagnostics()
    api.record_client_event(
        {
            "area": "ui",
            "eventType": "ui.error",
            "level": "error",
            "title": "页面异常",
            "detail": "按钮点击失败。",
        }
    )

    assert support_bundle_path.endswith(".zip")
    assert alias_path.endswith(".zip")
    assert exported_paths[0].suffix == ".zip"
    assert observed_events[0]["eventType"] == "ui.error"
