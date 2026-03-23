import json
import sqlite3
from datetime import UTC, datetime, timedelta

from audio_blue.models import AppConfig, DeviceRule
from audio_blue.storage import SQLiteStorage


def test_initialize_creates_schema_tables(tmp_path):
    database_path = tmp_path / "audioblue.db"
    storage = SQLiteStorage(db_path=database_path)

    storage.initialize()

    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert {
        "metadata",
        "config",
        "device_rules",
        "last_devices",
        "device_cache",
        "connection_history",
        "diagnostics_snapshots",
        "diagnostics_exports",
        "log_records",
    }.issubset(table_names)
    assert str(journal_mode).lower() == "wal"


def test_migrate_legacy_files_imports_and_is_idempotent(tmp_path):
    legacy_config_path = tmp_path / "config.json"
    legacy_log_path = tmp_path / "audioblue.log"
    legacy_diagnostics_dir = tmp_path / "diagnostics"
    legacy_diagnostics_dir.mkdir(parents=True)

    legacy_config_path.write_text(
        json.dumps(
            {
                "reconnect": True,
                "lastDevices": ["device-1"],
                "deviceRules": {"device-1": {"isFavorite": True, "priority": 1}},
            }
        ),
        encoding="utf-8",
    )
    legacy_log_path.write_text(
        "\n".join(
            [
                "2026-03-20 10:20:30,123 INFO legacy info message",
                "unstructured log line",
            ]
        ),
        encoding="utf-8",
    )
    (legacy_diagnostics_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "source": "legacy",
                "generatedAt": "2026-03-20T10:20:30+00:00",
                "config": {"reconnect": True, "lastDevices": ["device-1"], "deviceRules": {}},
                "devices": [],
                "attempts": [],
            }
        ),
        encoding="utf-8",
    )

    storage = SQLiteStorage(
        db_path=tmp_path / "audioblue.db",
        legacy_config_path=legacy_config_path,
        legacy_log_path=legacy_log_path,
        legacy_diagnostics_dir=legacy_diagnostics_dir,
    )
    storage.initialize()

    storage.migrate_legacy_files()
    first_load = storage.load_config()
    storage.migrate_legacy_files()
    second_load = storage.load_config()

    assert first_load == second_load == AppConfig(
        reconnect=True,
        last_devices=["device-1"],
        device_rules={"device-1": DeviceRule(is_favorite=True, priority=1)},
    )
    assert legacy_config_path.with_suffix(".json.legacy.bak").exists()
    assert legacy_log_path.with_suffix(".log.legacy.bak").exists()
    assert (legacy_diagnostics_dir / "snapshot.json.legacy.bak").exists()

    with sqlite3.connect(storage.db_path) as connection:
        log_records = connection.execute("SELECT level, message FROM log_records ORDER BY id").fetchall()
        snapshot_count = connection.execute("SELECT COUNT(*) FROM diagnostics_snapshots").fetchone()[0]
        export_count = connection.execute("SELECT COUNT(*) FROM diagnostics_exports").fetchone()[0]

    assert len(log_records) == 2
    assert any(level == "RAW" and message == "unstructured log line" for level, message in log_records)
    assert snapshot_count == 1
    assert export_count == 1


def test_purge_expired_records_keeps_config_rules_and_cache(tmp_path):
    database_path = tmp_path / "audioblue.db"
    storage = SQLiteStorage(db_path=database_path)
    storage.initialize()

    storage.save_config(
        AppConfig(
            reconnect=True,
            last_devices=["device-1"],
            device_rules={"device-1": DeviceRule(is_favorite=True, priority=7)},
        )
    )
    now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    stale_time = now - timedelta(days=120)
    fresh_time = now - timedelta(days=7)

    storage.upsert_device_cache(
        device_id="device-1",
        name="Headphones",
        connection_state="disconnected",
        supports_audio_playback=True,
        supports_microphone=False,
        last_seen_at=now,
    )
    storage.record_connection_attempt(
        device_id="device-1",
        trigger="startup",
        succeeded=False,
        state="timeout",
        failure_reason="legacy-timeout",
        failure_code="TIMEOUT",
        happened_at=stale_time,
    )
    storage.record_connection_attempt(
        device_id="device-1",
        trigger="reappear",
        succeeded=True,
        state="connected",
        happened_at=fresh_time,
    )
    stale_snapshot_id = storage.save_diagnostics_snapshot(
        {
            "source": "legacy",
            "generatedAt": stale_time.isoformat(),
            "config": {"reconnect": False, "lastDevices": [], "deviceRules": {}},
            "devices": [],
            "attempts": [],
        }
    )
    fresh_snapshot_id = storage.save_diagnostics_snapshot(
        {
            "source": "runtime",
            "generatedAt": fresh_time.isoformat(),
            "config": {"reconnect": True, "lastDevices": ["device-1"], "deviceRules": {}},
            "devices": [],
            "attempts": [],
        }
    )
    storage.record_diagnostics_export(
        export_path=tmp_path / "diagnostics" / "legacy.json",
        snapshot_id=stale_snapshot_id,
        exported_at=stale_time,
    )
    storage.record_diagnostics_export(
        export_path=tmp_path / "diagnostics" / "fresh.json",
        snapshot_id=fresh_snapshot_id,
        exported_at=fresh_time,
    )
    storage.record_log(
        level="INFO",
        message="old log",
        logger_name="audio_blue",
        created_at=stale_time,
    )
    storage.record_log(
        level="INFO",
        message="fresh log",
        logger_name="audio_blue",
        created_at=fresh_time,
    )

    storage.purge_expired_records(now=now, retention_days=90)

    loaded = storage.load_config()
    assert loaded.reconnect is True
    assert loaded.device_rules["device-1"].priority == 7

    with sqlite3.connect(database_path) as connection:
        history_count = connection.execute("SELECT COUNT(*) FROM connection_history").fetchone()[0]
        snapshot_count = connection.execute("SELECT COUNT(*) FROM diagnostics_snapshots").fetchone()[0]
        export_count = connection.execute("SELECT COUNT(*) FROM diagnostics_exports").fetchone()[0]
        log_count = connection.execute("SELECT COUNT(*) FROM log_records").fetchone()[0]
        cache_count = connection.execute("SELECT COUNT(*) FROM device_cache").fetchone()[0]
        last_devices_count = connection.execute("SELECT COUNT(*) FROM last_devices").fetchone()[0]

    assert history_count == 1
    assert snapshot_count == 1
    assert export_count == 1
    assert log_count == 1
    assert cache_count == 1
    assert last_devices_count == 1
