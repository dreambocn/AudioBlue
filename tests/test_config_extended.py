"""覆盖扩展配置字段在加载与保存时的兼容性。"""

import json

from audio_blue.config import load_config, save_config
from audio_blue.models import (
    AppConfig,
    DeviceRule,
    NotificationPreferences,
    StartupPreferences,
    UiPreferences,
)


def test_load_config_parses_extended_nested_payload(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "reconnect": True,
                "lastDevices": ["device-1"],
                "deviceRules": {
                    "device-1": {
                        "isFavorite": True,
                        "priority": 1,
                        "autoConnectOnStartup": True,
                    }
                },
                "notification": {"policy": "all"},
                "startup": {"autostart": True, "launchDelaySeconds": 5},
                "ui": {"theme": "dark", "language": "zh-CN"},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.reconnect is True
    assert config.last_devices == ["device-1"]
    assert config.device_rules["device-1"] == DeviceRule(
        is_favorite=True,
        priority=1,
        auto_connect_on_startup=True,
    )
    assert config.notification == NotificationPreferences(policy="all")
    assert config.startup == StartupPreferences(autostart=True, launch_delay_seconds=5)
    assert config.ui == UiPreferences(theme="dark", language="zh-CN")
    assert config_path.with_name("audioblue.db").exists()


def test_save_config_writes_extended_fields_when_non_default(tmp_path):
    config_path = tmp_path / "audioblue.db"
    config = AppConfig(
        reconnect=True,
        last_devices=["device-1"],
        device_rules={
            "device-1": DeviceRule(
                is_favorite=True,
                priority=3,
                auto_connect_on_reappear=True,
            )
        },
        notification=NotificationPreferences(policy="all"),
        startup=StartupPreferences(autostart=True, run_in_background=True),
        ui=UiPreferences(theme="light", high_contrast=True, language="en-US"),
    )

    save_config(config, config_path)
    loaded = load_config(config_path)

    assert loaded.device_rules["device-1"].is_favorite is True
    assert loaded.device_rules["device-1"].priority == 3
    assert loaded.notification.policy == "all"
    assert loaded.startup.autostart is True
    assert loaded.startup.run_in_background is True
    assert loaded.ui.theme == "light"
    assert loaded.ui.high_contrast is True
    assert loaded.ui.language == "en-US"


def test_load_config_defaults_language_to_system_when_missing(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "ui": {"theme": "dark"},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.ui.language == "system"
