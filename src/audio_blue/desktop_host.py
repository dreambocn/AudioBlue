from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from audio_blue.app_state import AppStateStore
from audio_blue.diagnostics import build_diagnostics_snapshot
from audio_blue.models import NotificationPolicy, ThemeMode


class DiagnosticsExporter(Protocol):
    def __call__(self, snapshot: dict[str, object], path: Path) -> Path: ...


class DesktopApi:
    def __init__(
        self,
        service,
        app_state: AppStateStore,
        autostart_manager,
        notification_service,
        diagnostics_exporter: DiagnosticsExporter,
        open_bluetooth_settings: Callable[[], None],
        diagnostics_output_dir: Path,
    ) -> None:
        self.service = service
        self.app_state = app_state
        self.autostart_manager = autostart_manager
        self.notification_service = notification_service
        self._diagnostics_exporter = diagnostics_exporter
        self._open_bluetooth_settings = open_bluetooth_settings
        self._diagnostics_output_dir = diagnostics_output_dir

    def get_initial_state(self) -> dict[str, Any]:
        self._sync_from_service()
        return self.app_state.snapshot()

    def refresh_devices(self) -> dict[str, Any]:
        self.service.refresh_devices()
        self._sync_from_service()
        return self.app_state.snapshot()

    def connect_device(self, device_id: str) -> dict[str, Any]:
        self.service.connect(device_id)
        self.app_state.handle_connector_event({"event": "device_connected", "device_id": device_id})
        self._sync_from_service()
        return self.app_state.snapshot()

    def disconnect_device(self, device_id: str) -> dict[str, Any]:
        self.service.disconnect(device_id)
        self.app_state.handle_connector_event(
            {"event": "device_disconnected", "device_id": device_id, "state": "disconnected"}
        )
        self._sync_from_service()
        return self.app_state.snapshot()

    def update_device_rule(self, device_id: str, rule_patch: dict[str, Any]) -> dict[str, Any]:
        self.app_state.update_device_rule(device_id, rule_patch)
        return self.app_state.snapshot()

    def reorder_device_priority(self, device_ids: list[str]) -> dict[str, Any]:
        self.app_state.reorder_device_priority(device_ids)
        return self.app_state.snapshot()

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        self.autostart_manager.set_enabled(enabled)
        self.app_state.config.startup.autostart = enabled
        return self.app_state.snapshot()

    def set_theme(self, mode: ThemeMode) -> dict[str, Any]:
        self.app_state.config.ui.theme = mode
        return self.app_state.snapshot()

    def set_notification_policy(self, policy: NotificationPolicy) -> dict[str, Any]:
        self.notification_service.update_policy(policy)
        self.app_state.config.notification.policy = policy
        return self.app_state.snapshot()

    def open_bluetooth_settings(self) -> None:
        self._open_bluetooth_settings()

    def export_diagnostics(self) -> str:
        snapshot = build_diagnostics_snapshot(
            config=self.app_state.config,
            devices=list(getattr(self.service, "known_devices", {}).values()),
            attempts=[
                device.last_connection_attempt
                for device in getattr(self.service, "known_devices", {}).values()
                if getattr(device, "last_connection_attempt", None) is not None
            ],
            source="desktop-api",
        )
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        export_path = self._diagnostics_output_dir / f"diagnostics-{timestamp}.json"
        return str(self._diagnostics_exporter(snapshot, export_path))

    def _sync_from_service(self) -> None:
        self.app_state.sync_devices(list(getattr(self.service, "known_devices", {}).values()))


class DesktopHost:
    def __init__(self, api: DesktopApi, ui_entrypoint: Path, webview_module=None) -> None:
        self.api = api
        self.ui_entrypoint = ui_entrypoint
        self._webview = webview_module
        self.main_window = None
        self.quick_panel_window = None

    def create_windows(self) -> None:
        if self._webview is None:
            return

        main_url = self.ui_entrypoint.as_uri()
        quick_panel_url = f"{main_url}#quick-panel"
        self.main_window = self._webview.create_window(
            "AudioBlue",
            url=main_url,
            js_api=self.api,
            width=1180,
            height=780,
            hidden=True,
            gui="edge",
        )
        self.quick_panel_window = self._webview.create_window(
            "AudioBlue Quick Panel",
            url=quick_panel_url,
            js_api=self.api,
            width=420,
            height=560,
            hidden=True,
            frameless=True,
            easy_drag=True,
            on_top=True,
            gui="edge",
        )

    def show_main_window(self) -> None:
        if self.main_window is not None:
            self.main_window.show()

    def show_quick_panel(self) -> None:
        if self.quick_panel_window is not None:
            self.quick_panel_window.show()
