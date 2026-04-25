"""封装 WebView 桌面宿主与暴露给前端的 API。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Protocol
import sys
import winreg

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
WM_NCLBUTTONDOWN = 0x00A1
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
NATIVE_WINDOW_BACKGROUND_COLORS = {
    "light": "#f3f6fb",
    "dark": "#090d13",
}


@dataclass(slots=True)
class NativeResizeGripBinding:
    """记录单个原生 resize grip 的控件与交互元数据。"""

    control: object
    hit_test: int
    cursor_name: str
    mouse_handler: Callable[..., None]


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


def _release_capture() -> bool:
    """释放当前鼠标捕获，让系统进入原生 resize 流程。"""
    return bool(ctypes.windll.user32.ReleaseCapture())


def _send_window_message(hwnd: int, msg: int, wparam: int, lparam: int) -> int:
    """统一封装窗口消息发送，便于测试里打桩。"""
    sender = ctypes.windll.user32.SendMessageW
    sender.restype = LRESULT
    sender.argtypes = [wintypes.HWND, wintypes.UINT, UINT_PTR, LONG_PTR]
    return int(sender(hwnd, msg, wparam, lparam))


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


def _coerce_window_handle(value: object) -> int | None:
    """尽量把不同宿主返回的句柄对象转换成稳定的 HWND 整数。"""
    if isinstance(value, int):
        return value if value > 0 else None

    for method_name in ("ToInt64", "ToInt32"):
        method = getattr(value, method_name, None)
        if not callable(method):
            continue
        try:
            coerced = int(method())
        except (TypeError, ValueError, OverflowError):
            continue
        if coerced > 0:
            return coerced

    try:
        coerced = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return coerced if coerced > 0 else None


def _resolve_known_window_handle(window: object) -> int | None:
    """优先从窗口对象及其 native 宿主上读取已知 HWND。"""
    for attribute in ("hwnd", "_hwnd"):
        value = _coerce_window_handle(getattr(window, attribute, None))
        if value is not None:
            return value

    native = getattr(window, "native", None)
    if native is None:
        return None

    for attribute in ("hwnd", "_hwnd", "Handle", "handle"):
        value = _coerce_window_handle(getattr(native, attribute, None))
        if value is not None:
            return value

    return None


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
        self._service = service
        self._app_state = app_state
        self._autostart_manager = autostart_manager
        self._notification_service = notification_service
        self._session_state = session_state
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
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.snapshot())
        self._sync_from_service()
        return self.attach_runtime_state(self._app_state.snapshot())

    def refresh_devices(self) -> dict[str, Any]:
        """刷新设备并返回最新快照。"""
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.refresh_devices())
        self._service.refresh_devices()
        self._sync_from_service()
        return self.attach_runtime_state(self._app_state.snapshot())

    def connect_device(self, device_id: str) -> dict[str, Any]:
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.connect_device(device_id))
        self._service.connect(device_id)
        self._app_state.handle_connector_event({"event": "device_connected", "device_id": device_id})
        self._sync_from_service()
        return self.attach_runtime_state(self._app_state.snapshot())

    def disconnect_device(self, device_id: str) -> dict[str, Any]:
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.disconnect_device(device_id))
        self._service.disconnect(device_id)
        self._app_state.handle_connector_event(
            {"event": "device_disconnected", "device_id": device_id, "state": "disconnected"}
        )
        self._sync_from_service()
        return self.attach_runtime_state(self._app_state.snapshot())

    def update_device_rule(self, device_id: str, rule_patch: dict[str, Any]) -> dict[str, Any]:
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.update_device_rule(device_id, rule_patch))
        self._app_state.update_device_rule(device_id, rule_patch)
        return self.attach_runtime_state(self._app_state.snapshot())

    def reorder_device_priority(self, device_ids: list[str]) -> dict[str, Any]:
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.reorder_device_priority(device_ids))
        self._app_state.reorder_device_priority(device_ids)
        return self.attach_runtime_state(self._app_state.snapshot())

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.set_autostart(enabled))
        self._autostart_manager.set_enabled(enabled)
        self._app_state.config.startup.autostart = enabled
        return self.attach_runtime_state(self._app_state.snapshot())

    def set_theme(self, mode: ThemeMode) -> dict[str, Any]:
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.set_theme(mode))
        self._app_state.config.ui.theme = mode
        return self.attach_runtime_state(self._app_state.snapshot())

    def set_language(self, language: str) -> dict[str, Any]:
        if language not in {"system", "zh-CN", "en-US"}:
            raise ValueError("Unsupported language")
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.set_language(language))
        setattr(self._app_state.config.ui, "language", language)
        snapshot = self._app_state.snapshot()
        snapshot.setdefault("settings", {}).setdefault("ui", {})["language"] = language
        return self.attach_runtime_state(snapshot)

    def set_notification_policy(self, policy: NotificationPolicy) -> dict[str, Any]:
        if self._session_state is not None:
            return self.attach_runtime_state(self._session_state.set_notification_policy(policy))
        self._notification_service.update_policy(policy)
        self._app_state.config.notification.policy = policy
        return self.attach_runtime_state(self._app_state.snapshot())

    def set_reconnect(self, enabled: bool) -> dict[str, Any]:
        if self._session_state is not None and hasattr(self._session_state, "set_reconnect"):
            snapshot = self._session_state.set_reconnect(enabled)
            return self.attach_runtime_state(self._ensure_reconnect_in_snapshot(snapshot, enabled))
        self._app_state.config.reconnect = bool(enabled)
        snapshot = self._app_state.snapshot()
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
            config=self._app_state.config,
            devices=list(getattr(self._service, "known_devices", {}).values()),
            attempts=[
                device.last_connection_attempt
                for device in getattr(self._service, "known_devices", {}).values()
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
        if self._session_state is not None and hasattr(self._session_state, "record_client_event"):
            return self._session_state.record_client_event(payload)
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
        self._app_state.sync_devices(list(getattr(self._service, "known_devices", {}).values()))

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
        self._native_resize_form: object | None = None
        self._native_resize_hwnd: int | None = None
        self._native_resize_runtime: dict[str, Any] | None = None
        self._native_resize_grips: dict[str, NativeResizeGripBinding] = {}
        self._native_resize_form_resize_handler: Callable[..., None] | None = None
        self._native_theme_mode = self._resolve_native_window_theme_mode()
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
            background_color=self._get_native_window_background_color(self._native_theme_mode),
        )
        window_events = getattr(self.main_window, "events", None)
        if window_events is not None and hasattr(window_events, "before_show"):
            window_events.before_show += self._on_main_window_before_show
        if window_events is not None and hasattr(window_events, "shown"):
            window_events.shown += self._on_main_window_shown
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
        session_state = getattr(self.api, "_session_state", None)

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
            self._apply_native_resize_chrome_theme(mode)
            self._apply_native_title_bar_theme(self.main_window, mode)
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        self._allow_close = True
        if callable(self._state_unsubscribe):
            self._state_unsubscribe()
            self._state_unsubscribe = None
        self._dispose_native_resize_chrome()

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

    def _on_main_window_before_show(self) -> None:
        self._ensure_native_resize_chrome()

    def _on_main_window_shown(self) -> None:
        self._ensure_native_resize_chrome()

    def _on_main_window_maximized(self) -> None:
        self._set_maximized(True)

    def _on_main_window_restored(self) -> None:
        self._set_maximized(False)

    def _set_maximized(self, is_maximized: bool) -> None:
        self._is_maximized = is_maximized
        self._update_native_resize_chrome_state()
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

    def _load_native_resize_runtime(self) -> dict[str, Any]:
        """按需加载 WinForms 运行时对象，避免导入阶段绑定 GUI 依赖。"""
        import clr  # type: ignore[import-not-found]

        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")

        import System.Windows.Forms as WinForms  # type: ignore[import-not-found]
        from System.Drawing import ColorTranslator  # type: ignore[import-not-found]

        return {
            "Panel": WinForms.Panel,
            "Cursors": WinForms.Cursors,
            "MouseButtons": WinForms.MouseButtons,
            "AnchorStyles": WinForms.AnchorStyles,
            "color_from_hex": ColorTranslator.FromHtml,
        }

    def _ensure_native_resize_chrome(self) -> None:
        """在原生窗体就绪后安装一圈原生 grip，直接接管四边四角 resize。"""
        if self.main_window is None:
            return

        native_form = getattr(self.main_window, "native", None)
        if native_form is None:
            return

        hwnd = _resolve_known_window_handle(self.main_window)
        if hwnd is None:
            return

        if self._native_resize_form is native_form and self._native_resize_grips:
            self._layout_native_resize_grips()
            self._update_native_resize_chrome_state()
            return

        self._dispose_native_resize_chrome()
        runtime = self._load_native_resize_runtime()
        self._native_resize_runtime = runtime
        self._native_resize_form = native_form
        self._native_resize_hwnd = hwnd

        resize_handler = lambda *_args, **_kwargs: self._layout_native_resize_grips()
        form_resize_event = getattr(native_form, "Resize", None)
        if form_resize_event is not None:
            form_resize_event += resize_handler
        self._native_resize_form_resize_handler = resize_handler

        for name, hit_test, cursor_name in self._iter_native_resize_grip_specs():
            control = self._build_native_resize_grip_control(name, cursor_name, runtime)

            def mouse_handler(*event_args, grip_hit_test=hit_test):
                self._handle_native_resize_grip_mouse_down(grip_hit_test, *event_args)

            mouse_event = getattr(control, "MouseDown", None)
            if mouse_event is not None:
                mouse_event += mouse_handler

            controls = getattr(native_form, "Controls", None)
            if controls is not None and hasattr(controls, "Add"):
                controls.Add(control)
            if hasattr(control, "BringToFront"):
                control.BringToFront()

            self._native_resize_grips[name] = NativeResizeGripBinding(
                control=control,
                hit_test=hit_test,
                cursor_name=cursor_name,
                mouse_handler=mouse_handler,
            )

        self._layout_native_resize_grips()
        self._update_native_resize_chrome_state()
        self._apply_native_resize_chrome_theme(self._native_theme_mode)

    def _dispose_native_resize_chrome(self) -> None:
        """卸载原生 grip 与事件绑定，避免重复安装和悬空引用。"""
        native_form = self._native_resize_form
        controls = getattr(native_form, "Controls", None) if native_form is not None else None

        for binding in list(self._native_resize_grips.values()):
            mouse_event = getattr(binding.control, "MouseDown", None)
            if mouse_event is not None and hasattr(mouse_event, "__isub__"):
                try:
                    mouse_event -= binding.mouse_handler
                except Exception:
                    pass

            if controls is not None and hasattr(controls, "Remove"):
                try:
                    controls.Remove(binding.control)
                except Exception:
                    pass

            if hasattr(binding.control, "Dispose"):
                try:
                    binding.control.Dispose()
                except Exception:
                    pass

        if native_form is not None and self._native_resize_form_resize_handler is not None:
            form_resize_event = getattr(native_form, "Resize", None)
            if form_resize_event is not None and hasattr(form_resize_event, "__isub__"):
                try:
                    form_resize_event -= self._native_resize_form_resize_handler
                except Exception:
                    pass

        self._native_resize_grips = {}
        self._native_resize_form = None
        self._native_resize_hwnd = None
        self._native_resize_runtime = None
        self._native_resize_form_resize_handler = None

    def _iter_native_resize_grip_specs(self) -> tuple[tuple[str, int, str], ...]:
        """定义四边四角 grip 的命中类型和光标语义。"""
        return (
            ("top_left", HTTOPLEFT, "SizeNWSE"),
            ("top", HTTOP, "SizeNS"),
            ("top_right", HTTOPRIGHT, "SizeNESW"),
            ("left", HTLEFT, "SizeWE"),
            ("right", HTRIGHT, "SizeWE"),
            ("bottom_left", HTBOTTOMLEFT, "SizeNESW"),
            ("bottom", HTBOTTOM, "SizeNS"),
            ("bottom_right", HTBOTTOMRIGHT, "SizeNWSE"),
        )

    def _build_native_resize_grip_control(self, name: str, cursor_name: str, runtime: dict[str, Any]) -> object:
        """创建单个原生 grip 控件。"""
        panel = runtime["Panel"]()
        panel.Name = f"AudioBlueResizeGrip_{name}"
        panel.Cursor = getattr(runtime["Cursors"], cursor_name)
        panel.TabStop = False
        color_factory = runtime.get("color_from_hex")
        if callable(color_factory):
            panel.BackColor = color_factory(self._get_native_window_background_color(self._native_theme_mode))
        return panel

    def _layout_native_resize_grips(self) -> None:
        """根据当前 ClientSize 重排 grip 布局，角优先于边。"""
        if self._native_resize_form is None or not self._native_resize_grips:
            return

        client_size = getattr(self._native_resize_form, "ClientSize", None)
        width = int(getattr(client_size, "Width", 0) or 0)
        height = int(getattr(client_size, "Height", 0) or 0)
        if width <= 0 or height <= 0:
            return

        thickness = max(1, _get_resize_border_thickness())
        corner_span = min(max(thickness * 2, 16), max(thickness, min(width, height)))
        horizontal_edge_width = max(0, width - (corner_span * 2))
        vertical_edge_height = max(0, height - (corner_span * 2))

        layout = {
            "top_left": (0, 0, corner_span, corner_span),
            "top": (corner_span, 0, horizontal_edge_width, thickness),
            "top_right": (max(0, width - corner_span), 0, corner_span, corner_span),
            "left": (0, corner_span, thickness, vertical_edge_height),
            "right": (max(0, width - thickness), corner_span, thickness, vertical_edge_height),
            "bottom_left": (0, max(0, height - corner_span), corner_span, corner_span),
            "bottom": (corner_span, max(0, height - thickness), horizontal_edge_width, thickness),
            "bottom_right": (
                max(0, width - corner_span),
                max(0, height - corner_span),
                corner_span,
                corner_span,
            ),
        }

        for name, binding in self._native_resize_grips.items():
            left, top, grip_width, grip_height = layout[name]
            binding.control.Left = left
            binding.control.Top = top
            binding.control.Width = grip_width
            binding.control.Height = grip_height

    def _update_native_resize_chrome_state(self) -> None:
        """根据最大化状态切换 grip 的光标和交互能力。"""
        if self._native_resize_runtime is None or not self._native_resize_grips:
            return

        cursors = self._native_resize_runtime["Cursors"]
        for binding in self._native_resize_grips.values():
            binding.control.Cursor = (
                getattr(cursors, "Default")
                if self._is_maximized
                else getattr(cursors, binding.cursor_name)
            )

    def _resolve_native_window_theme_mode(self) -> str:
        """从当前配置或系统偏好推断宿主应使用的原生主题。"""
        configured_theme = None
        session_state = getattr(self.api, "_session_state", None)
        snapshot = getattr(session_state, "snapshot", None)
        if callable(snapshot):
            try:
                configured_theme = (
                    snapshot()
                    .get("settings", {})
                    .get("ui", {})
                    .get("theme")
                )
            except Exception:
                configured_theme = None

        if configured_theme not in {"light", "dark"}:
            app_state = getattr(self.api, "_app_state", None)
            config = getattr(app_state, "config", None)
            ui_preferences = getattr(config, "ui", None)
            configured_theme = getattr(ui_preferences, "theme", None)

        if configured_theme in {"light", "dark"}:
            return configured_theme

        return self._get_system_theme_mode()

    def _get_system_theme_mode(self) -> str:
        """读取系统浅深色偏好，失败时回退浅色。"""
        try:
            personalize_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                0,
                winreg.KEY_READ,
            )
            try:
                system_theme, _ = winreg.QueryValueEx(personalize_key, "SystemUsesLightTheme")
            finally:
                winreg.CloseKey(personalize_key)
            return "light" if int(system_theme) != 0 else "dark"
        except Exception:
            return "light"

    def _get_native_window_background_color(self, mode: str) -> str:
        """返回宿主原生边缘与 grip 使用的主题背景色。"""
        return NATIVE_WINDOW_BACKGROUND_COLORS["dark" if mode == "dark" else "light"]

    def _apply_native_resize_chrome_theme(self, mode: str) -> None:
        """同步宿主窗体和原生 grip 的底色，避免默认白底露出。"""
        resolved_mode = "dark" if mode == "dark" else "light"
        self._native_theme_mode = resolved_mode
        color_value = self._get_native_window_background_color(resolved_mode)

        color_factory = None
        if self._native_resize_runtime is not None:
            color_factory = self._native_resize_runtime.get("color_from_hex")
        native_color = color_factory(color_value) if callable(color_factory) else color_value

        if self._native_resize_form is not None:
            try:
                self._native_resize_form.BackColor = native_color
            except Exception:
                pass

        for binding in self._native_resize_grips.values():
            try:
                binding.control.BackColor = native_color
            except Exception:
                continue

    def _handle_native_resize_grip_mouse_down(self, hit_test: int, *event_args: Any) -> None:
        """把 grip 鼠标按下转换成系统原生 resize 消息。"""
        if self._native_resize_hwnd is None or self._is_maximized:
            return
        if not self._is_left_resize_mouse_button(*event_args):
            return

        _release_capture()
        _send_window_message(self._native_resize_hwnd, WM_NCLBUTTONDOWN, hit_test, 0)

    def _is_left_resize_mouse_button(self, *event_args: Any) -> bool:
        """兼容 pythonnet 事件签名，识别左键按下。"""
        if self._native_resize_runtime is None:
            return False

        event_args_object = event_args[-1] if event_args else None
        button = getattr(event_args_object, "Button", None)
        left_button = getattr(self._native_resize_runtime["MouseButtons"], "Left", None)
        if left_button is None:
            return True
        return button == left_button or str(button) == str(left_button)

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
        hwnd = _resolve_known_window_handle(window)
        if hwnd is not None:
            return hwnd

        title = getattr(window, "title", "")
        if not isinstance(title, str):
            title = ""
        hwnd = ctypes.windll.user32.FindWindowW(None, title or None)
        if hwnd:
            return int(hwnd)
        raise RuntimeError("Could not resolve window handle")
