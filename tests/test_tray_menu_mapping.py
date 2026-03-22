from audio_blue.models import DeviceSummary
from audio_blue.tray_host import build_menu_entries


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
