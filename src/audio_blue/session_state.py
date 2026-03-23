from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from inspect import Parameter, signature
from typing import Any, Protocol

from audio_blue.config import save_config
from audio_blue.localization import connection_failure_message, notification_copy
from audio_blue.rules_engine import RulesEngine


class RuntimeStorage(Protocol):
    def record_connection_attempt(self, **payload: Any) -> None: ...

    def upsert_device_cache(self, **payload: Any) -> None: ...


class SessionStateCoordinator:
    def __init__(
        self,
        *,
        service,
        app_state,
        autostart_manager,
        notification_service,
        storage: RuntimeStorage | None = None,
    ) -> None:
        self.service = service
        self.app_state = app_state
        self.autostart_manager = autostart_manager
        self.notification_service = notification_service
        self.storage = storage
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._startup_auto_connect_completed = False
        self._bind_service_callback()
        self._sync_from_service()

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    def snapshot(self) -> dict[str, Any]:
        self._sync_from_service()
        return self._normalize_snapshot(self.app_state.snapshot())

    def list_devices(self):
        self._sync_from_service()
        return list(getattr(self.service, "known_devices", {}).values())

    def refresh_devices(self) -> dict[str, Any]:
        previous_presence = {
            device_id: bool(getattr(device, "present_in_last_scan", True))
            for device_id, device in getattr(self.service, "known_devices", {}).items()
        }

        self.service.refresh_devices()
        self._sync_from_service()
        self._sync_device_cache()

        devices = list(getattr(self.service, "known_devices", {}).values())
        if not self._startup_auto_connect_completed:
            self._attempt_auto_connect(trigger="startup", devices=devices)
            self._startup_auto_connect_completed = True
        else:
            reappeared = [
                device
                for device in devices
                if getattr(device, "present_in_last_scan", True)
                and not previous_presence.get(device.device_id, False)
            ]
            if reappeared:
                self._attempt_auto_connect(trigger="reappear", devices=reappeared)

        self._sync_from_service()
        return self._publish_snapshot()

    def connect_device(self, device_id: str) -> dict[str, Any]:
        self._connect_service_device(device_id, trigger="manual")
        self._sync_from_service()
        return self._publish_snapshot()

    def disconnect_device(self, device_id: str) -> dict[str, Any]:
        self._disconnect_service_device(device_id, trigger="manual")
        self._sync_from_service()
        return self._publish_snapshot()

    def update_device_rule(self, device_id: str, rule_patch: dict[str, Any]) -> dict[str, Any]:
        self.app_state.update_device_rule(device_id, rule_patch)
        self._persist_config()
        return self._publish_snapshot()

    def reorder_device_priority(self, device_ids: list[str]) -> dict[str, Any]:
        self.app_state.reorder_device_priority(device_ids)
        self._persist_config()
        return self._publish_snapshot()

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        self.autostart_manager.set_enabled(enabled)
        self.app_state.config.startup.autostart = enabled
        self._persist_config()
        return self._publish_snapshot()

    def set_reconnect(self, enabled: bool) -> dict[str, Any]:
        self.app_state.config.reconnect = enabled
        self._persist_config()
        return self._publish_snapshot()

    def set_theme(self, mode: str) -> dict[str, Any]:
        self.app_state.config.ui.theme = mode
        self._persist_config()
        return self._publish_snapshot()

    def set_language(self, language: str) -> dict[str, Any]:
        setattr(self.app_state.config.ui, "language", language)
        self._persist_config()
        return self._publish_snapshot()

    def set_notification_policy(self, policy: str) -> dict[str, Any]:
        self.notification_service.update_policy(policy)
        self.app_state.config.notification.policy = policy
        self._persist_config()
        return self._publish_snapshot()

    def handle_service_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.app_state.handle_connector_event(payload)
        self._sync_from_service()
        self._sync_device_cache()
        self._record_connection_attempt(payload)
        self._publish_notification(payload)
        return self._publish_snapshot()

    def _sync_from_service(self) -> None:
        self.app_state.sync_devices(list(getattr(self.service, "known_devices", {}).values()))

    def _publish_snapshot(self) -> dict[str, Any]:
        snapshot = self._normalize_snapshot(self.app_state.snapshot())
        for callback in list(self._listeners):
            callback(snapshot)
        return snapshot

    def _bind_service_callback(self) -> None:
        existing_callback = getattr(self.service, "_state_callback", None)

        def composed_callback(payload: dict[str, Any]) -> None:
            if callable(existing_callback):
                existing_callback(payload)
            if isinstance(payload, dict):
                self.handle_service_event(payload)

        setattr(self.service, "_state_callback", composed_callback)

    def _normalize_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        settings = snapshot.setdefault("settings", {})
        startup_settings = settings.setdefault("startup", {})
        startup_settings.setdefault("reconnectOnNextStart", bool(self.app_state.config.reconnect))
        ui_settings = settings.setdefault("ui", {})
        ui_settings.setdefault("language", getattr(self.app_state.config.ui, "language", "system"))
        return snapshot

    def _attempt_auto_connect(self, *, trigger: str, devices: list[Any]) -> None:
        if trigger not in {"startup", "reappear"}:
            return

        candidates = RulesEngine(self.app_state.config).get_auto_connect_candidates(
            devices=devices,
            trigger=trigger,
        )
        for device in candidates:
            if getattr(device, "connection_state", "disconnected") == "connected":
                return

            try:
                self._connect_service_device(device.device_id, trigger=trigger)
            except Exception:
                self.handle_service_event(
                    {
                        "event": "device_connection_failed",
                        "device_id": device.device_id,
                        "state": "error",
                        "trigger": trigger,
                    }
                )
                continue

            known_device = getattr(self.service, "known_devices", {}).get(device.device_id)
            if device.device_id in getattr(self.service, "active_connections", {}):
                return
            if known_device is not None and getattr(known_device, "connection_state", None) == "connected":
                return

    def _connect_service_device(self, device_id: str, *, trigger: str) -> None:
        connect = getattr(self.service, "connect")
        try:
            connect(device_id, trigger=trigger)
        except TypeError:
            connect(device_id)

    def _disconnect_service_device(self, device_id: str, *, trigger: str) -> None:
        disconnect = getattr(self.service, "disconnect")
        try:
            disconnect(device_id, trigger=trigger)
        except TypeError:
            disconnect(device_id)

    def _persist_config(self) -> None:
        save_config(self.app_state.config)

    def _record_connection_attempt(self, payload: dict[str, Any]) -> None:
        event_name = payload.get("event")
        if event_name not in {"device_connected", "device_connection_failed"}:
            return
        device_id = payload.get("device_id")
        if not isinstance(device_id, str):
            return

        trigger = payload.get("trigger")
        trigger_name = trigger if isinstance(trigger, str) else "manual"
        succeeded = event_name == "device_connected"
        state = "connected" if succeeded else payload.get("state", "error")
        if not isinstance(state, str):
            state = "error"

        known_device = getattr(self.service, "known_devices", {}).get(device_id)
        device_name = getattr(known_device, "name", device_id)
        language = getattr(self.app_state.config.ui, "language", "system")
        failure_reason = None if succeeded else connection_failure_message(state, language=language)
        failure_code = None if succeeded else f"connection.{state}"

        self._invoke_storage_method(
            "record_connection_attempt",
            device_id=device_id,
            device_name=device_name,
            trigger=trigger_name,
            succeeded=succeeded,
            state=state,
            failure_reason=failure_reason,
            failure_code=failure_code,
            happened_at=datetime.now(UTC),
        )

        if succeeded:
            existing = [item for item in self.app_state.config.last_devices if item != device_id]
            self.app_state.config.last_devices = [device_id, *existing]
            self._persist_config()

    def _sync_device_cache(self) -> None:
        for device in getattr(self.service, "known_devices", {}).values():
            capabilities = getattr(device, "capabilities", None)
            self._invoke_storage_method(
                "upsert_device_cache",
                device_id=device.device_id,
                name=device.name,
                connection_state=device.connection_state,
                supports_audio_playback=bool(
                    getattr(capabilities, "supports_audio_playback", False)
                ),
                supports_microphone=bool(
                    getattr(capabilities, "supports_microphone", False)
                ),
                last_seen_at=device.last_seen_at,
            )

    def _publish_notification(self, payload: dict[str, Any]) -> None:
        event_name = payload.get("event")
        if event_name not in {"device_connected", "device_connection_failed"}:
            return
        device_id = payload.get("device_id")
        if not isinstance(device_id, str):
            return

        known_device = getattr(self.service, "known_devices", {}).get(device_id)
        device_name = getattr(known_device, "name", device_id)
        language = getattr(self.app_state.config.ui, "language", "system")
        if event_name == "device_connected":
            title, body = notification_copy(
                "connect_success",
                language=language,
                device_name=device_name,
            )
            self.notification_service.publish_success(title, body)
            return

        state = payload.get("state", "error")
        if not isinstance(state, str):
            state = "error"
        reason = connection_failure_message(state, language=language)
        title, body = notification_copy(
            "connect_failed",
            language=language,
            device_name=device_name,
            reason=reason,
        )
        self.notification_service.publish_failure(title, body)

    def _invoke_storage_method(self, method_name: str, **payload: Any) -> None:
        if self.storage is None:
            return

        method = getattr(self.storage, method_name, None)
        if not callable(method):
            return

        method_signature = signature(method)
        if any(parameter.kind == Parameter.VAR_KEYWORD for parameter in method_signature.parameters.values()):
            method(**payload)
            return

        allowed = {
            key: value
            for key, value in payload.items()
            if key in method_signature.parameters
        }
        method(**allowed)
