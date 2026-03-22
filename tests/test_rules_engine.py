from audio_blue.models import AppConfig, DeviceCapabilities, DeviceRule, DeviceSummary
from audio_blue.rules_engine import RulesEngine


def test_startup_trigger_returns_matching_device_ids_in_priority_order():
    config = AppConfig(
        device_rules={
            "device-1": DeviceRule(
                is_favorite=True,
                priority=2,
                auto_connect_on_startup=True,
            ),
            "device-2": DeviceRule(
                priority=1,
                auto_connect_on_startup=True,
            ),
        }
    )
    devices = [
        DeviceSummary(device_id="device-1", name="Headphones"),
        DeviceSummary(device_id="device-2", name="Speaker"),
    ]

    candidates = RulesEngine(config).get_auto_connect_candidates(
        devices=devices,
        trigger="startup",
    )

    assert [device.device_id for device in candidates] == ["device-1", "device-2"]


def test_reappear_trigger_skips_ignored_and_non_audio_devices():
    config = AppConfig(
        device_rules={
            "device-1": DeviceRule(auto_connect_on_reappear=True, is_ignored=True),
            "device-2": DeviceRule(auto_connect_on_reappear=True),
        }
    )
    devices = [
        DeviceSummary(device_id="device-1", name="Keyboard"),
        DeviceSummary(
            device_id="device-2",
            name="Earbuds",
            capabilities=DeviceCapabilities(supports_audio_playback=True),
        ),
        DeviceSummary(
            device_id="device-3",
            name="Mouse",
            capabilities=DeviceCapabilities(supports_audio_playback=False),
        ),
    ]

    candidates = RulesEngine(config).get_auto_connect_candidates(
        devices=devices,
        trigger="reappear",
    )

    assert [device.device_id for device in candidates] == ["device-2"]


def test_reconnect_history_falls_back_after_rule_based_candidates():
    config = AppConfig(
        reconnect=True,
        last_devices=["device-3", "device-2"],
        device_rules={
            "device-1": DeviceRule(
                is_favorite=True,
                priority=1,
                auto_connect_on_startup=True,
            )
        },
    )
    devices = [
        DeviceSummary(device_id="device-1", name="Headphones"),
        DeviceSummary(device_id="device-2", name="Speaker"),
        DeviceSummary(device_id="device-3", name="Receiver"),
    ]

    candidates = RulesEngine(config).get_auto_connect_candidates(
        devices=devices,
        trigger="startup",
    )

    assert [device.device_id for device in candidates] == ["device-1", "device-3", "device-2"]
