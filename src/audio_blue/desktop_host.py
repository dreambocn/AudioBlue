from __future__ import annotations

import ctypes
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable, Protocol
import sys

from audio_blue.app_state import AppStateStore
from audio_blue.diagnostics import build_diagnostics_snapshot
from audio_blue.models import NotificationPolicy, ThemeMode


class DiagnosticsExporter(Protocol):
    def __call__(self, snapshot: dict[str, object], path: Path) -> Path: ...


def find_ui_entrypoint(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        root = base_dir
    elif getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "ui" / "dist" / "index.html",
        root / "dist" / "AudioBlue" / "_internal" / "ui" / "index.html",
        root / "_internal" / "ui" / "index.html",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not find built AudioBlue UI entrypoint. Run `npm run build` in the `ui` directory first."
    )


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
        session_state=None,
        support_bundle_exporter: DiagnosticsExporter | None = None,
        observability=None,
    ) -> None:
        self.service = service
        self.app_state = app_state
        self.autostart_manager = autostart_manager
        self.notification_service = notification_service
        self.session_state = session_state
        self._diagnostics_exporter = diagnostics_exporter
        self._support_bundle_exporter = support_bundle_exporter or diagnostics_exporter
        self._open_bluetooth_settings = open_bluetooth_settings
        self._diagnostics_output_dir = diagnostics_output_dir
        self._window_theme_sync: Callable[[str], bool] | None = None
        self._observability = observability

    def get_initial_state(self) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.snapshot()
        self._sync_from_service()
        return self.app_state.snapshot()

    def refresh_devices(self) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.refresh_devices()
        self.service.refresh_devices()
        self._sync_from_service()
        return self.app_state.snapshot()

    def connect_device(self, device_id: str) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.connect_device(device_id)
        self.service.connect(device_id)
        self.app_state.handle_connector_event({"event": "device_connected", "device_id": device_id})
        self._sync_from_service()
        return self.app_state.snapshot()

    def disconnect_device(self, device_id: str) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.disconnect_device(device_id)
        self.service.disconnect(device_id)
        self.app_state.handle_connector_event(
            {"event": "device_disconnected", "device_id": device_id, "state": "disconnected"}
        )
        self._sync_from_service()
        return self.app_state.snapshot()

    def update_device_rule(self, device_id: str, rule_patch: dict[str, Any]) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.update_device_rule(device_id, rule_patch)
        self.app_state.update_device_rule(device_id, rule_patch)
        return self.app_state.snapshot()

    def reorder_device_priority(self, device_ids: list[str]) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.reorder_device_priority(device_ids)
        self.app_state.reorder_device_priority(device_ids)
        return self.app_state.snapshot()

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.set_autostart(enabled)
        self.autostart_manager.set_enabled(enabled)
        self.app_state.config.startup.autostart = enabled
        return self.app_state.snapshot()

    def set_theme(self, mode: ThemeMode) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.set_theme(mode)
        self.app_state.config.ui.theme = mode
        return self.app_state.snapshot()

    def set_language(self, language: str) -> dict[str, Any]:
        if language not in {"system", "zh-CN", "en-US"}:
            raise ValueError("Unsupported language")
        if self.session_state is not None:
            return self.session_state.set_language(language)
        setattr(self.app_state.config.ui, "language", language)
        snapshot = self.app_state.snapshot()
        snapshot.setdefault("settings", {}).setdefault("ui", {})["language"] = language
        return snapshot

    def set_notification_policy(self, policy: NotificationPolicy) -> dict[str, Any]:
        if self.session_state is not None:
            return self.session_state.set_notification_policy(policy)
        self.notification_service.update_policy(policy)
        self.app_state.config.notification.policy = policy
        return self.app_state.snapshot()

    def set_reconnect(self, enabled: bool) -> dict[str, Any]:
        if self.session_state is not None and hasattr(self.session_state, "set_reconnect"):
            snapshot = self.session_state.set_reconnect(enabled)
            return self._ensure_reconnect_in_snapshot(snapshot, enabled)
        self.app_state.config.reconnect = bool(enabled)
        snapshot = self.app_state.snapshot()
        return self._ensure_reconnect_in_snapshot(snapshot, enabled)

    def register_window_theme_sync(self, callback: Callable[[str], bool]) -> None:
        self._window_theme_sync = callback

    def sync_window_theme(self, mode: str) -> dict[str, Any]:
        if mode not in {"light", "dark"}:
            raise ValueError("Unsupported theme mode")
        if self._window_theme_sync is None:
            return {"mode": mode, "applied": False}
        result = self._window_theme_sync(mode)
        applied = True if result is None else bool(result)
        return {"mode": mode, "applied": applied}

    def open_bluetooth_settings(self) -> None:
        try:
            self._open_bluetooth_settings()
        except Exception as exc:
            if self._observability is not None and hasattr(self._observability, "record_exception"):
                self._observability.record_exception(
                    area="desktop",
                    event_type="desktop.open_bluetooth_settings.failed",
                    title="打开蓝牙设置失败",
                    exc=exc,
                )
            raise
        if self._observability is not None and hasattr(self._observability, "record_event"):
            self._observability.record_event(
                area="desktop",
                event_type="desktop.open_bluetooth_settings.succeeded",
                level="info",
                title="已打开蓝牙设置",
                detail="已请求打开 Windows 蓝牙设置。",
            )

    def export_diagnostics(self) -> str:
        return self.export_support_bundle()

    def export_support_bundle(self) -> str:
        runtime_snapshot = self.get_initial_state()
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
        snapshot.update(
            {
                "connectionOverview": runtime_snapshot.get(
                    "connectionOverview",
                    runtime_snapshot.get("connection"),
                ),
                "recentActivity": runtime_snapshot.get("recentActivity", []),
                "deviceHistory": runtime_snapshot.get("deviceHistory", []),
                "diagnostics": runtime_snapshot.get("diagnostics", {}),
                "settings": runtime_snapshot.get("settings", {}),
            }
        )
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        export_path = self._diagnostics_output_dir / "support-bundles" / f"support-bundle-{timestamp}.zip"
        try:
            path = self._support_bundle_exporter(snapshot, export_path)
        except Exception as exc:
            if self._observability is not None and hasattr(self._observability, "record_exception"):
                self._observability.record_exception(
                    area="export",
                    event_type="export.support_bundle.failed",
                    title="支持包导出失败",
                    exc=exc,
                    details={"path": str(export_path)},
                )
            raise
        if self._observability is not None and hasattr(self._observability, "record_event"):
            self._observability.record_event(
                area="export",
                event_type="export.support_bundle.succeeded",
                level="info",
                title="支持包导出成功",
                detail=f"支持包已导出到 {path}。",
                details={"path": str(path)},
            )
        return str(path)

    def record_client_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.session_state is not None and hasattr(self.session_state, "record_client_event"):
            return self.session_state.record_client_event(payload)
        if self._observability is not None and hasattr(self._observability, "record_event"):
            self._observability.record_event(
                area=str(payload.get("area", "ui")),
                event_type=str(payload.get("eventType", payload.get("event_type", "ui.event"))),
                level=str(payload.get("level", "error")),
                title=str(payload.get("title", "界面事件")),
                detail=(
                    str(payload.get("detail"))
                    if payload.get("detail") is not None
                    else None
                ),
                device_id=(
                    str(payload.get("deviceId"))
                    if payload.get("deviceId") is not None
                    else None
                ),
                error_code=(
                    str(payload.get("errorCode"))
                    if payload.get("errorCode") is not None
                    else None
                ),
                details=payload.get("details") if isinstance(payload.get("details"), dict) else None,
            )
        return self.get_initial_state()

    def _sync_from_service(self) -> None:
        self.app_state.sync_devices(list(getattr(self.service, "known_devices", {}).values()))

    def _ensure_reconnect_in_snapshot(self, snapshot: dict[str, Any], enabled: bool) -> dict[str, Any]:
        settings = snapshot.setdefault("settings", {})
        startup = settings.setdefault("startup", {})
        startup["reconnectOnNextStart"] = bool(enabled)
        return snapshot


