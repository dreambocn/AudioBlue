"""覆盖 DesktopHost 在运行时窗口管理上的关键路径。"""

import inspect
import threading
from pathlib import Path

import pytest

from audio_blue import desktop_host as desktop_host_module
from audio_blue.desktop_host import (
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTLEFT,
    NATIVE_WINDOW_BACKGROUND_COLORS,
    HTRIGHT,
    HTTOP,
    HTTOPLEFT,
    HTTOPRIGHT,
    WM_NCLBUTTONDOWN,
    DesktopApi,
    DesktopHost,
    _resolve_resize_hit_test,
    find_ui_entrypoint,
)
from audio_blue.app_state import AppStateStore
from audio_blue.models import AppConfig
from audio_blue.notification_service import NotificationService


class WebviewWindowStub:
    """模拟 pywebview 窗口对象，记录显示、隐藏和脚本注入行为。"""

    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
        self.native = None
        self.show_called = False
        self.hide_called = False
        self.destroy_called = False
        self.minimize_called = False
        self.maximize_called = False
        self.restore_called = False
        self.scripts: list[str] = []
        self.events = type("Events", (), {})()
        self.events.before_show = WindowEventStub()
        self.events.shown = WindowEventStub()
        self.events.closing = WindowEventStub()
        self.events.maximized = WindowEventStub()
        self.events.restored = WindowEventStub()

    def show(self):
        self.show_called = True

    def hide(self):
        self.hide_called = True

    def destroy(self):
        self.destroy_called = True

    def minimize(self):
        self.minimize_called = True

    def maximize(self):
        self.maximize_called = True

    def restore(self):
        self.restore_called = True

    def evaluate_js(self, script: str):
        self.scripts.append(script)


class WindowEventStub:
    """模拟 pywebview Event，兼容 set/is_set 与测试中的主动触发。"""

    def __init__(self):
        self.handlers: list[object] = []
        self._is_set = False

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __isub__(self, handler):
        self.handlers.remove(handler)
        return self

    def set(self, *args, **kwargs):
        self._is_set = True
        return any(result is False for result in self.fire(*args, **kwargs))

    def fire(self, *args, **kwargs):
        self._is_set = True
        return [handler(*args, **kwargs) for handler in self.handlers]

    def is_set(self):
        return self._is_set


class IntPtrLikeStub:
    """模拟 WinForms Handle 常见的 IntPtr 风格包装对象。"""

    def __init__(self, value: int):
        self.value = value

    def ToInt64(self):
        return self.value

    def __int__(self):
        return self.value


class NativeControlCollectionStub:
    """模拟 WinForms 控件集合，保留 Add/Remove/Count 等最小行为。"""

    def __init__(self):
        self.items: list[object] = []

    @property
    def Count(self):
        return len(self.items)

    def Add(self, control):
        if control in self.items:
            return control
        self.items.append(control)
        control.Parent = self
        return control

    def Remove(self, control):
        if control in self.items:
            self.items.remove(control)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, index):
        return self.items[index]


class NativeCursorCatalogStub:
    """模拟 WinForms Cursors，方便断言具体光标类型。"""

    Default = "Default"
    SizeWE = "SizeWE"
    SizeNS = "SizeNS"
    SizeNWSE = "SizeNWSE"
    SizeNESW = "SizeNESW"


class NativeMouseButtonsStub:
    """模拟 WinForms MouseButtons。"""

    Left = "Left"
    Right = "Right"


class NativeAnchorStylesStub:
    """模拟 WinForms AnchorStyles 常量。"""

    Left = 1
    Top = 2
    Right = 4
    Bottom = 8


class NativeMouseEventArgsStub:
    """模拟鼠标事件参数。"""

    def __init__(self, button="Left"):
        self.Button = button


class NativePanelStub:
    """模拟覆盖在 BrowserForm 上方的原生 resize grip。"""

    def __init__(self):
        self.Name = ""
        self.Cursor = None
        self.Anchor = 0
        self.Visible = True
        self.Left = 0
        self.Top = 0
        self.Width = 0
        self.Height = 0
        self.BackColor = None
        self.Parent = None
        self.TabStop = False
        self.bring_to_front_calls = 0
        self.dispose_called = False
        self.MouseDown = WindowEventStub()

    def BringToFront(self):
        self.bring_to_front_calls += 1

    def Dispose(self):
        self.dispose_called = True


