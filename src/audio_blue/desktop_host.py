"""封装 WebView 桌面宿主与暴露给前端的 API。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable, Protocol
import sys

from audio_blue.app_state import AppStateStore
from audio_blue.diagnostics import build_diagnostics_snapshot
from audio_blue.models import NotificationPolicy, ThemeMode


class DiagnosticsExporter(Protocol):
    """描述诊断导出器的最小调用约定。"""

    def __call__(self, snapshot: dict[str, object], path: Path) -> Path: ...


LONG_PTR = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
UINT_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint
LRESULT = LONG_PTR
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, UINT_PTR, LONG_PTR)

GWLP_WNDPROC = -4
WM_NCHITTEST = 0x0084
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92


def _set_window_long_ptr(hwnd: int, index: int, value: int) -> int:
    """统一封装窗口过程替换，便于测试里打桩。"""
    user32 = ctypes.windll.user32
    setter = getattr(user32, "SetWindowLongPtrW", None)
    if setter is None:
        setter = user32.SetWindowLongW
    setter.restype = LONG_PTR
    setter.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
    return int(setter(hwnd, index, value))


def _call_window_proc(original_proc: int, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
    """把未处理的消息回落给原始窗口过程。"""
    caller = ctypes.windll.user32.CallWindowProcW
    caller.restype = LRESULT
    caller.argtypes = [LONG_PTR, wintypes.HWND, wintypes.UINT, UINT_PTR, LONG_PTR]
    return int(caller(original_proc, hwnd, msg, wparam, lparam))


def _get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """读取窗口外边界，用于命中测试。"""
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _get_resize_border_thickness() -> int:
    """读取系统边框厚度，并保留一个合理的最小拖拽尺寸。"""
    user32 = ctypes.windll.user32
    frame_x = int(user32.GetSystemMetrics(SM_CXSIZEFRAME))
    frame_y = int(user32.GetSystemMetrics(SM_CYSIZEFRAME))
    padded = int(user32.GetSystemMetrics(SM_CXPADDEDBORDER))
    return max(8, frame_x + padded, frame_y + padded)


def _decode_lparam_point(lparam: int) -> tuple[int, int]:
    """从 Windows 消息参数中解出屏幕坐标。"""
    x = ctypes.c_short(lparam & 0xFFFF).value
    y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
    return x, y


def _resolve_resize_hit_test(
    rect: tuple[int, int, int, int],
    point: tuple[int, int],
    border_thickness: int,
    *,
    is_maximized: bool,
) -> int | None:
    """根据窗口边界、指针位置和边框厚度计算 resize 命中结果。"""
    if is_maximized:
        return None

    left, top, right, bottom = rect
    x, y = point
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0 or border_thickness <= 0:
        return None
    if x < left or x >= right or y < top or y >= bottom:
        return None

    # 为极小窗口收紧 resize 热区，避免左右/上下边缘完全覆盖客户区。
    max_horizontal_border = max(1, (width // 2) - 1) if width > 2 else 1
    max_vertical_border = max(1, (height // 2) - 1) if height > 2 else 1
    horizontal_border = min(border_thickness, max_horizontal_border)
    vertical_border = min(border_thickness, max_vertical_border)

    on_left = x < left + horizontal_border
    on_right = x >= right - horizontal_border
    on_top = y < top + vertical_border
    on_bottom = y >= bottom - vertical_border

    if on_top and on_left:
        return HTTOPLEFT
    if on_top and on_right:
        return HTTOPRIGHT
    if on_bottom and on_left:
        return HTBOTTOMLEFT
    if on_bottom and on_right:
        return HTBOTTOMRIGHT
    if on_left:
        return HTLEFT
    if on_right:
        return HTRIGHT
    if on_top:
        return HTTOP
    if on_bottom:
        return HTBOTTOM
    return None


def find_ui_entrypoint(base_dir: Path | None = None) -> Path:
    """按开发态、目录版和打包态顺序解析前端入口文件。"""
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
    """承接 pywebview 调用，把桌面动作映射到应用状态与服务层。"""

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
        self._window_controls: dict[str, Callable[[], None] | None] = {
            "minimize": None,
            "toggle_maximize": None,
            "close": None,
        }
        # 窗口 runtime 默认按自绘标题栏初始化；具体能力会在宿主建窗后刷新。
        self._runtime_state: dict[str, Any] = {
            "chrome": "custom",
            "isMaximized": False,
            "canMinimize": False,
            "canMaximize": False,
            "canClose": False,
        }
        self._observability = observability

    def get_initial_state(self) -> dict[str, Any]:
        """返回前端启动时所需的第一份完整状态。"""
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.snapshot())
        self._sync_from_service()
        return self.attach_runtime_state(self.app_state.snapshot())

    def refresh_devices(self) -> dict[str, Any]:
        """刷新设备并返回最新快照。"""
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.refresh_devices())
        self.service.refresh_devices()
        self._sync_from_service()
        return self.attach_runtime_state(self.app_state.snapshot())

    def connect_device(self, device_id: str) -> dict[str, Any]:
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.connect_device(device_id))
        self.service.connect(device_id)
        self.app_state.handle_connector_event({"event": "device_connected", "device_id": device_id})
        self._sync_from_service()
        return self.attach_runtime_state(self.app_state.snapshot())

    def disconnect_device(self, device_id: str) -> dict[str, Any]:
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.disconnect_device(device_id))
        self.service.disconnect(device_id)
        self.app_state.handle_connector_event(
            {"event": "device_disconnected", "device_id": device_id, "state": "disconnected"}
        )
        self._sync_from_service()
        return self.attach_runtime_state(self.app_state.snapshot())

    def update_device_rule(self, device_id: str, rule_patch: dict[str, Any]) -> dict[str, Any]:
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.update_device_rule(device_id, rule_patch))
        self.app_state.update_device_rule(device_id, rule_patch)
        return self.attach_runtime_state(self.app_state.snapshot())

    def reorder_device_priority(self, device_ids: list[str]) -> dict[str, Any]:
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.reorder_device_priority(device_ids))
        self.app_state.reorder_device_priority(device_ids)
        return self.attach_runtime_state(self.app_state.snapshot())

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.set_autostart(enabled))
        self.autostart_manager.set_enabled(enabled)
        self.app_state.config.startup.autostart = enabled
        return self.attach_runtime_state(self.app_state.snapshot())

    def set_theme(self, mode: ThemeMode) -> dict[str, Any]:
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.set_theme(mode))
        self.app_state.config.ui.theme = mode
        return self.attach_runtime_state(self.app_state.snapshot())

    def set_language(self, language: str) -> dict[str, Any]:
        if language not in {"system", "zh-CN", "en-US"}:
            raise ValueError("Unsupported language")
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.set_language(language))
        setattr(self.app_state.config.ui, "language", language)
        snapshot = self.app_state.snapshot()
        snapshot.setdefault("settings", {}).setdefault("ui", {})["language"] = language
        return self.attach_runtime_state(snapshot)

    def set_notification_policy(self, policy: NotificationPolicy) -> dict[str, Any]:
        if self.session_state is not None:
            return self.attach_runtime_state(self.session_state.set_notification_policy(policy))
        self.notification_service.update_policy(policy)
        self.app_state.config.notification.policy = policy
        return self.attach_runtime_state(self.app_state.snapshot())

    def set_reconnect(self, enabled: bool) -> dict[str, Any]:
        if self.session_state is not None and hasattr(self.session_state, "set_reconnect"):
            snapshot = self.session_state.set_reconnect(enabled)
            return self.attach_runtime_state(self._ensure_reconnect_in_snapshot(snapshot, enabled))
        self.app_state.config.reconnect = bool(enabled)
        snapshot = self.app_state.snapshot()
        return self.attach_runtime_state(self._ensure_reconnect_in_snapshot(snapshot, enabled))

    def register_window_theme_sync(self, callback: Callable[[str], bool]) -> None:
        self._window_theme_sync = callback

    def register_window_controls(
        self,
        *,
        on_minimize: Callable[[], None],
        on_toggle_maximize: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self._window_controls = {
            "minimize": on_minimize,
            "toggle_maximize": on_toggle_maximize,
            "close": on_close,
        }

    def set_runtime_state(self, **updates: Any) -> None:
        self._runtime_state = {**self._runtime_state, **updates}

    def get_runtime_state(self) -> dict[str, Any]:
        return dict(self._runtime_state)

    def attach_runtime_state(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(snapshot)
        enriched["runtime"] = self.get_runtime_state()
        return enriched

    def minimize_window(self) -> dict[str, Any]:
        callback = self._window_controls.get("minimize")
        if callable(callback):
            callback()
        return self.get_initial_state()

    def toggle_maximize_window(self) -> dict[str, Any]:
        callback = self._window_controls.get("toggle_maximize")
        if callable(callback):
            callback()
        return self.get_initial_state()

    def close_main_window(self) -> dict[str, Any]:
        callback = self._window_controls.get("close")
        if callable(callback):
            callback()
        return self.get_initial_state()

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
        """导出支持包，并把运行态与诊断态合并到同一份快照。"""
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
    """负责创建原生窗口、挂载前端页面并处理窗口级事件。"""

    def __init__(self, api: DesktopApi, ui_entrypoint: Path, webview_module=None) -> None:
        self.api = api
        self.ui_entrypoint = ui_entrypoint
        self._webview = webview_module
        self.main_window = None
        self._state_unsubscribe = None
        self._allow_close = False
        self._is_maximized = False
        self._resize_hook_hwnd: int | None = None
        self._resize_hook_original_proc: int | None = None
        self._resize_hook_callback: WNDPROC | None = None
        if hasattr(self.api, "register_window_theme_sync"):
            self.api.register_window_theme_sync(self.sync_window_theme)
        if hasattr(self.api, "register_window_controls"):
            self.api.register_window_controls(
                on_minimize=self.minimize_window,
                on_toggle_maximize=self.toggle_maximize_window,
                on_close=self.close_main_window,
            )

    def create_windows(self) -> None:
        if self.main_window is not None:
            return

        if self._webview is None:
            import webview  # type: ignore[import-not-found]

            self._webview = webview

        self._configure_drag_region_settings()
        main_url = self.ui_entrypoint.as_uri()
        self.main_window = self._webview.create_window(
            "AudioBlue",
            url=main_url,
            js_api=self.api,
            width=1180,
            height=780,
            frameless=True,
            easy_drag=False,
            hidden=True,
        )
        self._install_resize_hit_test_hook()
        window_events = getattr(self.main_window, "events", None)
        if window_events is not None and hasattr(window_events, "closing"):
            window_events.closing += self._on_main_window_closing
        if window_events is not None and hasattr(window_events, "maximized"):
            window_events.maximized += self._on_main_window_maximized
        if window_events is not None and hasattr(window_events, "restored"):
            window_events.restored += self._on_main_window_restored
        self._sync_runtime_state(push=False)

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

    def minimize_window(self) -> None:
        if self.main_window is None or not hasattr(self.main_window, "minimize"):
            return
        self.main_window.minimize()

    def toggle_maximize_window(self) -> None:
        if self.main_window is None:
            return
        if self._is_maximized:
            if hasattr(self.main_window, "restore"):
                self.main_window.restore()
            self._set_maximized(False)
            return
        if hasattr(self.main_window, "maximize"):
            self.main_window.maximize()
        self._set_maximized(True)

    def close_main_window(self) -> None:
        self._on_main_window_closing()

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
        self._restore_resize_hit_test_hook()

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
        runtime_snapshot = (
            self.api.attach_runtime_state(snapshot)
            if hasattr(self.api, "attach_runtime_state")
            else snapshot
        )
        payload = json.dumps(runtime_snapshot, ensure_ascii=False)
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

    def _on_main_window_maximized(self) -> None:
        self._set_maximized(True)

    def _on_main_window_restored(self) -> None:
        self._set_maximized(False)

    def _set_maximized(self, is_maximized: bool) -> None:
        self._is_maximized = is_maximized
        self._sync_runtime_state(push=True)

    def _sync_runtime_state(self, *, push: bool) -> None:
        if hasattr(self.api, "set_runtime_state"):
            self.api.set_runtime_state(
                chrome="custom",
                isMaximized=self._is_maximized,
                canMinimize=bool(self.main_window is not None and hasattr(self.main_window, "minimize")),
                canMaximize=bool(
                    self.main_window is not None
                    and (hasattr(self.main_window, "maximize") or hasattr(self.main_window, "restore"))
                ),
                canClose=bool(self.main_window is not None and hasattr(self.main_window, "hide")),
            )
        if push:
            self.push_state(self.api.get_initial_state())

    def _configure_drag_region_settings(self) -> None:
        """显式锁定 pywebview 拖拽区域选择器，避免默认值漂移影响自绘标题栏。"""
        settings = getattr(self._webview, "settings", None)
        if settings is None:
            return

        try:
            settings["DRAG_REGION_SELECTOR"] = ".pywebview-drag-region"
            settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = False
        except Exception:
            return

    def _install_resize_hit_test_hook(self) -> None:
        """为 frameless 窗口补回 Windows 原生边缘 resize 命中。"""
        if self.main_window is None or self._resize_hook_callback is not None:
            return

        try:
            hwnd = self._resolve_window_handle(self.main_window)
        except Exception:
            return

        border_thickness = _get_resize_border_thickness()

        def window_proc(hwnd_value, msg, wparam, lparam):
            if int(msg) == WM_NCHITTEST:
                hit = _resolve_resize_hit_test(
                    _get_window_rect(int(hwnd_value)),
                    _decode_lparam_point(int(lparam)),
                    border_thickness,
                    is_maximized=self._is_maximized,
                )
                if hit is not None:
                    return hit

            if self._resize_hook_original_proc is None:
                return 0

            return _call_window_proc(
                self._resize_hook_original_proc,
                int(hwnd_value),
                int(msg),
                int(wparam),
                int(lparam),
            )

        callback = WNDPROC(window_proc)
        original_proc = _set_window_long_ptr(
            hwnd,
            GWLP_WNDPROC,
            int(ctypes.cast(callback, ctypes.c_void_p).value or 0),
        )
        self._resize_hook_hwnd = hwnd
        self._resize_hook_original_proc = original_proc
        self._resize_hook_callback = callback

    def _restore_resize_hit_test_hook(self) -> None:
        """恢复原始窗口过程，避免销毁后保留悬空回调。"""
        if self._resize_hook_hwnd is None or self._resize_hook_original_proc is None:
            self._resize_hook_hwnd = None
            self._resize_hook_original_proc = None
            self._resize_hook_callback = None
            return

        try:
            _set_window_long_ptr(
                self._resize_hook_hwnd,
                GWLP_WNDPROC,
                self._resize_hook_original_proc,
            )
        finally:
            self._resize_hook_hwnd = None
            self._resize_hook_original_proc = None
            self._resize_hook_callback = None

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
