from pathlib import Path

from audio_blue.desktop_host import DesktopApi, DesktopHost, find_ui_entrypoint
from audio_blue.app_state import AppStateStore
from audio_blue.models import AppConfig
from audio_blue.notification_service import NotificationService


class WebviewWindowStub:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
        self.show_called = False

    def show(self):
        self.show_called = True


class WebviewModuleStub:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def create_window(self, title: str, url: str, **kwargs):
        self.calls.append({"title": title, "url": url, "kwargs": kwargs})
        return WebviewWindowStub(title=title, url=url)


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
