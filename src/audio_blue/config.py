from __future__ import annotations

import os
from pathlib import Path

from audio_blue.models import AppConfig
from audio_blue.storage import SQLiteStorage, get_default_db_path


def get_config_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "AudioBlue" / "config.json"
    return Path.home() / "AppData" / "Local" / "AudioBlue" / "config.json"


def get_storage_path() -> Path:
    return get_default_db_path()


def load_config(path: Path | None = None) -> AppConfig:
    storage = _build_storage(path)
    storage.initialize()
    storage.migrate_legacy_files()
    return storage.load_config()


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    storage = _build_storage(path)
    storage.initialize()
    storage.migrate_legacy_files()
    storage.save_config(config)
    return storage.db_path


def _build_storage(path: Path | None) -> SQLiteStorage:
    if path is None:
        return SQLiteStorage(db_path=get_storage_path())

    resolved = Path(path)
    suffix = resolved.suffix.lower()
    if suffix == ".json":
        return SQLiteStorage(
            db_path=resolved.with_name("audioblue.db"),
            legacy_config_path=resolved,
            legacy_log_path=resolved.with_name("audioblue.log"),
            legacy_diagnostics_dir=resolved.with_name("diagnostics"),
        )
    if suffix == ".log":
        return SQLiteStorage(
            db_path=resolved.with_name("audioblue.db"),
            legacy_log_path=resolved,
            legacy_config_path=resolved.with_name("config.json"),
            legacy_diagnostics_dir=resolved.with_name("diagnostics"),
        )
    return SQLiteStorage(db_path=resolved)
