from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from audio_blue.models import AppConfig, ConnectionAttempt, DeviceRule, DeviceSummary
from audio_blue.storage import SQLiteStorage


def build_diagnostics_snapshot(
    config: AppConfig,
    devices: Sequence[DeviceSummary],
    attempts: Sequence[ConnectionAttempt],
    source: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or datetime.now(UTC)
    return {
        "source": source,
        "generatedAt": timestamp.isoformat(),
        "config": _serialize_config(config),
        "devices": [_serialize_device(device) for device in devices],
        "attempts": [_serialize_attempt(attempt) for attempt in attempts],
    }


def export_diagnostics_snapshot(snapshot: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    storage = _build_storage_for_export(path)
    storage.initialize()
    snapshot_id = storage.save_diagnostics_snapshot(snapshot)
    storage.record_diagnostics_export(export_path=path, snapshot_id=snapshot_id)
    storage.purge_expired_records()
    return path


def _serialize_config(config: AppConfig) -> dict[str, Any]:
    return {
        "reconnect": config.reconnect,
        "lastDevices": list(config.last_devices),
        "deviceRules": {
            device_id: _serialize_device_rule(rule)
            for device_id, rule in config.device_rules.items()
        },
        "notification": {"policy": config.notification.policy},
        "startup": {
            "autostart": config.startup.autostart,
            "runInBackground": config.startup.run_in_background,
            "launchDelaySeconds": config.startup.launch_delay_seconds,
        },
        "ui": {
            "theme": config.ui.theme,
            "highContrast": config.ui.high_contrast,
            "language": config.ui.language,
        },
    }


def _serialize_device_rule(rule: DeviceRule) -> dict[str, Any]:
    return {
        "isFavorite": rule.is_favorite,
        "isIgnored": rule.is_ignored,
        "priority": rule.priority,
        "autoConnectOnStartup": rule.auto_connect_on_startup,
        "autoConnectOnReappear": rule.auto_connect_on_reappear,
    }


def _serialize_device(device: DeviceSummary) -> dict[str, Any]:
    return {
        "deviceId": device.device_id,
        "name": device.name,
        "connectionState": device.connection_state,
        "capabilities": {
            "supportsAudioPlayback": device.capabilities.supports_audio_playback,
            "supportsMicrophone": device.capabilities.supports_microphone,
        },
        "lastSeenAt": _to_iso(device.last_seen_at),
        "lastConnectionAttempt": (
            _serialize_attempt(device.last_connection_attempt)
            if device.last_connection_attempt is not None
            else None
        ),
    }


def _serialize_attempt(attempt: ConnectionAttempt) -> dict[str, Any]:
    return {
        "trigger": attempt.trigger,
        "succeeded": attempt.succeeded,
        "state": attempt.state,
        "failureReason": attempt.failure_reason,
        "failureCode": attempt.failure_code,
        "happenedAt": _to_iso(attempt.happened_at),
    }


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _build_storage_for_export(export_path: Path) -> SQLiteStorage:
    if export_path.parent.name.lower() == "diagnostics":
        return SQLiteStorage(db_path=export_path.parent.parent / "audioblue.db")
    return SQLiteStorage(db_path=export_path.parent / "audioblue.db")
