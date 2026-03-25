from datetime import UTC, datetime

from audio_blue.app_state import AppStateStore, humanize_connection_failure
from audio_blue.models import AppConfig, DeviceRule, DeviceSummary, UiPreferences


def test_humanize_connection_failure_returns_user_friendly_copy():
    assert humanize_connection_failure("timeout", language="en-US") == "Connection timed out before audio could start."
    assert humanize_connection_failure("denied", language="en-US") == "Windows denied the audio connection request."
    assert humanize_connection_failure("error", language="zh-CN") == "AudioBlue 无法连接到该设备。"


def test_app_state_tracks_failures_and_rule_updates():
    store = AppStateStore(config=AppConfig(ui=UiPreferences(language="zh-CN")))
    store.sync_devices(
        [
            DeviceSummary(
                device_id="device-1",
                name="Headphones",
                last_seen_at=datetime(2026, 3, 23, 9, 30, tzinfo=UTC),
            )
        ]
    )

    store.handle_connector_event(
        {"event": "device_connection_failed", "device_id": "device-1", "state": "timeout"}
    )
    store.update_device_rule(
        "device-1",
        {
            "is_favorite": True,
            "auto_connect_on_reappear": True,
        },
    )

    snapshot = store.snapshot()

    assert snapshot["lastFailure"]["deviceId"] == "device-1"
    assert snapshot["lastFailure"]["state"] == "timeout"
    assert snapshot["lastFailure"]["code"] == "connection.timeout"
    assert snapshot["lastFailure"]["message"] == humanize_connection_failure("timeout", language="zh-CN")
    assert snapshot["settings"]["ui"]["language"] == "zh-CN"
    assert snapshot["devices"][0]["lastSeenAt"] == "2026-03-23T09:30:00+00:00"
    assert snapshot["deviceRules"]["device-1"] == {
        "isFavorite": True,
        "isIgnored": False,
        "priority": None,
        "autoConnectOnStartup": False,
        "autoConnectOnReappear": True,
    }


def test_app_state_reorders_priorities_without_dropping_existing_flags():
    store = AppStateStore(
        config=AppConfig(
            device_rules={
                "device-1": DeviceRule(is_favorite=True, auto_connect_on_startup=True),
                "device-2": DeviceRule(auto_connect_on_startup=True),
            }
        )
    )

    store.reorder_device_priority(["device-2", "device-1"])

    assert store.config.device_rules["device-2"].priority == 1
    assert store.config.device_rules["device-1"].priority == 2
    assert store.config.device_rules["device-1"].is_favorite is True
    assert store.config.device_rules["device-1"].auto_connect_on_startup is True


def test_app_state_connection_attempt_uses_failure_code_as_stable_contract():
    store = AppStateStore(config=AppConfig())
    store.sync_devices([DeviceSummary(device_id="device-1", name="Headphones")])

    store.handle_connector_event(
        {"event": "device_connection_failed", "device_id": "device-1", "state": "denied"}
    )
    snapshot = store.snapshot()

    attempt = snapshot["devices"][0]["lastConnectionAttempt"]
    assert attempt["state"] == "denied"
    assert attempt["failureCode"] == "connection.denied"


def test_app_state_snapshot_includes_scan_visibility_flag():
    store = AppStateStore(config=AppConfig())
    store.sync_devices(
        [
            DeviceSummary(
                device_id="device-1",
                name="Phone",
                connection_state="connected",
                present_in_last_scan=False,
            )
        ]
    )

    snapshot = store.snapshot()

    assert snapshot["devices"][0]["presentInLastScan"] is False


