"""覆盖扩展模型字段与触发规则的默认行为。"""

from audio_blue.models import (
    AppConfig,
    DeviceCapabilities,
    DeviceRule,
    NotificationPreferences,
    StartupPreferences,
    UiPreferences,
)


def test_device_rule_trigger_flags_cover_startup_and_reappear():
    manual_rule = DeviceRule()
    startup_rule = DeviceRule(auto_connect_on_startup=True)
    reappear_rule = DeviceRule(auto_connect_on_reappear=True)

    assert manual_rule.matches_trigger("startup") is False
    assert startup_rule.matches_trigger("startup") is True
    assert startup_rule.matches_trigger("reappear") is False
    assert reappear_rule.matches_trigger("startup") is False
    assert reappear_rule.matches_trigger("reappear") is True


def test_app_config_defaults_include_extended_preferences():
    config = AppConfig()

    assert config.reconnect is False
    assert config.notification == NotificationPreferences()
    assert config.startup == StartupPreferences()
    assert config.ui == UiPreferences()
    assert config.device_rules == {}


def test_ui_preferences_default_language_is_system():
    preferences = UiPreferences()

    assert preferences.language == "system"


def test_device_capabilities_defaults_to_audio_playback_support():
    capabilities = DeviceCapabilities()

    assert capabilities.supports_audio_playback is True
    assert capabilities.supports_microphone is False
