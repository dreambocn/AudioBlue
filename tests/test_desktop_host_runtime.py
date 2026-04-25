"""覆盖 DesktopHost 在运行时窗口管理上的关键路径。"""

import threading
from pathlib import Path

import pytest

from audio_blue import desktop_host as desktop_host_module
from audio_blue.desktop_host import (
    GWLP_WNDPROC,
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTLEFT,
    HTRIGHT,
    HTTOP,
    HTTOPLEFT,
    HTTOPRIGHT,
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
        self.show_called = False
        self.hide_called = False
        self.destroy_called = False
        self.minimize_called = False
        self.maximize_called = False
        self.restore_called = False
        self.scripts: list[str] = []
        self.events = type("Events", (), {})()
        self.events.closing = ClosingEventStub()
        self.events.maximized = ClosingEventStub()
        self.events.restored = ClosingEventStub()

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


class ClosingEventStub:
    """模拟 pywebview 的关闭事件集合，便于主动触发回调。"""

    def __init__(self):
        self.handlers: list[object] = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self):
        return [handler() for handler in self.handlers]


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


def create_api(tmp_path: Path):
    """构造运行时宿主测试共用的最小 DesktopApi。"""
    return DesktopApi(
        service=type("ServiceStub", (), {"known_devices": {}, "active_connections": {}})(),
        app_state=AppStateStore(config=AppConfig()),
        autostart_manager=type("AutostartStub", (), {"set_enabled": lambda self, enabled: None})(),
        notification_service=NotificationService(),
        diagnostics_exporter=lambda snapshot, path: path,
        open_bluetooth_settings=lambda: None,
        diagnostics_output_dir=tmp_path,
    )


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

    host.create_windows()

    assert len(webview.calls) == 1
    assert webview.calls[0]["url"] == index_path.as_uri()
    assert webview.calls[0]["kwargs"]["frameless"] is True
    assert webview.calls[0]["kwargs"]["easy_drag"] is False
    assert webview.settings["DRAG_REGION_SELECTOR"] == ".pywebview-drag-region"
    assert webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] is False


def test_create_windows_installs_resize_hit_test_hook(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    calls: list[str] = []
    monkeypatch.setattr(host, "_install_resize_hit_test_hook", lambda: calls.append("install"))

    host.create_windows()

    assert calls == ["install"]


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


def test_install_resize_hit_test_hook_registers_original_proc_and_callback(tmp_path, monkeypatch):
    index_path = tmp_path / "ui" / "dist" / "index.html"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("<html></html>", encoding="utf-8")
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=index_path,
        webview_module=WebviewModuleStub(),
    )
    host.main_window = WebviewWindowStub("AudioBlue", index_path.as_uri())
    host.main_window.hwnd = 2468
    set_calls: list[tuple[int, int, int]] = []

    monkeypatch.setattr(
        desktop_host_module,
        "_set_window_long_ptr",
        lambda hwnd, index, value: set_calls.append((hwnd, index, value)) or 97531,
    )

    host._install_resize_hit_test_hook()

    assert set_calls
    assert set_calls[0][0] == 2468
    assert set_calls[0][1] == GWLP_WNDPROC
    assert host._resize_hook_hwnd == 2468
    assert host._resize_hook_original_proc == 97531
    assert host._resize_hook_callback is not None


def test_restore_resize_hit_test_hook_restores_original_proc_and_clears_state(tmp_path, monkeypatch):
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=tmp_path / "ui" / "dist" / "index.html",
        webview_module=WebviewModuleStub(),
    )
    restore_calls: list[tuple[int, int, int]] = []
    host._resize_hook_hwnd = 2468
    host._resize_hook_original_proc = 97531
    host._resize_hook_callback = object()

    monkeypatch.setattr(
        desktop_host_module,
        "_set_window_long_ptr",
        lambda hwnd, index, value: restore_calls.append((hwnd, index, value)) or 0,
    )

    host._restore_resize_hit_test_hook()

    assert restore_calls == [(2468, GWLP_WNDPROC, 97531)]
    assert host._resize_hook_hwnd is None
    assert host._resize_hook_original_proc is None
    assert host._resize_hook_callback is None


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
    monkeypatch.setattr(host, "_restore_resize_hit_test_hook", lambda: restore_calls.append("restore"))

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
    api = create_api(tmp_path)
    api.session_state = session_state
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
    monkeypatch.setattr(
        host,
        "_apply_native_title_bar_theme",
        lambda window, mode: calls.append((window, mode)),
    )

    applied = host.sync_window_theme("light")

    assert applied is True
    assert len(calls) == 1
    assert calls[0][1] == "light"


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
