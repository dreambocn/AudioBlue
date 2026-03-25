"""负责生成诊断快照并导出支持包。"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
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
    """把当前运行配置、设备与连接尝试整理成可持久化的快照。"""
    timestamp = generated_at or datetime.now(UTC)
    return {
        "source": source,
        "generatedAt": timestamp.isoformat(),
        "config": _serialize_config(config),
        "devices": [_serialize_device(device) for device in devices],
        "attempts": [_serialize_attempt(attempt) for attempt in attempts],
    }


def export_diagnostics_snapshot(snapshot: dict[str, Any], path: Path) -> Path:
    """导出单份 JSON 诊断快照，并同步记录到本地存储。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    storage = _build_storage_for_export(path)
    storage.initialize()
    snapshot_id = storage.save_diagnostics_snapshot(snapshot)
    storage.record_diagnostics_export(export_path=path, snapshot_id=snapshot_id)
    storage.purge_expired_records()
    return path


def export_support_bundle(
    *,
    snapshot: dict[str, Any],
    path: Path,
    storage: SQLiteStorage,
) -> Path:
    """导出支持包压缩文件，汇总最近运行时状态与历史记录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_state = storage.build_runtime_diagnostics()
    connection_overview = snapshot.get("connectionOverview")
    if not isinstance(connection_overview, dict):
        connection_overview = snapshot.get("connection")
    state_diagnostics = snapshot.get("diagnostics")
    payloads = {
        "summary.json": {
            "source": snapshot.get("source", "unknown"),
            "generatedAt": snapshot.get("generatedAt"),
            "version": _read_project_version(),
            "status": connection_overview.get("status")
            if isinstance(connection_overview, dict)
            else None,
            "currentPhase": connection_overview.get("currentPhase")
            if isinstance(connection_overview, dict)
            else None,
            "lastErrorCode": connection_overview.get("lastErrorCode")
            if isinstance(connection_overview, dict)
            else None,
        },
        "activity-events.json": storage.list_activity_events(limit=200),
        "connection-history.json": storage.list_connection_attempts(limit=200),
        "device-history.json": storage.list_device_history(limit=200),
        "diagnostics.json": {
            **snapshot,
            "diagnostics": (
                {**diagnostics_state, **state_diagnostics}
                if isinstance(state_diagnostics, dict)
                else diagnostics_state
            ),
        },
        "config.json": snapshot.get("config", {}),
    }
    # 支持包里的各份 JSON 面向不同排障入口，保持职责拆分更易定位问题。
    with ZipFile(path, mode="w", compression=ZIP_DEFLATED) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, json.dumps(payload, indent=2, ensure_ascii=False))

    storage.record_diagnostics_export(export_path=path, snapshot_id=None)
    storage.purge_expired_records()
    return path


def _serialize_config(config: AppConfig) -> dict[str, Any]:
    """把配置对象转换为前后端都易读的字典结构。"""
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
    """序列化设备快照，同时保留能力信息与最近连接结果。"""
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
    """根据导出目录推断应写入哪份 SQLite 数据库。"""
    if export_path.parent.name.lower() == "diagnostics":
        return SQLiteStorage(db_path=export_path.parent.parent / "audioblue.db")
    return SQLiteStorage(db_path=export_path.parent / "audioblue.db")


def _read_project_version() -> str | None:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"(?P<version>[^"]+)"', content)
    if not match:
        return None
    return match.group("version")