class DesktopHost:
    def __init__(self, api: DesktopApi, ui_entrypoint: Path, webview_module=None) -> None:
        self.api = api
        self.ui_entrypoint = ui_entrypoint
        self._webview = webview_module
        self.main_window = None
        self._state_unsubscribe = None
        self._allow_close = False
        if hasattr(self.api, "register_window_theme_sync"):
            self.api.register_window_theme_sync(self.sync_window_theme)

    def create_windows(self) -> None:
        if self.main_window is not None:
            return

        if self._webview is None:
            import webview  # type: ignore[import-not-found]

            self._webview = webview

        main_url = self.ui_entrypoint.as_uri()
        self.main_window = self._webview.create_window(
            "AudioBlue",
            url=main_url,
            js_api=self.api,
            width=1180,
            height=780,
            hidden=True,
        )
        window_events = getattr(self.main_window, "events", None)
        if window_events is not None and hasattr(window_events, "closing"):
            window_events.closing += self._on_main_window_closing

    def run(self, on_started: Callable[[], None] | None = None) -> None:
        self.create_windows()
        if self._webview is None:
            raise RuntimeError("Webview module is not available.")
        session_state = getattr(self.api, "session_state", None)

        def on_started_wrapper() -> None:
            if session_state is not None and hasattr(session_state, "subscribe"):
                self._state_unsubscribe = session_state.subscribe(self.push_state)
            if on_started is not None:
                on_started()

        self._webview.start(on_started_wrapper if on_started or session_state is not None else None, gui="edgechromium", http_server=False)

    def show_main_window(self) -> None:
        if self.main_window is None:
            raise RuntimeError("Main window has not been created.")
        self.main_window.show()

    def show_quick_panel(self) -> None:
        raise RuntimeError("Quick panel is not part of the runtime path.")

    def sync_window_theme(self, mode: str) -> bool:
        if self.main_window is None:
            return False
        try:
            self._apply_native_title_bar_theme(self.main_window, mode)
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        self._allow_close = True
        if callable(self._state_unsubscribe):
            self._state_unsubscribe()
            self._state_unsubscribe = None

        for window in (self.main_window,):
            if window is None or not hasattr(window, "destroy"):
                continue

            window_events = getattr(window, "events", None)
            shown_event = getattr(window_events, "shown", None)
            if shown_event is not None and not shown_event.is_set():
                continue

            try:
                window.destroy()
            except Exception:
                continue

    def push_state(self, snapshot: dict[str, Any]) -> None:
        if self.main_window is None or not hasattr(self.main_window, "evaluate_js"):
            return
        payload = json.dumps(snapshot, ensure_ascii=False)
        script = (
            "window.dispatchEvent("
            f"new CustomEvent('audioblue:state', {{ detail: {payload} }})"
            ");"
        )
        self.main_window.evaluate_js(script)

    def _on_main_window_closing(self) -> bool:
        if self._allow_close or self.main_window is None:
            return True
        if hasattr(self.main_window, "hide"):
            self.main_window.hide()
        return False

    def _apply_native_title_bar_theme(self, window: object, mode: str) -> None:
        if mode not in {"light", "dark"}:
            raise ValueError("Unsupported theme mode")

        hwnd = self._resolve_window_handle(window)
        enabled = ctypes.c_int(1 if mode == "dark" else 0)
        dwmapi = ctypes.windll.dwmapi
        attributes = (20, 19)
        for attribute in attributes:
            result = dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(attribute),
                ctypes.byref(enabled),
                ctypes.c_uint(ctypes.sizeof(enabled)),
            )
            if result == 0:
                return
        raise RuntimeError("Failed to apply native title bar theme")

    def _resolve_window_handle(self, window: object) -> int:
        for attribute in ("hwnd", "_hwnd"):
            value = getattr(window, attribute, None)
            if isinstance(value, int) and value > 0:
                return value

        native = getattr(window, "native", None)
        if native is not None:
            for attribute in ("hwnd", "_hwnd", "Handle", "handle"):
                value = getattr(native, attribute, None)
                if isinstance(value, int) and value > 0:
                    return value

        title = getattr(window, "title", "")
        if not isinstance(title, str):
            title = ""
        hwnd = ctypes.windll.user32.FindWindowW(None, title or None)
        if hwnd:
            return int(hwnd)
        raise RuntimeError("Could not resolve window handle")