class NativeSizeStub:
    """模拟 WinForms ClientSize。"""

    def __init__(self, width: int, height: int):
        self.Width = width
        self.Height = height


class NativeFormStub:
    """模拟 pywebview BrowserForm，便于验证 grip 安装与清理。"""

    def __init__(self, handle: int = 2468, width: int = 1180, height: int = 780):
        self.Handle = IntPtrLikeStub(handle)
        self.ClientSize = NativeSizeStub(width, height)
        self.Controls = NativeControlCollectionStub()
        self.Resize = WindowEventStub()

    def set_client_size(self, width: int, height: int):
        self.ClientSize = NativeSizeStub(width, height)


def create_native_resize_runtime_stub():
    """构造 DesktopHost 原生 grip 创建所需的最小 WinForms 运行时。"""
    return {
        "Panel": NativePanelStub,
        "Cursors": NativeCursorCatalogStub,
        "MouseButtons": NativeMouseButtonsStub,
        "AnchorStyles": NativeAnchorStylesStub,
        "color_from_hex": lambda value: value,
    }


class WebviewModuleStub:
    """模拟 pywebview 模块，记录建窗参数和 start 调用。"""

    def __init__(self):
        self.calls: list[dict[str, object]] = []
        self.start_call: dict[str, object] | None = None
        self.settings = {
            "DRAG_REGION_SELECTOR": ".unexpected-drag-region",
            "DRAG_REGION_DIRECT_TARGET_ONLY": True,
        }

    def create_window(self, title: str, url: str, **kwargs):
        self.calls.append({"title": title, "url": url, "kwargs": kwargs})
        return WebviewWindowStub(title=title, url=url)

    def start(self, func, *args, **kwargs):
        self.start_call = {
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "thread_name": threading.current_thread().name,
        }
        if func is not None:
            func()


def _collect_pywebview_api_scan_errors(obj: object) -> tuple[dict[str, object], list[str]]:
    """按 pywebview 的递归规则扫描 API，对外暴露名与错误都返回给测试断言。"""
    exposed_objects: list[int] = []
    functions: dict[str, object] = {}
    errors: list[str] = []

    def get_functions(target: object, base_name: str = "") -> None:
        target_id = id(target)
        if target_id in exposed_objects:
            return

        exposed_objects.append(target_id)
        for name in dir(target):
            full_name = f"{base_name}.{name}" if base_name else name
            try:
                nested_target = getattr(target, name)
                if name.startswith("_") or getattr(nested_target, "_serializable", True) is False:
                    continue

                attr = getattr(target, name)
                if inspect.ismethod(attr):
                    functions[full_name] = attr
                elif inspect.isclass(attr) or (
                    isinstance(attr, object) and not callable(attr) and hasattr(attr, "__module__")
                ):
                    get_functions(attr, full_name)
            except Exception as exc:  # pragma: no cover - 分支由失败断言消费
                errors.append(f"{full_name}: {exc}")

    get_functions(obj)
    return functions, errors


def create_api(tmp_path: Path, session_state=None):
    """构造运行时宿主测试共用的最小 DesktopApi。"""
    return DesktopApi(
        service=type("ServiceStub", (), {"known_devices": {}, "active_connections": {}})(),
        app_state=AppStateStore(config=AppConfig()),
        autostart_manager=type("AutostartStub", (), {"set_enabled": lambda self, enabled: None})(),
        notification_service=NotificationService(),
        diagnostics_exporter=lambda snapshot, path: path,
        open_bluetooth_settings=lambda: None,
        diagnostics_output_dir=tmp_path,
        session_state=session_state,
    )


