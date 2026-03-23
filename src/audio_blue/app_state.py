from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from audio_blue.localization import connection_failure_message
from audio_blue.models import AppConfig, ConnectionAttempt, DeviceRule, DeviceSummary
from audio_blue.rules_engine import RulesEngine


def humanize_connection_failure(state: str, *, language: str = "system") -> str:
    return connection_failure_message(state, language=language)


class AppStateStore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
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
        return {
            "devices": [self._serialize_device(device) for device in self._devices.values()],
            "deviceRules": {
                device_id: self._serialize_rule(rule)
                for device_id, rule in self.config.device_rules.items()
            },
            "lastFailure": self._last_failure,
            "lastTrigger": self._last_trigger,
            "settings": {
                "notification": asdict(self.config.notification),
                "startup": asdict(self.config.startup),
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
