import logging

import pywintypes

from audio_blue.models import AppConfig
from audio_blue.models import DeviceSummary
from audio_blue.tray_host import TrayHost, build_menu_entries


def test_build_menu_entries_includes_static_actions_and_toggle():
    entries = build_menu_entries([], reconnect_enabled=True)
    labels = [entry.label for entry in entries]

    assert labels[:2] == ["Refresh Devices", "Reconnect On Next Start"]
    assert "Open Control Center" in labels
    assert "Bluetooth Settings" in labels
    assert labels[-1] == "Exit"
    toggle = next(entry for entry in entries if entry.action == "toggle_reconnect")
    assert toggle.checked is True


def test_build_menu_entries_adds_one_entry_per_device_with_stateful_labels():
    devices = [
        DeviceSummary(device_id="device-1", name="Headphones", connection_state="connected"),
        DeviceSummary(device_id="device-2", name="Speaker", connection_state="disconnected"),
    ]

    entries = build_menu_entries(devices, reconnect_enabled=False)
    device_entries = [entry for entry in entries if entry.action in {"connect_device", "disconnect_device"}]

    assert [entry.label for entry in device_entries] == [
        "Disconnect Headphones",
        "Connect Speaker",
    ]
    assert [entry.device_id for entry in device_entries] == ["device-1", "device-2"]


class ServiceStub:
    def __init__(self):
        self.known_devices = {}


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
