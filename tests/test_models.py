"""验证核心数据模型的默认值保持稳定。"""

from audio_blue.models import AppConfig, DeviceSummary


def test_device_summary_defaults_to_disconnected_state():
    device = DeviceSummary(device_id="device-1", name="Headphones")

    assert device.device_id == "device-1"
    assert device.name == "Headphones"
    assert device.connection_state == "disconnected"


def test_app_config_defaults_match_reference_behavior():
    config = AppConfig()

    assert config.reconnect is False
    assert config.last_devices == []