def test_desktop_api_hides_internal_runtime_dependencies_from_pywebview_scan(tmp_path):
    class StorageStub:
        """模拟会触发 pywebview 递归扫描的 Path 型内部状态。"""

        def __init__(self, root: Path):
            self.db_path = root / "audioblue.db"
            self.legacy_config_path = root / "config.json"
            self.legacy_log_path = root / "audioblue.log"
            self.legacy_diagnostics_dir = root / "diagnostics"

    class SessionStateStub:
        """模拟运行时会话对象，保持最小 snapshot 能力。"""

        def __init__(self, root: Path):
            self.storage = StorageStub(root)

        def snapshot(self):
            return {"devices": []}

    api = create_api(tmp_path, session_state=SessionStateStub(tmp_path))

    functions, errors = _collect_pywebview_api_scan_errors(api)

    assert "get_initial_state" in functions
    assert errors == []
    assert not any(name.startswith("session_state") for name in functions)


def test_desktop_api_set_reconnect_updates_snapshot_field(tmp_path):
    api = create_api(tmp_path)

    snapshot = api.set_reconnect(True)

    assert snapshot["settings"]["startup"]["reconnectOnNextStart"] is True


def test_desktop_api_sync_window_theme_calls_registered_handler(tmp_path):
    api = create_api(tmp_path)
    calls: list[str] = []
    api.register_window_theme_sync(lambda mode: calls.append(mode))

    result = api.sync_window_theme("dark")

    assert result == {"mode": "dark", "applied": True}
    assert calls == ["dark"]


def test_find_ui_entrypoint_returns_built_index(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")

    resolved = find_ui_entrypoint(tmp_path)

    assert resolved == index_path


def test_find_ui_entrypoint_accepts_pyinstaller_internal_ui_index(tmp_path):
    index_path = tmp_path / "_internal" / "ui" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")

    resolved = find_ui_entrypoint(tmp_path)

    assert resolved == index_path


def test_find_ui_entrypoint_requires_built_assets_not_raw_vite_source(tmp_path):
    index_path = tmp_path / "ui" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="npm run build"):
        find_ui_entrypoint(tmp_path)


def test_create_windows_only_builds_main_window(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    webview = WebviewModuleStub()
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=webview,
    )
    host._native_theme_mode = "light"

    host.create_windows()

    assert len(webview.calls) == 1
    assert webview.calls[0]["url"] == index_path.as_uri()
    assert webview.calls[0]["kwargs"]["frameless"] is True
    assert webview.calls[0]["kwargs"]["easy_drag"] is False
    assert webview.calls[0]["kwargs"]["background_color"] == NATIVE_WINDOW_BACKGROUND_COLORS["light"]
    assert webview.settings["DRAG_REGION_SELECTOR"] == ".pywebview-drag-region"
    assert webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] is False


def test_create_windows_uses_resolved_theme_background_color(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    webview = WebviewModuleStub()
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=webview,
    )
    monkeypatch.setattr(host, "_resolve_native_window_theme_mode", lambda: "dark")

    host.create_windows()

    assert webview.calls[0]["kwargs"]["background_color"] == NATIVE_WINDOW_BACKGROUND_COLORS["dark"]


