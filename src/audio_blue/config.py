from __future__ import annotations

import json
import os
from pathlib import Path

from audio_blue.models import (
    AppConfig,
    DeviceRule,
    NotificationPreferences,
    StartupPreferences,
    UiPreferences,
)


def get_config_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "AudioBlue" / "config.json"

    return Path.home() / "AppData" / "Local" / "AudioBlue" / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or get_config_path()

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return AppConfig()

    reconnect = bool(payload.get("reconnect", False))
    last_devices = payload.get("lastDevices", [])
    if not isinstance(last_devices, list):
        last_devices = []

    return AppConfig(
        reconnect=reconnect,
        last_devices=[item for item in last_devices if isinstance(item, str)],
        device_rules=_load_device_rules(payload.get("deviceRules")),
        notification=_load_notification_preferences(payload.get("notification")),
        startup=_load_startup_preferences(payload.get("startup")),
        ui=_load_ui_preferences(payload.get("ui")),
    )


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    config_path = path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, object] = {
        "reconnect": config.reconnect,
        "lastDevices": config.last_devices,
    }
    if config.device_rules:
        payload["deviceRules"] = {
            device_id: _serialize_device_rule(rule)
            for device_id, rule in config.device_rules.items()
        }
    if config.notification != NotificationPreferences():
        payload["notification"] = _serialize_notification_preferences(config.notification)
    if config.startup != StartupPreferences():
        payload["startup"] = _serialize_startup_preferences(config.startup)
    if config.ui != UiPreferences():
        payload["ui"] = _serialize_ui_preferences(config.ui)

    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return config_path


def _load_device_rules(payload: object) -> dict[str, DeviceRule]:
    if not isinstance(payload, dict):
        return {}

    rules: dict[str, DeviceRule] = {}
    for device_id, raw_rule in payload.items():
        if isinstance(device_id, str) and isinstance(raw_rule, dict):
            rules[device_id] = DeviceRule(
                is_favorite=bool(raw_rule.get("isFavorite", False)),
                is_ignored=bool(raw_rule.get("isIgnored", False)),
                priority=raw_rule.get("priority")
                if isinstance(raw_rule.get("priority"), int)
                else None,
                auto_connect_on_startup=bool(
                    raw_rule.get("autoConnectOnStartup", False)
                ),
                auto_connect_on_reappear=bool(
                    raw_rule.get("autoConnectOnReappear", False)
                ),
            )
    return rules


def _load_notification_preferences(payload: object) -> NotificationPreferences:
    if not isinstance(payload, dict):
        return NotificationPreferences()

    policy = payload.get("policy")
    if policy not in {"silent", "failures", "all"}:
        return NotificationPreferences()
    return NotificationPreferences(policy=policy)


def _load_startup_preferences(payload: object) -> StartupPreferences:
    if not isinstance(payload, dict):
        return StartupPreferences()

    delay = payload.get("launchDelaySeconds", StartupPreferences().launch_delay_seconds)
    return StartupPreferences(
        autostart=bool(payload.get("autostart", False)),
        run_in_background=bool(payload.get("runInBackground", False)),
        launch_delay_seconds=delay if isinstance(delay, int) and delay >= 0 else 3,
    )


def _load_ui_preferences(payload: object) -> UiPreferences:
    if not isinstance(payload, dict):
        return UiPreferences()

    theme = payload.get("theme")
    if theme not in {"system", "light", "dark"}:
        theme = "system"

    return UiPreferences(
        theme=theme,
        high_contrast=bool(payload.get("highContrast", False)),
    )


def _serialize_device_rule(rule: DeviceRule) -> dict[str, object]:
    payload: dict[str, object] = {}
    if rule.is_favorite:
        payload["isFavorite"] = True
    if rule.is_ignored:
        payload["isIgnored"] = True
    if rule.priority is not None:
        payload["priority"] = rule.priority
    if rule.auto_connect_on_startup:
        payload["autoConnectOnStartup"] = True
    if rule.auto_connect_on_reappear:
        payload["autoConnectOnReappear"] = True
    return payload


def _serialize_notification_preferences(
    preferences: NotificationPreferences,
) -> dict[str, object]:
    return {"policy": preferences.policy}


def _serialize_startup_preferences(
    preferences: StartupPreferences,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    if preferences.autostart:
        payload["autostart"] = True
    if preferences.run_in_background:
        payload["runInBackground"] = True
    if preferences.launch_delay_seconds != StartupPreferences().launch_delay_seconds:
        payload["launchDelaySeconds"] = preferences.launch_delay_seconds
    return payload


def _serialize_ui_preferences(preferences: UiPreferences) -> dict[str, object]:
    payload: dict[str, object] = {}
    if preferences.theme != UiPreferences().theme:
        payload["theme"] = preferences.theme
    if preferences.high_contrast:
        payload["highContrast"] = True
    return payload
