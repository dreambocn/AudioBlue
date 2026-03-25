import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from audio_blue.diagnostics import (
    build_diagnostics_snapshot,
    export_diagnostics_snapshot,
    export_support_bundle,
)
from audio_blue.models import (
    AppConfig,
    ConnectionAttempt,
    DeviceCapabilities,
    DeviceRule,
    DeviceSummary,
)
from audio_blue.storage import SQLiteStorage


def test_snapshot_serializes_config_devices_and_attempts():
    happened_at = datetime(2026, 3, 22, 2, 30, tzinfo=UTC)
    attempt = ConnectionAttempt(
        trigger="startup",
        succeeded=False,
        state="timeout",
        failure_reason="request timed out",
        happened_at=happened_at,
    )
    config = AppConfig(
        reconnect=True,
        last_devices=["device-1"],
        device_rules={"device-1": DeviceRule(is_favorite=True, priority=1)},
    )
    devices = [
        DeviceSummary(
            device_id="device-1",
            name="Headphones",
            connection_state="disconnected",
            capabilities=DeviceCapabilities(supports_audio_playback=True),
            last_connection_attempt=attempt,
        )
    ]

    snapshot = build_diagnostics_snapshot(
        config=config,
        devices=devices,
        attempts=[attempt],
        source="unit-test",
    )

    assert snapshot["source"] == "unit-test"
    assert snapshot["config"]["reconnect"] is True
    assert snapshot["config"]["deviceRules"]["device-1"]["isFavorite"] is True
    assert snapshot["devices"][0]["name"] == "Headphones"
    assert snapshot["devices"][0]["lastConnectionAttempt"]["state"] == "timeout"
    assert snapshot["attempts"][0]["happenedAt"] == happened_at.isoformat()


def test_export_snapshot_writes_json_file(tmp_path):
    snapshot = build_diagnostics_snapshot(
        config=AppConfig(),
        devices=[],
        attempts=[],
        source="unit-test",
    )
    export_path = tmp_path / "diagnostics" / "snapshot.json"

    written_path = export_diagnostics_snapshot(snapshot=snapshot, path=export_path)

    payload = json.loads(written_path.read_text(encoding="utf-8"))
    assert written_path == export_path
    assert payload["source"] == "unit-test"
    assert payload["devices"] == []
    assert payload["attempts"] == []

    database_path = tmp_path / "audioblue.db"
    with sqlite3.connect(database_path) as connection:
        snapshot_count = connection.execute("SELECT COUNT(*) FROM diagnostics_snapshots").fetchone()[0]
        export_count = connection.execute("SELECT COUNT(*) FROM diagnostics_exports").fetchone()[0]

    assert snapshot_count == 1
    assert export_count == 1


def test_export_support_bundle_writes_required_files_and_records_export(tmp_path):
    storage = SQLiteStorage(db_path=tmp_path / "audioblue.db")
    storage.initialize()
    storage.record_activity_event(
        area="connection",
        event_type="connection.failed",
        level="error",
        title="连接失败",
        detail="Phone 连接超时。",
        device_id="device-1",
    )
    storage.record_connection_attempt(
        device_id="device-1",
        trigger="startup",
        succeeded=False,
        state="timeout",
        failure_reason="连接超时",
        failure_code="connection.timeout",
    )
    snapshot = build_diagnostics_snapshot(
        config=AppConfig(reconnect=True, last_devices=["device-1"]),
        devices=[],
        attempts=[],
        source="unit-test",
    )
    bundle_path = tmp_path / "support-bundles" / "support-bundle.zip"

    written_path = export_support_bundle(
        snapshot=snapshot,
        path=bundle_path,
        storage=storage,
    )

    assert written_path == bundle_path
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        assert {
            "summary.json",
            "activity-events.json",
            "connection-history.json",
            "device-history.json",
            "diagnostics.json",
            "config.json",
        }.issubset(names)
        summary = json.loads(archive.read("summary.json").decode("utf-8"))
        assert summary["source"] == "unit-test"

    with sqlite3.connect(storage.db_path) as connection:
        export_paths = [
            row[0]
            for row in connection.execute(
                "SELECT export_path FROM diagnostics_exports ORDER BY id DESC"
            ).fetchall()
        ]

    assert str(bundle_path) in export_paths
