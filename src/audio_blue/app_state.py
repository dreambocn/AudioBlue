from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from typing import Any

from audio_blue.localization import connection_failure_message
from audio_blue.models import AppConfig, ConnectionAttempt, DeviceRule, DeviceSummary
from audio_blue.rules_engine import RulesEngine


def humanize_connection_failure(state: str, *, language: str = "system") -> str:
    return connection_failure_message(state, language=language)


class AppStateStore:
    def __init__(self, config: AppConfig, history_provider: Any | None = None) -> None:
        self.config = config
        self._history_provider = history_provider
        self._devices: dict[str, DeviceSummary] = {}
        self._last_failure: dict[str, str] | None = None
        self._last_trigger: str | None = None

    def sync_devices(self, devices: list[DeviceSummary]) -> None:
        self._devices = {device.device_id: device for device in devices}

    def handle_connector_event(self, payload: dict[str, Any]) -> None:
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
                self._apply_device_state(device_id=device_id, state=state, trigger=trigger_name)
        elif event_name == "device_connection_failed":
            state = payload.get("state", "error")
            if not isinstance(state, str):
                state = "error"
            self._apply_device_state(device_id=device_id, state=state, trigger=trigger_name)
            language = getattr(self.config.ui, "language", "system")
            self._last_failure = {
                "deviceId": device_id,
                "state": state,
                "code": f"connection.{state}",
                "message": humanize_connection_failure(state, language=language),
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
        rules_engine = RulesEngine(self.config)
        auto_connect_candidates = rules_engine.get_auto_connect_candidates(
            devices=list(self._devices.values()),
            trigger="startup",
        )
        startup_settings = asdict(self.config.startup)
        startup_settings["reconnectOnNextStart"] = self.config.reconnect
        return {
            "devices": [self._serialize_device(device) for device in self._devices.values()],
            "deviceHistory": self._serialize_device_history(),
            "deviceRules": {
                device_id: self._serialize_rule(rule)
                for device_id, rule in self.config.device_rules.items()
            },
            "lastFailure": self._last_failure,
            "lastTrigger": self._last_trigger,
            "settings": {
                "notification": asdict(self.config.notification),
                "startup": startup_settings,
                "ui": asdict(self.config.ui),
            },
            "autoConnectCandidates": [device.device_id for device in auto_connect_candidates],
        }

    def _apply_device_state(self, device_id: str, state: str, trigger: str) -> None:
        device = self._devices.get(device_id)
        if device is None:
            return

        attempt = ConnectionAttempt(
            trigger=trigger,
            succeeded=state == "connected",
            state=state,
            failure_reason=(
                None
                if state == "connected"
                else humanize_connection_failure(state, language=getattr(self.config.ui, "language", "system"))
            ),
            failure_code=None if state == "connected" else f"connection.{state}",
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
        visible_device_ids = {
            device.device_id
            for device in self._devices.values()
            if device.connection_state == "connected" or device.capabilities.supports_audio_playback
        }
        return [
            self._serialize_device_history_entry(entry)
            for entry in raw_entries
            if str(entry.get("device_id", "")) not in visible_device_ids
        ]

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
            "lastSeenAt": _serialize_history_timestamp(entry.get("last_seen_at")),
            "lastConnectionAt": _serialize_history_timestamp(entry.get("last_connection_at")),
            "lastConnectionState": _string_or_none(entry.get("last_connection_state")),
            "lastConnectionTrigger": _string_or_none(entry.get("last_connection_trigger")),
            "lastFailureReason": _string_or_none(entry.get("last_failure_reason")),
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