def test_app_state_snapshot_includes_full_device_history_payload():
    store = AppStateStore(config=AppConfig())
    store.sync_devices(
        [
            DeviceSummary(
                device_id="device-visible",
                name="Visible Speaker",
                connection_state="disconnected",
            )
        ]
    )
    setattr(
        store,
        "_history_provider",
        lambda limit=10: [
            {
                "device_id": "device-visible",
                "name": "Visible Speaker",
                "supports_audio_playback": True,
                "last_seen_at": "2026-03-23T09:20:00+00:00",
                "last_connection_at": "2026-03-23T09:10:00+00:00",
                "last_connection_state": "connected",
                "last_connection_trigger": "manual",
                "last_failure_reason": None,
                "saved_rule": {
                    "is_favorite": False,
                    "is_ignored": False,
                    "auto_connect_on_reappear": False,
                    "priority": None,
                },
            },
            {
                "device_id": "device-offline",
                "name": "Offline Headset",
                "supports_audio_playback": True,
                "last_seen_at": "2026-03-22T18:00:00+00:00",
                "last_connection_at": "2026-03-22T17:30:00+00:00",
                "last_connection_state": "timeout",
                "last_connection_trigger": "startup",
                "last_failure_reason": "Connection timed out before audio could start.",
                "saved_rule": {
                    "is_favorite": True,
                    "is_ignored": False,
                    "auto_connect_on_reappear": True,
                    "priority": 1,
                },
            },
        ],
    )

    snapshot = store.snapshot()

    assert [entry["deviceId"] for entry in snapshot["deviceHistory"]] == [
        "device-visible",
        "device-offline",
    ]
    assert snapshot["deviceHistory"][1] == {
        "deviceId": "device-offline",
        "name": "Offline Headset",
        "supportsAudioPlayback": True,
        "firstSeenAt": None,
        "lastSeenAt": "2026-03-22T18:00:00+00:00",
        "lastConnectionAt": "2026-03-22T17:30:00+00:00",
        "lastConnectionState": "timeout",
        "lastConnectionTrigger": "startup",
        "lastFailureReason": "Connection timed out before audio could start.",
        "lastSuccessAt": None,
        "lastFailureAt": None,
        "lastAbsentAt": None,
        "lastPresentAt": None,
        "successCount": 0,
        "failureCount": 0,
        "lastErrorCode": None,
        "lastPresentReason": None,
        "lastAbsentReason": None,
        "savedRule": {
            "isFavorite": True,
            "isIgnored": False,
            "autoConnectOnReappear": True,
            "priority": 1,
        },
    }


def test_app_state_snapshot_uses_structured_activity_connection_overview_and_diagnostics():
    class Provider:
        def list_device_history(self, limit=10):
            return []

        def list_activity_events(self, limit=20):
            return [
                {
                    "id": 7,
                    "area": "connection",
                    "event_type": "connection.failed",
                    "level": "error",
                    "title": "连接失败",
                    "detail": "Phone 连接超时。",
                    "device_id": "device-1",
                    "happened_at": "2026-03-25T10:00:00+00:00",
                }
            ]

        def list_connection_attempts(self, limit=20):
            return [
                {
                    "device_id": "device-1",
                    "device_name": "Phone",
                    "trigger": "startup",
                    "succeeded": False,
                    "state": "timeout",
                    "failure_reason": "连接超时",
                    "failure_code": "connection.timeout",
                    "happened_at": "2026-03-25T10:00:00+00:00",
                }
            ]

        def build_runtime_diagnostics(self):
            return {
                "databasePath": "C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\audioblue.db",
                "logRetentionDays": 90,
                "activityEventCount": 1,
                "connectionAttemptCount": 1,
                "lastExportPath": "C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\diagnostics\\diagnostics-1.json",
                "lastSupportBundlePath": "C:\\Users\\DreamBo\\AppData\\Local\\AudioBlue\\support-bundles\\support-1.zip",
                "recentErrors": [
                    {
                        "title": "连接失败",
                        "detail": "Phone 连接超时。",
                        "happenedAt": "2026-03-25T10:00:00+00:00",
                    }
                ],
            }

    store = AppStateStore(config=AppConfig(), history_provider=Provider())
    store.sync_devices(
        [
            DeviceSummary(
                device_id="device-1",
                name="Phone",
                connection_state="connecting",
                last_seen_at=datetime(2026, 3, 25, 10, 0, tzinfo=UTC),
            )
        ]
    )

    snapshot = store.snapshot()

    assert snapshot["recentActivity"] == [
        {
            "id": "7",
            "area": "connection",
            "eventType": "connection.failed",
            "level": "error",
            "title": "连接失败",
            "detail": "Phone 连接超时。",
            "deviceId": "device-1",
            "happenedAt": "2026-03-25T10:00:00+00:00",
            "errorCode": None,
            "details": None,
        }
    ]
    assert snapshot["connectionOverview"]["status"] == "connecting"
    assert snapshot["connectionOverview"]["lastErrorCode"] == "connection.timeout"
    assert snapshot["connectionOverview"]["lastErrorMessage"] == "连接超时"
    assert snapshot["diagnostics"]["databasePath"].endswith("audioblue.db")
    assert snapshot["diagnostics"]["recentErrors"][0]["title"] == "连接失败"
