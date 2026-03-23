import json
import sqlite3
from datetime import UTC, datetime

from audio_blue.diagnostics import (
    build_diagnostics_snapshot,
    export_diagnostics_snapshot,
)
from audio_blue.models import (
    AppConfig,
    ConnectionAttempt,
    DeviceCapabilities,
    DeviceRule,
    DeviceSummary,
)


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
