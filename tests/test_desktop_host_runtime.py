import threading
from pathlib import Path

import pytest

from audio_blue.desktop_host import DesktopApi, DesktopHost, find_ui_entrypoint
from audio_blue.app_state import AppStateStore
from audio_blue.models import AppConfig
from audio_blue.notification_service import NotificationService


class WebviewWindowStub:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
        self.show_called = False
        self.destroy_called = False

    def show(self):
        self.show_called = True

    def destroy(self):
        self.destroy_called = True


class WebviewModuleStub:
    def __init__(self):
        self.calls: list[dict[str, object]] = []
        self.start_call: dict[str, object] | None = None

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
    return DesktopApi(
        service=type("ServiceStub", (), {"known_devices": {}, "active_connections": {}})(),
        app_state=AppStateStore(config=AppConfig()),
        autostart_manager=type("AutostartStub", (), {"set_enabled": lambda self, enabled: None})(),
        notification_service=NotificationService(),
        diagnostics_exporter=lambda snapshot, path: path,
        open_bluetooth_settings=lambda: None,
        diagnostics_output_dir=tmp_path,
    )


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


def test_create_windows_uses_main_and_quick_panel_urls(tmp_path):
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

    assert len(webview.calls) == 2
    assert webview.calls[0]["url"] == index_path.as_uri()
    assert webview.calls[1]["url"] == f"{index_path.as_uri()}#quick-panel"


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


def test_show_quick_panel_requires_created_window(tmp_path):
    host = DesktopHost(
        api=create_api(tmp_path),
        ui_entrypoint=tmp_path / "ui" / "dist" / "index.html",
        webview_module=WebviewModuleStub(),
    )

    with pytest.raises(RuntimeError, match="Quick panel window has not been created"):
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

    assert host.quick_panel_window.destroy_called is True
    assert host.main_window.destroy_called is True
