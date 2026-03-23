from pathlib import Path

from audio_blue.config import get_config_path, load_config, save_config
from audio_blue.models import AppConfig, DeviceRule, NotificationPreferences, StartupPreferences, UiPreferences
from audio_blue.tray_host import build_exit_config


def test_get_config_path_uses_local_app_data(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Test\AppData\Local")

    config_path = get_config_path()

    assert config_path == Path(r"C:\Users\Test\AppData\Local\AudioBlue\config.json")


def test_load_config_returns_defaults_when_file_missing(tmp_path):
    config = load_config(tmp_path / "missing.db")

    assert config == AppConfig()


def test_load_config_returns_defaults_when_legacy_json_is_invalid(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{not-json", encoding="utf-8")

    config = load_config(config_path)

    assert config == AppConfig()
    assert config_path.with_name("audioblue.db").exists()


def test_save_config_persists_reconnect_and_last_devices(tmp_path):
    config_path = tmp_path / "nested" / "audioblue.db"
    config = AppConfig(reconnect=True, last_devices=["device-1", "device-2"])

    saved_path = save_config(config, config_path)
    loaded = load_config(config_path)

    assert saved_path == config_path
    assert loaded == config


def test_load_config_round_trips_saved_values(tmp_path):
    config_path = tmp_path / "audioblue.db"
    save_config(AppConfig(reconnect=True, last_devices=["device-1"]), config_path)

    config = load_config(config_path)

    assert config == AppConfig(reconnect=True, last_devices=["device-1"])


def test_build_exit_config_persists_active_connection_ids():
    class ServiceStub:
        active_connections = {"device-1": object(), "device-2": object()}

    exit_config = build_exit_config(AppConfig(reconnect=True), ServiceStub())

    assert exit_config == AppConfig(reconnect=True, last_devices=["device-1", "device-2"])


def test_build_exit_config_preserves_extended_preferences():
    class ServiceStub:
        active_connections = {"device-1": object()}

    config = AppConfig(
        reconnect=True,
        device_rules={"device-1": DeviceRule(is_favorite=True, auto_connect_on_startup=True)},
        notification=NotificationPreferences(policy="all"),
        startup=StartupPreferences(autostart=True, run_in_background=True),
        ui=UiPreferences(theme="dark", high_contrast=True),
    )

    exit_config = build_exit_config(config, ServiceStub())

    assert exit_config.device_rules == config.device_rules
    assert exit_config.notification == config.notification
    assert exit_config.startup == config.startup
    assert exit_config.ui == config.ui
