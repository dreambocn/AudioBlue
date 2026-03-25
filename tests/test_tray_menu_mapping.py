"""覆盖托盘菜单文案、命令映射与窗口交互路径。"""

import logging

import pywintypes
import win32con

from audio_blue.models import AppConfig
from audio_blue.models import DeviceSummary
from audio_blue.tray_host import TrayHost, build_menu_entries


def test_build_menu_entries_includes_static_actions_and_toggle():
    entries = build_menu_entries([], reconnect_enabled=True, language="en-US")
    labels = [entry.label for entry in entries]

    assert labels[:2] == ["Refresh Devices", "Reconnect On Next Start"]
    assert "Open Control Center" in labels
    assert "Bluetooth Settings" in labels
    assert labels[-1] == "Exit"
    toggle = next(entry for entry in entries if entry.action == "toggle_reconnect")
    assert toggle.checked is True
    language = next(entry for entry in entries if entry.action == "set_language")
    assert [item.label for item in language.children] == ["Follow System", "Chinese", "English"]
    assert language.children[2].checked is True


def test_build_menu_entries_adds_one_entry_per_device_with_stateful_labels():
    devices = [
        DeviceSummary(device_id="device-1", name="Headphones", connection_state="connected"),
        DeviceSummary(device_id="device-2", name="Speaker", connection_state="disconnected"),
    ]

    entries = build_menu_entries(devices, reconnect_enabled=False, language="en-US")
    device_entries = [entry for entry in entries if entry.action in {"connect_device", "disconnect_device"}]

    assert [entry.label for entry in device_entries] == [
        "Disconnect Headphones",
        "Connect Speaker",
    ]
    assert [entry.device_id for entry in device_entries] == ["device-1", "device-2"]


def test_build_menu_entries_localizes_labels():
    entries = build_menu_entries([], reconnect_enabled=True, language="zh-CN")
    labels = [entry.label for entry in entries]

    assert labels[:3] == ["刷新设备", "下次启动时自动重连", "打开控制中心"]
    language = next(entry for entry in entries if entry.action == "set_language")
    assert [item.label for item in language.children] == ["跟随系统", "中文", "英文"]
    assert language.children[1].checked is True


class ServiceStub:
    """提供托盘宿主所需的最小服务接口。"""

    def __init__(self):
        self.known_devices = {}
        self.active_connections = {}
        self.shutdown_called = False

    def shutdown(self):
        self.shutdown_called = True


class SessionStateStub:
    """模拟托盘读取的会话快照与设备操作入口。"""

    def __init__(self):
        self.calls: list[str] = []
        self._devices = [
            DeviceSummary(device_id="device-1", name="Headphones", connection_state="connected"),
        ]
        self._reconnect = True
        self._language = "system"

    def list_devices(self):
        return list(self._devices)

    def snapshot(self):
        return {
            "settings": {
                "startup": {
                    "reconnectOnNextStart": self._reconnect,
                },
                "ui": {
                    "language": self._language,
                },
            }
        }

    def refresh_devices(self):
        self.calls.append("refresh")

    def connect_device(self, device_id: str):
        self.calls.append(f"connect:{device_id}")

    def disconnect_device(self, device_id: str):
        self.calls.append(f"disconnect:{device_id}")

    def set_reconnect(self, enabled: bool):
        self._reconnect = enabled
        self.calls.append(f"reconnect:{enabled}")

    def set_language(self, language: str):
        self._language = language
        self.calls.append(f"language:{language}")


def test_show_menu_tolerates_set_foreground_window_error(monkeypatch):
    host = TrayHost(
        service=ServiceStub(),
        config=AppConfig(),
        logger=logging.getLogger("tray-test"),
    )
    host._hwnd = 123
    calls: list[str] = []

    monkeypatch.setattr("audio_blue.tray_host.win32gui.CreatePopupMenu", lambda: object())
    monkeypatch.setattr("audio_blue.tray_host.win32gui.AppendMenu", lambda *args: None)
    monkeypatch.setattr("audio_blue.tray_host.win32gui.GetCursorPos", lambda: (10, 20))

    def raise_foreground_error(_hwnd: int) -> None:
        raise pywintypes.error(0, "SetForegroundWindow", "No error message is available")

    monkeypatch.setattr("audio_blue.tray_host.win32gui.SetForegroundWindow", raise_foreground_error)
    monkeypatch.setattr(
        "audio_blue.tray_host.win32gui.TrackPopupMenu",
        lambda *args: calls.append("tracked"),
    )

    host._show_menu()

    assert calls == ["tracked"]


def test_on_destroy_calls_shutdown_ui_before_service_shutdown(monkeypatch):
    service = ServiceStub()
    call_order: list[str] = []
    host = TrayHost(
        service=service,
        config=AppConfig(),
        logger=logging.getLogger("tray-test"),
        shutdown_ui=lambda: call_order.append("shutdown_ui"),
    )
    host._notify_id = ("notify",)

    monkeypatch.setattr(
        "audio_blue.tray_host.win32gui.Shell_NotifyIcon",
        lambda *args: call_order.append("notify_delete"),
    )
    monkeypatch.setattr(
        "audio_blue.tray_host.save_config",
        lambda config: call_order.append("save_config"),
    )
    monkeypatch.setattr(
        "audio_blue.tray_host.win32gui.PostQuitMessage",
        lambda code: call_order.append(f"quit:{code}"),
    )

    host._on_destroy(0, 0, 0, 0)

    assert call_order == ["notify_delete", "shutdown_ui", "save_config", "quit:0"]
    assert service.shutdown_called is True


def test_on_command_uses_session_state_for_device_actions():
    state = SessionStateStub()
    host = TrayHost(
        service=ServiceStub(),
        config=AppConfig(),
        logger=logging.getLogger("tray-test"),
        session_state=state,
    )
    host._command_map = {
        1000: type("Entry", (), {"action": "connect_device", "device_id": "device-1"})(),
        1001: type("Entry", (), {"action": "disconnect_device", "device_id": "device-1"})(),
        1002: type("Entry", (), {"action": "refresh_devices", "device_id": None})(),
    }

    host._on_command(0, 0, 1000, 0)
    host._on_command(0, 0, 1001, 0)
    host._on_command(0, 0, 1002, 0)

    assert state.calls == ["connect:device-1", "disconnect:device-1", "refresh"]


def test_on_command_uses_session_state_for_reconnect_and_language():
    state = SessionStateStub()
    host = TrayHost(
        service=ServiceStub(),
        config=AppConfig(),
        logger=logging.getLogger("tray-test"),
        session_state=state,
    )
    host._command_map = {
        1000: type("Entry", (), {"action": "toggle_reconnect", "device_id": None, "language": None})(),
        1001: type("Entry", (), {"action": "set_language", "device_id": None, "language": "zh-CN"})(),
    }

    host._on_command(0, 0, 1000, 0)
    host._on_command(0, 0, 1001, 0)

    assert state.calls == ["reconnect:False", "language:zh-CN"]


def test_left_click_opens_main_window_instead_of_quick_panel():
    called: list[str] = []
    host = TrayHost(
        service=ServiceStub(),
        config=AppConfig(),
        logger=logging.getLogger("tray-test"),
        show_quick_panel=lambda: called.append("quick"),
        show_main_window=lambda: called.append("main"),
    )

    host._on_notify(0, 0, 0, win32con.WM_LBUTTONUP)

    assert called == ["main"]
