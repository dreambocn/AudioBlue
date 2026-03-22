from __future__ import annotations

from dataclasses import replace

from audio_blue.models import AppConfig, AutoConnectTrigger, DeviceRule, DeviceSummary


class RulesEngine:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def get_auto_connect_candidates(
        self,
        devices: list[DeviceSummary],
        trigger: AutoConnectTrigger,
    ) -> list[DeviceSummary]:
        device_map = {
            device.device_id: self._apply_rule_defaults(
                device=device,
                rule=self._config.device_rules.get(device.device_id),
            )
            for device in devices
        }

        matched = [
            device
            for device in device_map.values()
            if self._should_include_device(device=device, trigger=trigger)
        ]
        matched.sort(key=self._candidate_sort_key)

        fallback = []
        if self._config.reconnect:
            for device_id in self._config.last_devices:
                device = device_map.get(device_id)
                if device is None or device in matched or not device.capabilities.supports_audio_playback:
                    continue
                rule = self._config.device_rules.get(device.device_id, DeviceRule())
                if rule.is_ignored:
                    continue
                fallback.append(device)

        return matched + fallback

    def _apply_rule_defaults(
        self,
        device: DeviceSummary,
        rule: DeviceRule | None,
    ) -> DeviceSummary:
        if rule is None:
            return device
        return replace(device)

    def _should_include_device(
        self,
        device: DeviceSummary,
        trigger: AutoConnectTrigger,
    ) -> bool:
        rule = self._config.device_rules.get(device.device_id, DeviceRule())
        return (
            device.capabilities.supports_audio_playback
            and not rule.is_ignored
            and rule.matches_trigger(trigger)
        )

    def _candidate_sort_key(self, device: DeviceSummary) -> tuple[int, int, str]:
        rule = self._config.device_rules.get(device.device_id, DeviceRule())
        favorite_rank = 0 if rule.is_favorite else 1
        priority_rank = rule.priority if rule.priority is not None else 10_000
        return (favorite_rank, priority_rank, device.name.casefold())
