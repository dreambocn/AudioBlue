from audio_blue.models import AppConfig, DeviceCapabilities, DeviceRule, DeviceSummary
from audio_blue.rules_engine import RulesEngine


def test_startup_trigger_uses_reconnect_history_with_priority_order():
    config = AppConfig(
        reconnect=True,
        last_devices=["device-3", "device-2", "device-1"],
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


def test_startup_trigger_ignores_legacy_startup_rule_when_reconnect_disabled():
    config = AppConfig(
        reconnect=False,
        last_devices=["device-1"],
        device_rules={
            "device-1": DeviceRule(auto_connect_on_startup=True),
        },
    )
    devices = [DeviceSummary(device_id="device-1", name="Headphones")]

    candidates = RulesEngine(config).get_auto_connect_candidates(
        devices=devices,
        trigger="startup",
    )

    assert candidates == []


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


def test_reappear_trigger_uses_same_priority_order_for_multiple_candidates():
    config = AppConfig(
        device_rules={
            "device-1": DeviceRule(auto_connect_on_reappear=True, priority=2),
            "device-2": DeviceRule(auto_connect_on_reappear=True, is_favorite=True),
            "device-3": DeviceRule(auto_connect_on_reappear=True, priority=1),
        },
    )
    devices = [
        DeviceSummary(device_id="device-1", name="Headphones"),
        DeviceSummary(device_id="device-2", name="Speaker"),
        DeviceSummary(device_id="device-3", name="Receiver"),
    ]

    candidates = RulesEngine(config).get_auto_connect_candidates(
        devices=devices,
        trigger="reappear",
    )

    assert [device.device_id for device in candidates] == ["device-2", "device-3", "device-1"]


def test_startup_trigger_filters_missing_non_audio_and_ignored_history_entries():
    config = AppConfig(
        reconnect=True,
        last_devices=["device-4", "device-3", "device-2", "device-1"],
        device_rules={
            "device-3": DeviceRule(is_ignored=True),
        },
    )
    devices = [
        DeviceSummary(device_id="device-1", name="Headphones"),
        DeviceSummary(
            device_id="device-2",
            name="Speaker",
            capabilities=DeviceCapabilities(supports_audio_playback=False),
        ),
        DeviceSummary(device_id="device-3", name="Receiver"),
    ]

    candidates = RulesEngine(config).get_auto_connect_candidates(
        devices=devices,
        trigger="startup",
    )

    assert [device.device_id for device in candidates] == ["device-1"]
