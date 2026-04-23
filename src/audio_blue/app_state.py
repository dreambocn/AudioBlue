"""负责把运行态设备信息整理成前端快照。"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from typing import Any

from audio_blue.localization import connection_failure_message
from audio_blue.models import AppConfig, ConnectionAttempt, DeviceRule, DeviceSummary
from audio_blue.rules_engine import RulesEngine


def humanize_connection_failure(state: str, *, language: str = "system") -> str:
    """把连接失败状态码转换为界面可直接展示的文案。"""
    return connection_failure_message(state, language=language)


class AppStateStore:
    """维护控制中心所需的内存态快照，并负责事件到界面模型的映射。"""

    def __init__(self, config: AppConfig, history_provider: Any | None = None) -> None:
        self.config = config
        self._history_provider = history_provider
        self._devices: dict[str, DeviceSummary] = {}
        self._last_failure: dict[str, str] | None = None
        self._last_trigger: str | None = None

    def sync_devices(self, devices: list[DeviceSummary]) -> None:
        self._devices = {device.device_id: device for device in devices}

    def handle_connector_event(self, payload: dict[str, Any]) -> None:
        """吸收连接层事件，并把它们折叠成统一的设备状态。"""
        event_name = payload.get("event")
        device_id = payload.get("device_id")
        trigger = payload.get("trigger")
        trigger_name = trigger if isinstance(trigger, str) else "manual"
        if not isinstance(device_id, str):
            return

        if event_name == "device_connected":
            self._apply_device_state(device_id=device_id, state="connected", trigger=trigger_name)
        elif event_name in {"device_disconnected", "device_state_changed"}:
            state = payload.get("state", "disconnected")
            if isinstance(state, str):
                self._apply_device_state(
                    device_id=device_id,
                    state=state,
                    trigger=trigger_name,
                    failure_code_override=_string_or_none(payload.get("failure_code")),
                    failure_reason_override=_resolve_failure_message(
                        state=state,
                        failure_code=_string_or_none(payload.get("failure_code")),
                        failure_message=_string_or_none(payload.get("failure_message")),
                        language=getattr(self.config.ui, "language", "system"),
                    ),
                )
                if state == "stale":
                    language = getattr(self.config.ui, "language", "system")
                    self._last_failure = {
                        "deviceId": device_id,
                        "state": state,
                        "code": f"connection.{state}",
                        "message": humanize_connection_failure(state, language=language),
                    }
        elif event_name == "device_connection_failed":
            state = payload.get("state", "error")
            if not isinstance(state, str):
                state = "error"
            language = getattr(self.config.ui, "language", "system")
            failure_code = _string_or_none(payload.get("failure_code")) or f"connection.{state}"
            failure_message = _resolve_failure_message(
                state=state,
                failure_code=failure_code,
                failure_message=_string_or_none(payload.get("failure_message")),
                language=language,
            )
            self._apply_device_state(
                device_id=device_id,
                state=state,
                trigger=trigger_name,
                failure_code_override=failure_code,
                failure_reason_override=failure_message,
            )
            self._last_failure = {
                "deviceId": device_id,
                "state": state,
                "code": failure_code,
                "message": failure_message,
            }

    def update_device_rule(self, device_id: str, rule_patch: dict[str, Any]) -> DeviceRule:
        current_rule = self.config.device_rules.get(device_id, DeviceRule())
        next_rule = replace(current_rule, **rule_patch)
        self.config.device_rules[device_id] = next_rule
        return next_rule

    def reorder_device_priority(self, device_ids: list[str]) -> None:
        for index, device_id in enumerate(device_ids, start=1):
            current_rule = self.config.device_rules.get(device_id, DeviceRule())
            self.config.device_rules[device_id] = replace(current_rule, priority=index)

    def snapshot(self) -> dict[str, Any]:
        """生成供前端桥接层消费的完整快照。"""
        rules_engine = RulesEngine(self.config)
        auto_connect_candidates = rules_engine.get_auto_connect_candidates(
            devices=list(self._devices.values()),
            trigger="startup",
        )
        startup_settings = asdict(self.config.startup)
        startup_settings["reconnectOnNextStart"] = self.config.reconnect
        recent_activity = self._load_recent_activity(limit=20)
        connection_overview = self._build_connection_overview()
        return {
            "devices": [self._serialize_device(device) for device in self._devices.values()],
            "deviceHistory": self._serialize_device_history(),
            "recentActivity": recent_activity,
            "connectionOverview": connection_overview,
            "deviceRules": {
                device_id: self._serialize_rule(rule)
                for device_id, rule in self.config.device_rules.items()
            },
            "lastFailure": self._last_failure,
            "lastTrigger": self._last_trigger,
            "diagnostics": self._build_diagnostics_state(),
            "settings": {
                "notification": asdict(self.config.notification),
                "startup": startup_settings,
                "ui": asdict(self.config.ui),
            },
            "autoConnectCandidates": [device.device_id for device in auto_connect_candidates],
        }

    def _apply_device_state(
        self,
        device_id: str,
        state: str,
        trigger: str,
        *,
        failure_code_override: str | None = None,
        failure_reason_override: str | None = None,
    ) -> None:
        device = self._devices.get(device_id)
        if device is None:
            return

        # 每次状态切换都同步生成一次连接尝试记录，确保前端历史区与诊断区基于同一份事实。
        attempt = ConnectionAttempt(
            trigger=trigger,
            succeeded=state == "connected",
            state=state,
            failure_reason=(
                None
                if state == "connected"
                else (
                    failure_reason_override
                    or humanize_connection_failure(
                        state,
                        language=getattr(self.config.ui, "language", "system"),
                    )
                )
            ),
            failure_code=(
                None
                if state == "connected"
                else failure_code_override or f"connection.{state}"
            ),
        )
        self._devices[device_id] = replace(
            device,
            connection_state=state,
            last_connection_attempt=attempt,
        )
        self._last_trigger = trigger

    def _serialize_device(self, device: DeviceSummary) -> dict[str, Any]:
        payload = {
            "deviceId": device.device_id,
            "name": device.name,
            "connectionState": device.connection_state,
            "capabilities": asdict(device.capabilities),
            "presentInLastScan": device.present_in_last_scan,
        }
        if device.last_seen_at is not None:
            payload["lastSeenAt"] = device.last_seen_at.isoformat()
        if device.last_connection_attempt is not None:
            payload["lastConnectionAttempt"] = {
                "trigger": device.last_connection_attempt.trigger,
                "succeeded": device.last_connection_attempt.succeeded,
                "state": device.last_connection_attempt.state,
                "failureReason": device.last_connection_attempt.failure_reason,
                "failureCode": device.last_connection_attempt.failure_code,
                "happenedAt": device.last_connection_attempt.happened_at.isoformat(),
            }
        return payload

    def _serialize_rule(self, rule: DeviceRule) -> dict[str, Any]:
        return {
            "isFavorite": rule.is_favorite,
            "isIgnored": rule.is_ignored,
            "priority": rule.priority,
            "autoConnectOnStartup": rule.auto_connect_on_startup,
            "autoConnectOnReappear": rule.auto_connect_on_reappear,
        }

    def _serialize_device_history(self) -> list[dict[str, Any]]:
        raw_entries = self._load_device_history(limit=10)
        return [self._serialize_device_history_entry(entry) for entry in raw_entries]

    def _load_recent_activity(self, *, limit: int) -> list[dict[str, Any]]:
        provider = getattr(self, "_history_provider", None)
        loader = getattr(provider, "list_activity_events", None)
        if not callable(loader):
            return []
        entries = loader(limit=limit)
        if not isinstance(entries, list):
            return []
        normalized: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            normalized.append(
                {
                    "id": str(entry.get("id", "")),
                    "area": str(entry.get("area", "runtime")),
                    "eventType": str(entry.get("event_type", entry.get("eventType", "runtime.event"))),
                    "level": str(entry.get("level", "info")),
                    "title": str(entry.get("title", "")),
                    "detail": str(entry.get("detail", "")) if entry.get("detail") is not None else "",
                    "deviceId": (
                        str(entry.get("device_id"))
                        if entry.get("device_id") is not None
                        else str(entry.get("deviceId"))
                        if entry.get("deviceId") is not None
                        else None
                    ),
                    "happenedAt": str(entry.get("happened_at", entry.get("happenedAt", ""))),
                    "errorCode": (
                        str(entry.get("error_code"))
                        if entry.get("error_code") is not None
                        else str(entry.get("errorCode"))
                        if entry.get("errorCode") is not None
                        else None
                    ),
                    "details": entry.get("details") if isinstance(entry.get("details"), dict) else None,
                }
            )
        return normalized

    def _build_connection_overview(self) -> dict[str, Any]:
        current_device = next(
            (
                device
                for device in self._devices.values()
                if device.connection_state in {"connected", "connecting", "stale"}
            ),
            None,
        )
        attempts = self._load_connection_attempts(limit=20)
        last_attempt = attempts[0] if attempts else None
        last_success = next((item for item in attempts if item.get("succeeded") is True), None)
        last_failure = next((item for item in attempts if item.get("succeeded") is False), None)
        current_status = (
            current_device.connection_state
            if current_device is not None
            else "disconnected"
        )
        current_phase = current_status
        if current_device is None and isinstance(last_attempt, dict) and last_attempt.get("succeeded") is False:
            current_phase = "failed"
        return {
            "status": current_status,
            "currentDeviceId": current_device.device_id if current_device is not None else None,
            "currentDeviceName": current_device.name if current_device is not None else None,
            "currentPhase": current_phase,
            "lastSuccessAt": last_success.get("happened_at") if isinstance(last_success, dict) else None,
            "lastAttemptAt": last_attempt.get("happened_at") if isinstance(last_attempt, dict) else None,
            "lastTrigger": last_attempt.get("trigger") if isinstance(last_attempt, dict) else self._last_trigger,
            "lastErrorCode": (
                last_failure.get("failure_code")
                if isinstance(last_failure, dict)
                else self._last_failure.get("code")
                if isinstance(self._last_failure, dict)
                else None
            ),
            "lastErrorMessage": (
                last_failure.get("failure_reason")
                if isinstance(last_failure, dict)
                else self._last_failure.get("message")
                if isinstance(self._last_failure, dict)
                else None
            ),
            "lastStateChangedAt": (
                current_device.last_connection_attempt.happened_at.isoformat()
                if current_device is not None and current_device.last_connection_attempt is not None
                else None
            ),
        }

    def _build_diagnostics_state(self) -> dict[str, Any]:
        provider = getattr(self, "_history_provider", None)
        builder = getattr(provider, "build_runtime_diagnostics", None)
        if callable(builder):
            result = builder()
            if isinstance(result, dict):
                return result
        return {
            "databasePath": None,
            "storageEngine": "sqlite",
            "logRetentionDays": 90,
            "activityEventCount": 0,
            "connectionAttemptCount": 0,
            "logRecordCount": 0,
            "lastExportPath": None,
            "lastExportAt": None,
            "lastSupportBundlePath": None,
            "lastSupportBundleAt": None,
            "recentErrors": [],
            "audioRouting": {
                "currentDeviceId": None,
                "remoteContainerId": None,
                "remoteAepConnected": None,
                "remoteAepPresent": None,
                "localRenderId": None,
                "localRenderName": None,
                "localRenderState": None,
                "audioFlowObserved": None,
                "audioFlowPeakMax": None,
                "validationPhase": None,
                "lastValidatedAt": None,
                "lastRecoverReason": None,
            },
        }

    def _load_connection_attempts(self, *, limit: int) -> list[dict[str, Any]]:
        provider = getattr(self, "_history_provider", None)
        loader = getattr(provider, "list_connection_attempts", None)
        if not callable(loader):
            return []
        result = loader(limit=limit)
        if not isinstance(result, list):
            return []
        return [entry for entry in result if isinstance(entry, dict)]

    def _load_device_history(self, *, limit: int) -> list[dict[str, Any]]:
        provider = getattr(self, "_history_provider", None)
        if provider is None:
            return []

        if callable(provider):
            result = provider(limit=limit)
        else:
            loader = getattr(provider, "list_device_history", None)
            if not callable(loader):
                return []
            result = loader(limit=limit)

        if not isinstance(result, list):
            return []
        return [entry for entry in result if isinstance(entry, dict)]

    def _serialize_device_history_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        saved_rule = entry.get("saved_rule")
        if not isinstance(saved_rule, dict):
            saved_rule = {}
        return {
            "deviceId": str(entry.get("device_id", "")),
            "name": str(entry.get("name", entry.get("device_id", ""))),
            "supportsAudioPlayback": bool(entry.get("supports_audio_playback", False)),
            "firstSeenAt": _serialize_history_timestamp(entry.get("first_seen_at")),
            "lastSeenAt": _serialize_history_timestamp(entry.get("last_seen_at")),
            "lastConnectionAt": _serialize_history_timestamp(entry.get("last_connection_at")),
            "lastConnectionState": _string_or_none(entry.get("last_connection_state")),
            "lastConnectionTrigger": _string_or_none(entry.get("last_connection_trigger")),
            "lastFailureReason": _string_or_none(entry.get("last_failure_reason")),
            "lastSuccessAt": _serialize_history_timestamp(entry.get("last_success_at")),
            "lastFailureAt": _serialize_history_timestamp(entry.get("last_failure_at")),
            "lastAbsentAt": _serialize_history_timestamp(entry.get("last_absent_at")),
            "lastPresentAt": _serialize_history_timestamp(entry.get("last_present_at")),
            "successCount": int(entry.get("success_count", 0) or 0),
            "failureCount": int(entry.get("failure_count", 0) or 0),
            "lastErrorCode": _string_or_none(entry.get("last_error_code")),
            "lastPresentReason": _string_or_none(entry.get("last_present_reason")),
            "lastAbsentReason": _string_or_none(entry.get("last_absent_reason")),
            "savedRule": {
                "isFavorite": bool(saved_rule.get("is_favorite", False)),
                "isIgnored": bool(saved_rule.get("is_ignored", False)),
                "autoConnectOnReappear": bool(saved_rule.get("auto_connect_on_reappear", False)),
                "priority": saved_rule.get("priority"),
            },
        }


def _serialize_history_timestamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _resolve_failure_message(
    *,
    state: str,
    failure_code: str | None,
    failure_message: str | None,
    language: str,
) -> str:
    if failure_message:
        return failure_message
    if failure_code == "connection.no_audio":
        return humanize_connection_failure("no_audio", language=language)
    return humanize_connection_failure(state, language=language)
