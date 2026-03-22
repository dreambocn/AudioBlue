from datetime import UTC, datetime

from audio_blue.app_state import AppStateStore, humanize_connection_failure
from audio_blue.models import AppConfig, DeviceRule, DeviceSummary, UiPreferences


def test_humanize_connection_failure_returns_user_friendly_copy():
    assert humanize_connection_failure("timeout") == "Connection timed out before audio could start."
    assert humanize_connection_failure("denied") == "Windows denied the audio connection request."
    assert humanize_connection_failure("error") == "AudioBlue could not connect to the device."


def test_app_state_tracks_failures_and_rule_updates():
    store = AppStateStore(config=AppConfig(ui=UiPreferences(language="zh-CN")))
    store.sync_devices(
        [
            DeviceSummary(
                device_id="device-1",
                name="Headphones",
                last_seen_at=datetime(2026, 3, 23, 9, 30, tzinfo=UTC),
            )
        ]
    )

    store.handle_connector_event(
        {"event": "device_connection_failed", "device_id": "device-1", "state": "timeout"}
    )
    store.update_device_rule(
        "device-1",
        {
            "is_favorite": True,
            "auto_connect_on_reappear": True,
        },
    )

    snapshot = store.snapshot()

    assert snapshot["lastFailure"]["deviceId"] == "device-1"
    assert snapshot["lastFailure"]["state"] == "timeout"
    assert snapshot["lastFailure"]["code"] == "connection.timeout"
    assert "message" not in snapshot["lastFailure"]
    assert snapshot["settings"]["ui"]["language"] == "zh-CN"
    assert snapshot["devices"][0]["lastSeenAt"] == "2026-03-23T09:30:00+00:00"
    assert snapshot["deviceRules"]["device-1"] == {
        "isFavorite": True,
        "isIgnored": False,
        "priority": None,
        "autoConnectOnStartup": False,
        "autoConnectOnReappear": True,
    }


def test_app_state_reorders_priorities_without_dropping_existing_flags():
    store = AppStateStore(
        config=AppConfig(
            device_rules={
                "device-1": DeviceRule(is_favorite=True, auto_connect_on_startup=True),
                "device-2": DeviceRule(auto_connect_on_startup=True),
            }
        )
    )

    store.reorder_device_priority(["device-2", "device-1"])

    assert store.config.device_rules["device-2"].priority == 1
    assert store.config.device_rules["device-1"].priority == 2
    assert store.config.device_rules["device-1"].is_favorite is True
    assert store.config.device_rules["device-1"].auto_connect_on_startup is True


def test_app_state_connection_attempt_uses_failure_code_as_stable_contract():
    store = AppStateStore(config=AppConfig())
    store.sync_devices([DeviceSummary(device_id="device-1", name="Headphones")])

    store.handle_connector_event(
        {"event": "device_connection_failed", "device_id": "device-1", "state": "denied"}
    )
    snapshot = store.snapshot()

    attempt = snapshot["devices"][0]["lastConnectionAttempt"]
    assert attempt["state"] == "denied"
    assert attempt["failureCode"] == "connection.denied"
