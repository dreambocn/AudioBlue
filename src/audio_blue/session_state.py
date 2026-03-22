from __future__ import annotations

from collections.abc import Callable
from typing import Any


class SessionStateCoordinator:
    def __init__(
        self,
        *,
        service,
        app_state,
        autostart_manager,
        notification_service,
    ) -> None:
        self.service = service
        self.app_state = app_state
        self.autostart_manager = autostart_manager
        self.notification_service = notification_service
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
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
        self.service.refresh_devices()
        self._sync_from_service()
        return self._publish_snapshot()

    def connect_device(self, device_id: str) -> dict[str, Any]:
        self.service.connect(device_id)
        self._sync_from_service()
        return self._publish_snapshot()

    def disconnect_device(self, device_id: str) -> dict[str, Any]:
        self.service.disconnect(device_id)
        self._sync_from_service()
        return self._publish_snapshot()

    def update_device_rule(self, device_id: str, rule_patch: dict[str, Any]) -> dict[str, Any]:
        self.app_state.update_device_rule(device_id, rule_patch)
        return self._publish_snapshot()

    def reorder_device_priority(self, device_ids: list[str]) -> dict[str, Any]:
        self.app_state.reorder_device_priority(device_ids)
        return self._publish_snapshot()

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        self.autostart_manager.set_enabled(enabled)
        self.app_state.config.startup.autostart = enabled
        return self._publish_snapshot()

    def set_theme(self, mode: str) -> dict[str, Any]:
        self.app_state.config.ui.theme = mode
        return self._publish_snapshot()

    def set_language(self, language: str) -> dict[str, Any]:
        setattr(self.app_state.config.ui, "language", language)
        return self._publish_snapshot()

    def set_notification_policy(self, policy: str) -> dict[str, Any]:
        self.notification_service.update_policy(policy)
        self.app_state.config.notification.policy = policy
        return self._publish_snapshot()

    def handle_service_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.app_state.handle_connector_event(payload)
        self._sync_from_service()
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
        ui_settings = settings.setdefault("ui", {})
        ui_settings.setdefault("language", getattr(self.app_state.config.ui, "language", "system"))
        return snapshot
