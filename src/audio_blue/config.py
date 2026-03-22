from __future__ import annotations

import json
import os
from pathlib import Path

from audio_blue.models import AppConfig


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
    )


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    config_path = path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "reconnect": config.reconnect,
                "lastDevices": config.last_devices,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return config_path
