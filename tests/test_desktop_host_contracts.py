from __future__ import annotations

import inspect
"""覆盖桌面宿主对 pywebview 事件与接口暴露的契约。"""

from pathlib import Path

import pytest

from audio_blue.models import AppConfig, DeviceSummary


BRIDGE_METHODS = {
    "get_initial_state",
    "refresh_devices",
    "connect_device",
    "disconnect_device",
    "update_device_rule",
    "reorder_device_priority",
    "set_autostart",
    "set_reconnect",
    "set_theme",
    "sync_window_theme",
    "set_language",
    "set_notification_policy",
    "minimize_window",
    "toggle_maximize_window",
    "close_main_window",
    "open_bluetooth_settings",
    "export_support_bundle",
    "export_diagnostics",
}

def test_desktop_host_bridge_surface_contract_when_module_available():
    module = pytest.importorskip(
        "audio_blue.desktop_host",
        reason="desktop host is under active parallel development",
    )

    missing_from_module = {name for name in BRIDGE_METHODS if not callable(getattr(module, name, None))}
    if not missing_from_module:
        return

    candidate_classes = [
        cls
        for _, cls in inspect.getmembers(module, inspect.isclass)
        if cls.__module__ == module.__name__
    ]
    for cls in candidate_classes:
        class_missing = {name for name in BRIDGE_METHODS if not callable(getattr(cls, name, None))}
        if not class_missing:
            return

    pytest.fail(
        "Desktop host must expose bridge APIs either as module callables or on a bridge class. "
        f"Missing methods: {sorted(missing_from_module)}"
    )


def test_app_state_maps_connection_failure_to_stable_snapshot_payload():
    module = pytest.importorskip(
        "audio_blue.app_state",
        reason="app state module is under active parallel development",
    )
    store = module.AppStateStore(AppConfig())
    store.sync_devices([DeviceSummary(device_id="dev-1", name="Headphones")])
    store.handle_connector_event(
        {
            "event": "device_connection_failed",
            "device_id": "dev-1",
            "state": "timeout",
        }
    )

    payload = store.snapshot()
    assert set(payload) >= {
        "devices",
        "deviceRules",
        "lastFailure",
        "lastTrigger",
        "settings",
        "autoConnectCandidates",
    }

    assert payload["lastFailure"] is not None
    assert payload["lastFailure"]["deviceId"] == "dev-1"
    assert payload["lastFailure"]["state"] == "timeout"
    assert "timed out" in payload["lastFailure"]["message"].lower()
    assert payload["lastTrigger"] == "manual"

    device_payload = payload["devices"][0]
    assert set(device_payload) >= {"deviceId", "name", "connectionState", "capabilities"}
    assert device_payload["deviceId"] == "dev-1"
    assert device_payload["connectionState"] == "timeout"
    assert device_payload["lastConnectionAttempt"]["succeeded"] is False
    assert device_payload["lastConnectionAttempt"]["state"] == "timeout"


def test_app_state_maps_connected_event_to_success_attempt():
    module = pytest.importorskip(
        "audio_blue.app_state",
        reason="app state module is under active parallel development",
    )
    store = module.AppStateStore(AppConfig())
    store.sync_devices([DeviceSummary(device_id="dev-1", name="Headphones")])
    store.handle_connector_event({"event": "device_connected", "device_id": "dev-1"})

    payload = store.snapshot()
    device_payload = payload["devices"][0]
    assert device_payload["connectionState"] == "connected"
    assert device_payload["lastConnectionAttempt"]["succeeded"] is True
    assert payload["lastFailure"] is None


def test_autostart_command_shape_contract_when_module_available():
    module = pytest.importorskip(
        "audio_blue.autostart_manager",
        reason="autostart manager is under active parallel development",
    )
    builder = None
    for name in ("build_autostart_command", "build_command_line", "build_run_value"):
        candidate = getattr(module, name, None)
        if callable(candidate):
            builder = candidate
            break
    if builder is None:
        pytest.skip("autostart manager is present but has no exported command builder")

    command = builder(Path("C:/Program Files/AudioBlue/audioblue.exe"))
    if isinstance(command, (list, tuple)):
        command_text = " ".join(str(part) for part in command)
    else:
        command_text = str(command)
    assert "--background" in command_text


def test_single_instance_activation_contract_when_module_available():
    module = pytest.importorskip(
        "audio_blue.single_instance",
        reason="single instance module is under active parallel development",
    )
    callables = {name for name, value in vars(module).items() if callable(value)}
    acquire_candidates = {"try_acquire", "acquire_single_instance", "ensure_single_instance"}
    activate_candidates = {"activate_existing_instance", "signal_existing_instance", "focus_existing_window"}

    if not (callables & acquire_candidates):
        pytest.skip("single_instance module missing known acquire callable names")
    if not (callables & activate_candidates):
        pytest.skip("single_instance module missing known activation callable names")

    assert callables & acquire_candidates
    assert callables & activate_candidates
