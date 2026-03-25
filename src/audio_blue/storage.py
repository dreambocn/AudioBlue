from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from audio_blue.models import (
    AppConfig,
    DeviceRule,
    NotificationPreferences,
    StartupPreferences,
    UiPreferences,
)

_LEGACY_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (?P<level>[A-Z]+) (?P<message>.*)$"
)
_THEME_VALUES = {"system", "light", "dark"}
_LANGUAGE_VALUES = {"system", "zh-CN", "en-US"}
_POLICY_VALUES = {"silent", "failures", "all"}


def get_default_db_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "AudioBlue" / "audioblue.db"
    return Path.home() / "AppData" / "Local" / "AudioBlue" / "audioblue.db"


def get_storage(*, db_path: Path | None = None) -> "SQLiteStorage":
    return SQLiteStorage(db_path=db_path)


def get_default_storage() -> "SQLiteStorage":
    return get_storage()


default_storage = get_default_storage
storage = get_storage


class SQLiteStorage:
    def __init__(
        self,
        *,
        db_path: Path | None = None,
        legacy_config_path: Path | None = None,
        legacy_log_path: Path | None = None,
        legacy_diagnostics_dir: Path | None = None,
    ) -> None:
        self.db_path = (db_path or get_default_db_path()).resolve()
        root_dir = self.db_path.parent
        self.legacy_config_path = legacy_config_path or (root_dir / "config.json")
        self.legacy_log_path = legacy_log_path or (root_dir / "audioblue.log")
        self.legacy_diagnostics_dir = legacy_diagnostics_dir or (root_dir / "diagnostics")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS device_rules (
                    device_id TEXT PRIMARY KEY,
                    is_favorite INTEGER NOT NULL DEFAULT 0,
                    is_ignored INTEGER NOT NULL DEFAULT 0,
                    priority INTEGER,
                    auto_connect_on_startup INTEGER NOT NULL DEFAULT 0,
                    auto_connect_on_reappear INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS last_devices (
                    position INTEGER PRIMARY KEY,
                    device_id TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS device_cache (
                    device_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    connection_state TEXT NOT NULL,
                    supports_audio_playback INTEGER NOT NULL DEFAULT 1,
                    supports_microphone INTEGER NOT NULL DEFAULT 0,
                    last_seen_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS connection_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    succeeded INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    failure_reason TEXT,
                    failure_code TEXT,
                    happened_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagnostics_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagnostics_exports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER,
                    export_path TEXT NOT NULL,
                    exported_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(snapshot_id) REFERENCES diagnostics_snapshots(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS log_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    logger_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    extra_json TEXT
                );
                """
            )
            now = _utc_now().isoformat()
            connection.execute(
                """
                INSERT INTO metadata(key, value, updated_at)
                VALUES ('schema_version', '1', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (now,),
            )

    def migrate_legacy_files(self) -> None:
        self.initialize()
        with self._connect() as connection:
            migrated = connection.execute(
                "SELECT value FROM metadata WHERE key = 'legacy_migrated_v1'"
            ).fetchone()
            if migrated is not None and migrated["value"] == "1":
                return

            self._migrate_legacy_config(connection)
            self._migrate_legacy_log(connection)
            self._migrate_legacy_diagnostics(connection)

            now = _utc_now().isoformat()
            connection.execute(
                """
                INSERT INTO metadata(key, value, updated_at)
                VALUES ('legacy_migrated_v1', '1', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (now,),
            )

    def load_config(self) -> AppConfig:
        with self._connect() as connection:
            return self._load_config(connection)

    def save_config(self, config: AppConfig) -> None:
        with self._connect() as connection:
            self._save_config(connection, config)

    def record_connection_attempt(
        self,
        *,
        device_id: str,
        trigger: str,
        succeeded: bool,
        state: str,
        failure_reason: str | None = None,
        failure_code: str | None = None,
        happened_at: datetime | None = None,
    ) -> int:
        timestamp = (happened_at or _utc_now()).astimezone(UTC).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO connection_history(
                    device_id, trigger, succeeded, state, failure_reason, failure_code, happened_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    trigger,
                    int(succeeded),
                    state,
                    failure_reason,
                    failure_code,
                    timestamp,
                    _utc_now().isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def upsert_device_cache(
        self,
        *,
        device_id: str,
        name: str,
        connection_state: str,
        supports_audio_playback: bool,
        supports_microphone: bool,
        last_seen_at: datetime | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO device_cache(
                    device_id,
                    name,
                    connection_state,
                    supports_audio_playback,
                    supports_microphone,
                    last_seen_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name = excluded.name,
                    connection_state = excluded.connection_state,
                    supports_audio_playback = excluded.supports_audio_playback,
                    supports_microphone = excluded.supports_microphone,
                    last_seen_at = excluded.last_seen_at,
                    updated_at = excluded.updated_at
                """,
                (
                    device_id,
                    name,
                    connection_state,
                    int(supports_audio_playback),
                    int(supports_microphone),
                    _to_iso(last_seen_at),
                    _utc_now().isoformat(),
                ),
            )

    def save_diagnostics_snapshot(self, snapshot: dict[str, Any]) -> int:
        generated_at = _parse_iso_datetime(snapshot.get("generatedAt")) or _utc_now()
        source = str(snapshot.get("source", "unknown"))
        payload_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO diagnostics_snapshots(source, generated_at, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (source, generated_at.isoformat(), payload_json, _utc_now().isoformat()),
            )
            return int(cursor.lastrowid)

    def record_diagnostics_export(
        self,
        *,
        export_path: Path | str,
        snapshot_id: int | None = None,
        exported_at: datetime | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO diagnostics_exports(snapshot_id, export_path, exported_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    str(export_path),
                    (exported_at or _utc_now()).astimezone(UTC).isoformat(),
                    _utc_now().isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def record_log(
        self,
        *,
        level: str,
        message: str,
        logger_name: str,
        created_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO log_records(level, message, logger_name, created_at, extra_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    level,
                    message,
                    logger_name,
                    (created_at or _utc_now()).astimezone(UTC).isoformat(),
                    json.dumps(extra, ensure_ascii=False, sort_keys=True) if extra else None,
                ),
            )
            return int(cursor.lastrowid)

    def purge_expired_records(
        self,
        *,
        now: datetime | None = None,
        retention_days: int = 90,
    ) -> None:
        cutoff = (now or _utc_now()).astimezone(UTC) - timedelta(days=retention_days)
        cutoff_iso = cutoff.isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM log_records WHERE created_at < ?", (cutoff_iso,))
            connection.execute("DELETE FROM connection_history WHERE happened_at < ?", (cutoff_iso,))
            connection.execute("DELETE FROM diagnostics_exports WHERE exported_at < ?", (cutoff_iso,))
            connection.execute(
                "DELETE FROM diagnostics_snapshots WHERE generated_at < ?",
                (cutoff_iso,),
            )

    def list_device_history(self, *, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cache_rows = connection.execute(
                """
                SELECT
                    device_id,
                    name,
                    supports_audio_playback,
                    supports_microphone,
                    last_seen_at
                FROM device_cache
                """
            ).fetchall()
            connection_rows = connection.execute(
                """
                SELECT
                    id,
                    device_id,
                    trigger,
                    succeeded,
                    state,
                    failure_reason,
                    failure_code,
                    happened_at
                FROM connection_history
                ORDER BY happened_at DESC, id DESC
                """
            ).fetchall()
            rule_rows = connection.execute(
                """
                SELECT
                    device_id,
                    is_favorite,
                    is_ignored,
                    priority,
                    auto_connect_on_reappear
                FROM device_rules
                """
            ).fetchall()
            last_device_rows = connection.execute(
                "SELECT position, device_id FROM last_devices ORDER BY position ASC"
            ).fetchall()

        cache_by_id = {
            row["device_id"]: {
                "name": row["name"],
                "supports_audio_playback": bool(row["supports_audio_playback"]),
                "supports_microphone": bool(row["supports_microphone"]),
                "last_seen_at": row["last_seen_at"],
            }
            for row in cache_rows
        }
        latest_connection_by_id: dict[str, dict[str, Any]] = {}
        for row in connection_rows:
            device_id = row["device_id"]
            if device_id in latest_connection_by_id:
                continue
            latest_connection_by_id[device_id] = {
                "last_connection_at": row["happened_at"],
                "last_connection_state": row["state"],
                "last_connection_trigger": row["trigger"],
                "last_failure_reason": row["failure_reason"],
                "last_failure_code": row["failure_code"],
            }

        rules_by_id = {
            row["device_id"]: {
                "is_favorite": bool(row["is_favorite"]),
                "is_ignored": bool(row["is_ignored"]),
                "auto_connect_on_reappear": bool(row["auto_connect_on_reappear"]),
                "priority": row["priority"],
            }
            for row in rule_rows
        }
        last_device_ids = [row["device_id"] for row in last_device_rows]

        candidate_ids = {
            *latest_connection_by_id.keys(),
            *rules_by_id.keys(),
            *last_device_ids,
        }
        history = [
            self._build_device_history_entry(
                device_id=device_id,
                cache=cache_by_id.get(device_id),
                latest_connection=latest_connection_by_id.get(device_id),
                saved_rule=rules_by_id.get(device_id),
            )
            for device_id in candidate_ids
        ]
        history.sort(key=_device_history_sort_key)
        return history[: max(limit, 0)]

    def _migrate_legacy_config(self, connection: sqlite3.Connection) -> None:
        if not self.legacy_config_path.exists():
            return

        try:
            payload = json.loads(self.legacy_config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}

        if isinstance(payload, dict):
            self._save_config(connection, _config_from_payload(payload))
        self._backup_legacy_file(self.legacy_config_path)

    def _migrate_legacy_log(self, connection: sqlite3.Connection) -> None:
        if not self.legacy_log_path.exists():
            return

        for line in self.legacy_log_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            parsed = _LEGACY_LOG_PATTERN.match(line)
            if parsed is None:
                self._record_log(
                    connection,
                    level="RAW",
                    message=line,
                    logger_name="audio_blue.legacy",
                    created_at=None,
                    extra={"rawLine": line},
                )
                continue
            timestamp = datetime.strptime(
                parsed.group("timestamp"),
                "%Y-%m-%d %H:%M:%S,%f",
            ).replace(tzinfo=UTC)
            self._record_log(
                connection,
                level=parsed.group("level"),
                message=parsed.group("message"),
                logger_name="audio_blue.legacy",
                created_at=timestamp,
                extra={"migratedFrom": str(self.legacy_log_path)},
            )

        self._backup_legacy_file(self.legacy_log_path)

    def _migrate_legacy_diagnostics(self, connection: sqlite3.Connection) -> None:
        if not self.legacy_diagnostics_dir.exists():
            return

        for file_path in sorted(self.legacy_diagnostics_dir.glob("*.json")):
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {
                    "source": "legacy-invalid-json",
                    "generatedAt": _utc_now().isoformat(),
                    "raw": file_path.read_text(encoding="utf-8", errors="replace"),
                    "config": {"reconnect": False, "lastDevices": [], "deviceRules": {}},
                    "devices": [],
                    "attempts": [],
                }
            if not isinstance(payload, dict):
                payload = {
                    "source": "legacy-invalid-shape",
                    "generatedAt": _utc_now().isoformat(),
                    "payload": payload,
                    "config": {"reconnect": False, "lastDevices": [], "deviceRules": {}},
                    "devices": [],
                    "attempts": [],
                }

            snapshot_id = self._save_diagnostics_snapshot(connection, payload)
            self._record_diagnostics_export(
                connection,
                export_path=file_path,
                snapshot_id=snapshot_id,
                exported_at=_datetime_from_timestamp(file_path.stat().st_mtime),
            )
            self._backup_legacy_file(file_path)

    def _backup_legacy_file(self, path: Path) -> None:
        if not path.exists():
            return
        backup_path = path.with_suffix(path.suffix + ".legacy.bak")
        if backup_path.exists():
            return
        path.rename(backup_path)

    def _load_config(self, connection: sqlite3.Connection) -> AppConfig:
        rows = connection.execute("SELECT key, value FROM config").fetchall()
        values = {row["key"]: row["value"] for row in rows}

        rules_rows = connection.execute(
            """
            SELECT device_id, is_favorite, is_ignored, priority, auto_connect_on_startup, auto_connect_on_reappear
            FROM device_rules
            """
        ).fetchall()
        device_rules = {
            row["device_id"]: DeviceRule(
                is_favorite=bool(row["is_favorite"]),
                is_ignored=bool(row["is_ignored"]),
                priority=row["priority"] if row["priority"] is not None else None,
                auto_connect_on_startup=bool(row["auto_connect_on_startup"]),
                auto_connect_on_reappear=bool(row["auto_connect_on_reappear"]),
            )
            for row in rules_rows
        }

        last_device_rows = connection.execute(
            "SELECT device_id FROM last_devices ORDER BY position ASC"
        ).fetchall()
        last_devices = [row["device_id"] for row in last_device_rows]

        policy = values.get("notification.policy", NotificationPreferences().policy)
        if policy not in _POLICY_VALUES:
            policy = NotificationPreferences().policy

        theme = values.get("ui.theme", UiPreferences().theme)
        if theme not in _THEME_VALUES:
            theme = UiPreferences().theme

        language = values.get("ui.language", UiPreferences().language)
        if language not in _LANGUAGE_VALUES:
            language = UiPreferences().language

        launch_delay = _coerce_int(
            values.get("startup.launch_delay_seconds"),
            StartupPreferences().launch_delay_seconds,
            minimum=0,
        )

        return AppConfig(
            reconnect=_coerce_bool(values.get("reconnect"), False),
            last_devices=last_devices,
            device_rules=device_rules,
            notification=NotificationPreferences(policy=policy),
            startup=StartupPreferences(
                autostart=_coerce_bool(values.get("startup.autostart"), False),
                run_in_background=_coerce_bool(values.get("startup.run_in_background"), False),
                launch_delay_seconds=launch_delay,
            ),
            ui=UiPreferences(
                theme=theme,
                high_contrast=_coerce_bool(values.get("ui.high_contrast"), False),
                language=language,
            ),
        )

    def _save_config(self, connection: sqlite3.Connection, config: AppConfig) -> None:
        now = _utc_now().isoformat()
        entries = {
            "reconnect": str(int(config.reconnect)),
            "notification.policy": config.notification.policy,
            "startup.autostart": str(int(config.startup.autostart)),
            "startup.run_in_background": str(int(config.startup.run_in_background)),
            "startup.launch_delay_seconds": str(config.startup.launch_delay_seconds),
            "ui.theme": config.ui.theme,
            "ui.high_contrast": str(int(config.ui.high_contrast)),
            "ui.language": config.ui.language,
        }
        connection.executemany(
            """
            INSERT INTO config(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            [(key, value, now) for key, value in entries.items()],
        )

        connection.execute("DELETE FROM device_rules")
        if config.device_rules:
            connection.executemany(
                """
                INSERT INTO device_rules(
                    device_id,
                    is_favorite,
                    is_ignored,
                    priority,
                    auto_connect_on_startup,
                    auto_connect_on_reappear,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        device_id,
                        int(rule.is_favorite),
                        int(rule.is_ignored),
                        rule.priority,
                        int(rule.auto_connect_on_startup),
                        int(rule.auto_connect_on_reappear),
                        now,
                    )
                    for device_id, rule in config.device_rules.items()
                ],
            )

        connection.execute("DELETE FROM last_devices")
        if config.last_devices:
            connection.executemany(
                "INSERT INTO last_devices(position, device_id) VALUES (?, ?)",
                [(index, device_id) for index, device_id in enumerate(config.last_devices)],
            )

    def _save_diagnostics_snapshot(
        self,
        connection: sqlite3.Connection,
        snapshot: dict[str, Any],
    ) -> int:
        generated_at = _parse_iso_datetime(snapshot.get("generatedAt")) or _utc_now()
        source = str(snapshot.get("source", "unknown"))
        cursor = connection.execute(
            """
            INSERT INTO diagnostics_snapshots(source, generated_at, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                source,
                generated_at.isoformat(),
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                _utc_now().isoformat(),
            ),
        )
        return int(cursor.lastrowid)

    def _record_diagnostics_export(
        self,
        connection: sqlite3.Connection,
        *,
        export_path: Path | str,
        snapshot_id: int | None,
        exported_at: datetime | None,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO diagnostics_exports(snapshot_id, export_path, exported_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                snapshot_id,
                str(export_path),
                (exported_at or _utc_now()).astimezone(UTC).isoformat(),
                _utc_now().isoformat(),
            ),
        )
        return int(cursor.lastrowid)

    def _record_log(
        self,
        connection: sqlite3.Connection,
        *,
        level: str,
        message: str,
        logger_name: str,
        created_at: datetime | None,
        extra: dict[str, Any] | None,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO log_records(level, message, logger_name, created_at, extra_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                level,
                message,
                logger_name,
                (created_at or _utc_now()).astimezone(UTC).isoformat(),
                json.dumps(extra, ensure_ascii=False, sort_keys=True) if extra else None,
            ),
        )
        return int(cursor.lastrowid)

    def _build_device_history_entry(
        self,
        *,
        device_id: str,
        cache: dict[str, Any] | None,
        latest_connection: dict[str, Any] | None,
        saved_rule: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "device_id": device_id,
            "name": (
                str(cache.get("name"))
                if isinstance(cache, dict) and cache.get("name")
                else device_id
            ),
            "supports_audio_playback": bool(
                cache.get("supports_audio_playback", False) if isinstance(cache, dict) else False
            ),
            "supports_microphone": bool(
                cache.get("supports_microphone", False) if isinstance(cache, dict) else False
            ),
            "last_seen_at": cache.get("last_seen_at") if isinstance(cache, dict) else None,
            "last_connection_at": (
                latest_connection.get("last_connection_at")
                if isinstance(latest_connection, dict)
                else None
            ),
            "last_connection_state": (
                latest_connection.get("last_connection_state")
                if isinstance(latest_connection, dict)
                else None
            ),
            "last_connection_trigger": (
                latest_connection.get("last_connection_trigger")
                if isinstance(latest_connection, dict)
                else None
            ),
            "last_failure_reason": (
                latest_connection.get("last_failure_reason")
                if isinstance(latest_connection, dict)
                else None
            ),
            "last_failure_code": (
                latest_connection.get("last_failure_code")
                if isinstance(latest_connection, dict)
                else None
            ),
            "saved_rule": {
                "is_favorite": bool(saved_rule.get("is_favorite", False))
                if isinstance(saved_rule, dict)
                else False,
                "is_ignored": bool(saved_rule.get("is_ignored", False))
                if isinstance(saved_rule, dict)
                else False,
                "auto_connect_on_reappear": bool(saved_rule.get("auto_connect_on_reappear", False))
                if isinstance(saved_rule, dict)
                else False,
                "priority": saved_rule.get("priority") if isinstance(saved_rule, dict) else None,
            },
        }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _datetime_from_timestamp(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _coerce_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value in {"1", "true", "True", "yes"}


def _coerce_int(value: str | None, default: int, minimum: int = 0) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else default


def _config_from_payload(payload: dict[str, Any]) -> AppConfig:
    reconnect = bool(payload.get("reconnect", False))
    raw_last_devices = payload.get("lastDevices", [])
    last_devices = raw_last_devices if isinstance(raw_last_devices, list) else []
    device_rules = _device_rules_from_payload(payload.get("deviceRules"))
    notification = _notification_from_payload(payload.get("notification"))
    startup = _startup_from_payload(payload.get("startup"))
    ui = _ui_from_payload(payload.get("ui"))
    return AppConfig(
        reconnect=reconnect,
        last_devices=[item for item in last_devices if isinstance(item, str)],
        device_rules=device_rules,
        notification=notification,
        startup=startup,
        ui=ui,
    )


def _device_rules_from_payload(payload: object) -> dict[str, DeviceRule]:
    if not isinstance(payload, dict):
        return {}
    rules: dict[str, DeviceRule] = {}
    for device_id, raw_rule in payload.items():
        if not isinstance(device_id, str) or not isinstance(raw_rule, dict):
            continue
        rules[device_id] = DeviceRule(
            is_favorite=bool(raw_rule.get("isFavorite", False)),
            is_ignored=bool(raw_rule.get("isIgnored", False)),
            priority=raw_rule.get("priority") if isinstance(raw_rule.get("priority"), int) else None,
            auto_connect_on_startup=bool(raw_rule.get("autoConnectOnStartup", False)),
            auto_connect_on_reappear=bool(raw_rule.get("autoConnectOnReappear", False)),
        )
    return rules


def _notification_from_payload(payload: object) -> NotificationPreferences:
    if not isinstance(payload, dict):
        return NotificationPreferences()
    policy = payload.get("policy")
    if policy not in _POLICY_VALUES:
        return NotificationPreferences()
    return NotificationPreferences(policy=policy)


def _startup_from_payload(payload: object) -> StartupPreferences:
    if not isinstance(payload, dict):
        return StartupPreferences()
    launch_delay = payload.get(
        "launchDelaySeconds",
        StartupPreferences().launch_delay_seconds,
    )
    return StartupPreferences(
        autostart=bool(payload.get("autostart", False)),
        run_in_background=bool(payload.get("runInBackground", False)),
        launch_delay_seconds=launch_delay if isinstance(launch_delay, int) and launch_delay >= 0 else 3,
    )


def _ui_from_payload(payload: object) -> UiPreferences:
    if not isinstance(payload, dict):
        return UiPreferences()
    theme = payload.get("theme")
    if theme not in _THEME_VALUES:
        theme = UiPreferences().theme
    language = payload.get("language")
    if language not in _LANGUAGE_VALUES:
        language = UiPreferences().language
    return UiPreferences(
        theme=theme,
        high_contrast=bool(payload.get("highContrast", False)),
        language=language,
    )


def _device_history_sort_key(entry: dict[str, Any]) -> tuple[int, float, int, float, str, str]:
    last_connection_at = _parse_iso_datetime(entry.get("last_connection_at"))
    last_seen_at = _parse_iso_datetime(entry.get("last_seen_at"))
    return (
        0 if last_connection_at is not None else 1,
        -(last_connection_at.timestamp()) if last_connection_at is not None else 0.0,
        0 if last_seen_at is not None else 1,
        -(last_seen_at.timestamp()) if last_seen_at is not None else 0.0,
        str(entry.get("name", "")).casefold(),
        str(entry.get("device_id", "")).casefold(),
    )