def test_create_windows_registers_native_ready_resize_chrome_callbacks(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    calls: list[str] = []
    monkeypatch.setattr(host, "_ensure_native_resize_chrome", lambda: calls.append("install"))

    host.create_windows()

    assert calls == []
    assert len(host.main_window.events.before_show.handlers) == 1
    assert len(host.main_window.events.shown.handlers) == 1


def test_before_show_installs_native_resize_chrome_when_native_form_is_ready(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host._native_theme_mode = "light"
    monkeypatch.setattr(host, "_load_native_resize_runtime", create_native_resize_runtime_stub)

    host.create_windows()
    host.main_window.native = NativeFormStub()

    host.main_window.events.before_show.set()

    assert host._native_resize_form is host.main_window.native
    assert host._native_resize_hwnd == 2468
    assert len(host._native_resize_grips) == 8
    assert host.main_window.native.Controls.Count == 8
    assert host.main_window.native.BackColor == NATIVE_WINDOW_BACKGROUND_COLORS["light"]
    assert all(
        binding.control.BackColor == NATIVE_WINDOW_BACKGROUND_COLORS["light"]
        for binding in host._native_resize_grips.values()
    )


def test_shown_retries_native_resize_chrome_after_before_show_misses_form(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    monkeypatch.setattr(host, "_load_native_resize_runtime", create_native_resize_runtime_stub)

    host.create_windows()
    host.main_window.events.before_show.set()
    host.main_window.native = NativeFormStub()
    host.main_window.events.shown.set()

    assert host._native_resize_form is host.main_window.native
    assert len(host._native_resize_grips) == 8


def test_native_ready_events_do_not_reinstall_native_resize_chrome(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    monkeypatch.setattr(host, "_load_native_resize_runtime", create_native_resize_runtime_stub)

    host.create_windows()
    host.main_window.native = NativeFormStub()

    host.main_window.events.before_show.set()
    host.main_window.events.before_show.set()
    host.main_window.events.shown.set()

    assert len(host._native_resize_grips) == 8
    assert host.main_window.native.Controls.Count == 8


def test_create_windows_does_not_pass_gui_to_create_window(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    webview = WebviewModuleStub()
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=webview,
    )

    host.create_windows()

    assert all("gui" not in call["kwargs"] for call in webview.calls)


def test_desktop_api_window_controls_call_registered_handlers(tmp_path):
    api = create_api(tmp_path)
    calls: list[str] = []
    api.register_window_controls(
        on_minimize=lambda: calls.append("minimize"),
        on_toggle_maximize=lambda: calls.append("toggle"),
        on_close=lambda: calls.append("close"),
    )

    api.minimize_window()
    api.toggle_maximize_window()
    api.close_main_window()

    assert calls == ["minimize", "toggle", "close"]


def test_resolve_resize_hit_test_maps_edges_and_corners():
    rect = (100, 100, 400, 300)
    border = 12

    assert _resolve_resize_hit_test(rect, (101, 101), border, is_maximized=False) == HTTOPLEFT
    assert _resolve_resize_hit_test(rect, (398, 101), border, is_maximized=False) == HTTOPRIGHT
    assert _resolve_resize_hit_test(rect, (101, 298), border, is_maximized=False) == HTBOTTOMLEFT
    assert _resolve_resize_hit_test(rect, (398, 298), border, is_maximized=False) == HTBOTTOMRIGHT
    assert _resolve_resize_hit_test(rect, (101, 180), border, is_maximized=False) == HTLEFT
    assert _resolve_resize_hit_test(rect, (398, 180), border, is_maximized=False) == HTRIGHT
    assert _resolve_resize_hit_test(rect, (250, 101), border, is_maximized=False) == HTTOP
    assert _resolve_resize_hit_test(rect, (250, 298), border, is_maximized=False) == HTBOTTOM
    assert _resolve_resize_hit_test(rect, (250, 180), border, is_maximized=False) is None


def test_resolve_resize_hit_test_disables_maximized_and_clamps_border():
    rect = (0, 0, 18, 18)

    assert _resolve_resize_hit_test(rect, (1, 1), 20, is_maximized=True) is None
    assert _resolve_resize_hit_test(rect, (9, 9), 20, is_maximized=False) is None
    assert _resolve_resize_hit_test(rect, (1, 9), 20, is_maximized=False) == HTLEFT
    assert _resolve_resize_hit_test(rect, (16, 9), 20, is_maximized=False) == HTRIGHT


def test_native_resize_chrome_installs_all_grips_with_expected_hit_tests_and_cursors(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.main_window = WebviewWindowStub("AudioBlue", index_path.as_uri())
    host.main_window.native = NativeFormStub()
    monkeypatch.setattr(host, "_load_native_resize_runtime", create_native_resize_runtime_stub)

    host._ensure_native_resize_chrome()

    expected = {
        "top_left": (HTTOPLEFT, "SizeNWSE"),
        "top": (HTTOP, "SizeNS"),
        "top_right": (HTTOPRIGHT, "SizeNESW"),
        "left": (HTLEFT, "SizeWE"),
        "right": (HTRIGHT, "SizeWE"),
        "bottom_left": (HTBOTTOMLEFT, "SizeNESW"),
        "bottom": (HTBOTTOM, "SizeNS"),
        "bottom_right": (HTBOTTOMRIGHT, "SizeNWSE"),
    }

    assert set(host._native_resize_grips) == set(expected)
    for name, (hit_test, cursor_name) in expected.items():
        grip = host._native_resize_grips[name]
        assert grip.hit_test == hit_test
        assert grip.control.Cursor == cursor_name
        assert grip.control.bring_to_front_calls == 1


def test_native_resize_grip_mouse_down_calls_release_capture_and_send_message(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.main_window = WebviewWindowStub("AudioBlue", index_path.as_uri())
    host.main_window.native = NativeFormStub()
    monkeypatch.setattr(host, "_load_native_resize_runtime", create_native_resize_runtime_stub)
    release_calls: list[str] = []
    send_calls: list[tuple[int, int, int, int]] = []
    monkeypatch.setattr(desktop_host_module, "_release_capture", lambda: release_calls.append("release") or True)
    monkeypatch.setattr(
        desktop_host_module,
        "_send_window_message",
        lambda hwnd, msg, wparam, lparam: send_calls.append((hwnd, msg, wparam, lparam)) or 0,
    )

    host._ensure_native_resize_chrome()
    host._native_resize_grips["left"].control.MouseDown.fire(NativeMouseEventArgsStub("Left"))

    assert release_calls == ["release"]
    assert send_calls == [(2468, WM_NCLBUTTONDOWN, HTLEFT, 0)]


def test_resolve_window_handle_accepts_int_ptr_like_native_handle(tmp_path):
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=tmp_path / "ui" / "dist" / "index.html",
        webview_module=WebviewModuleStub(),
    )
    window = WebviewWindowStub("AudioBlue", "file:///test/index.html")
    window.native = type("NativeStub", (), {"Handle": IntPtrLikeStub(2468)})()

    resolved = host._resolve_window_handle(window)

    assert resolved == 2468


def test_maximized_native_resize_grips_do_not_send_resize_message_until_restored(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.main_window = WebviewWindowStub("AudioBlue", index_path.as_uri())
    host.main_window.native = NativeFormStub()
    monkeypatch.setattr(host, "_load_native_resize_runtime", create_native_resize_runtime_stub)
    send_calls: list[tuple[int, int, int, int]] = []
    monkeypatch.setattr(desktop_host_module, "_release_capture", lambda: True)
    monkeypatch.setattr(
        desktop_host_module,
        "_send_window_message",
        lambda hwnd, msg, wparam, lparam: send_calls.append((hwnd, msg, wparam, lparam)) or 0,
    )

    host._ensure_native_resize_chrome()
    host._set_maximized(True)
    host._native_resize_grips["top"].control.MouseDown.fire(NativeMouseEventArgsStub("Left"))
    host._set_maximized(False)
    host._native_resize_grips["top"].control.MouseDown.fire(NativeMouseEventArgsStub("Left"))

    assert send_calls == [(2468, WM_NCLBUTTONDOWN, HTTOP, 0)]
    assert host._native_resize_grips["top"].control.Visible is True


def test_native_resize_chrome_relayouts_grips_on_form_resize(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.main_window = WebviewWindowStub("AudioBlue", index_path.as_uri())
    host.main_window.native = NativeFormStub(width=1180, height=780)
    monkeypatch.setattr(host, "_load_native_resize_runtime", create_native_resize_runtime_stub)
    monkeypatch.setattr(desktop_host_module, "_get_resize_border_thickness", lambda: 12)

    host._ensure_native_resize_chrome()
    host.main_window.native.set_client_size(900, 600)
    host.main_window.native.Resize.fire()

    assert host._native_resize_grips["right"].control.Left == 888
    assert host._native_resize_grips["bottom"].control.Top == 588
    assert host._native_resize_grips["bottom_right"].control.Left == 876


def test_dispose_native_resize_chrome_releases_grips_and_handlers(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.main_window = WebviewWindowStub("AudioBlue", index_path.as_uri())
    host.main_window.native = NativeFormStub()
    monkeypatch.setattr(host, "_load_native_resize_runtime", create_native_resize_runtime_stub)

    host._ensure_native_resize_chrome()
    form = host.main_window.native
    grips = [binding.control for binding in host._native_resize_grips.values()]

    host._dispose_native_resize_chrome()

    assert form.Controls.Count == 0
    assert all(grip.dispose_called for grip in grips)
    assert form.Resize.handlers == []
    assert host._native_resize_grips == {}
    assert host._native_resize_form is None
    assert host._native_resize_hwnd is None


def test_run_starts_webview_in_current_thread_with_edgechromium(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    webview = WebviewModuleStub()
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=webview,
    )

    host.run()

    assert webview.start_call is not None
    assert webview.start_call["thread_name"] == threading.current_thread().name
    assert webview.start_call["kwargs"] == {"gui": "edgechromium", "http_server": False}


def test_show_main_window_requires_created_window(tmp_path):
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=tmp_path / "ui" / "dist" / "index.html",
        webview_module=WebviewModuleStub(),
    )

    with pytest.raises(RuntimeError, match="Main window has not been created"):
        host.show_main_window()


def test_show_quick_panel_is_not_supported(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.create_windows()

    with pytest.raises(RuntimeError, match="Quick panel is not part of the runtime path"):
        host.show_quick_panel()


def test_shutdown_destroys_existing_windows(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    webview = WebviewModuleStub()
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=webview,
    )
    host.create_windows()
    host.main_window.events.shown.set()

    host.shutdown()

    assert host.main_window.destroy_called is True


def test_shutdown_restores_resize_hit_test_hook_before_destroying_window(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    restore_calls: list[str] = []
    monkeypatch.setattr(host, "_dispose_native_resize_chrome", lambda: restore_calls.append("restore"))

    host.create_windows()
    host.shutdown()

    assert restore_calls == ["restore"]


def test_main_window_close_hides_window_instead_of_exiting(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    webview = WebviewModuleStub()
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=webview,
    )
    host.create_windows()

    results = host.main_window.events.closing.fire()

    assert results == [False]
    assert host.main_window.hide_called is True
    assert host.main_window.destroy_called is False


class SessionStateStub:
    """模拟会话状态推送通道，验证浏览器事件桥接。"""

    def __init__(self):
        self.listener = None

    def subscribe(self, callback):
        self.listener = callback

        def unsubscribe():
            self.listener = None

        return unsubscribe

    def emit(self, payload):
        if callable(self.listener):
            self.listener(payload)


def test_run_subscribes_state_push_channel_and_dispatches_browser_event(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    webview = WebviewModuleStub()
    session_state = SessionStateStub()
    api = create_api(tmp_path, session_state=session_state)
    host = DesktopHost(
        api=api,
        ui_entrypoint=index_path,
        webview_module=webview,
    )

    host.run()
    session_state.emit({"devices": [{"deviceId": "device-1"}]})

    assert host.main_window.scripts
    assert "audioblue:state" in host.main_window.scripts[-1]


def test_maximize_and_restore_push_runtime_state_snapshot(tmp_path):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    webview = WebviewModuleStub()
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=webview,
    )

    host.create_windows()
    host.main_window.events.maximized.fire()
    host.main_window.events.restored.fire()

    assert any('"isMaximized": true' in script for script in host.main_window.scripts)
    assert any('"isMaximized": false' in script for script in host.main_window.scripts)


def test_desktop_host_sync_window_theme_returns_false_without_window(tmp_path):
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=tmp_path / "ui" / "dist" / "index.html",
        webview_module=WebviewModuleStub(),
    )

    assert host.sync_window_theme("dark") is False


def test_desktop_host_sync_window_theme_uses_native_theme_applier(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.create_windows()
    calls: list[tuple[object, str]] = []
    chrome_calls: list[str] = []
    monkeypatch.setattr(
        host,
        "_apply_native_title_bar_theme",
        lambda window, mode: calls.append((window, mode)),
    )
    monkeypatch.setattr(
        host,
        "_apply_native_resize_chrome_theme",
        lambda mode: chrome_calls.append(mode),
    )

    applied = host.sync_window_theme("light")

    assert applied is True
    assert len(calls) == 1
    assert calls[0][1] == "light"
    assert chrome_calls == ["light"]


def test_desktop_host_sync_window_theme_swallow_errors(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.create_windows()

    def raise_error(_window, _mode):
        raise RuntimeError("boom")

    monkeypatch.setattr(host, "_apply_native_title_bar_theme", raise_error)

    assert host.sync_window_theme("dark") is False
