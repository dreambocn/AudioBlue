"""根据设备规则筛选自动连接候选集。"""

from __future__ import annotations

from dataclasses import replace

from audio_blue.models import AppConfig, AutoConnectTrigger, DeviceRule, DeviceSummary


class RulesEngine:
    """封装启动重连与设备再次出现两类自动连接规则。"""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def get_auto_connect_candidates(
        self,
        devices: list[DeviceSummary],
        trigger: AutoConnectTrigger,
    ) -> list[DeviceSummary]:
        """返回当前触发场景下应尝试自动连接的设备列表。"""
        device_map = {
            device.device_id: self._apply_rule_defaults(
                device=device,
                rule=self._config.device_rules.get(device.device_id),
            )
            for device in devices
        }

        if trigger == "startup":
            return self._startup_candidates(device_map)

        # 再次出现场景直接从当前扫描结果中过滤，再按收藏和优先级排序。
        matched = [device for device in device_map.values() if self._should_include_reappear(device)]
        matched.sort(key=self._candidate_sort_key)
        return matched

    def _startup_candidates(self, device_map: dict[str, DeviceSummary]) -> list[DeviceSummary]:
        """按上次成功设备顺序恢复启动重连候选。"""
        if not self._config.reconnect:
            return []

        candidates: list[DeviceSummary] = []
        seen_ids: set[str] = set()
        for device_id in self._config.last_devices:
            if device_id in seen_ids:
                continue
            seen_ids.add(device_id)

            device = device_map.get(device_id)
            if device is None:
                continue
            if not device.capabilities.supports_audio_playback:
                continue
            if not getattr(device, "present_in_last_scan", True):
                continue

            rule = self._config.device_rules.get(device.device_id, DeviceRule())
            if rule.is_ignored:
                continue
            candidates.append(device)

        candidates.sort(key=self._candidate_sort_key)
        return candidates

    def _apply_rule_defaults(
        self,
        device: DeviceSummary,
        rule: DeviceRule | None,
    ) -> DeviceSummary:
        if rule is None:
            return device
        return replace(device)

    def _should_include_reappear(self, device: DeviceSummary) -> bool:
        """判断设备再次出现时是否需要自动连接。"""
        rule = self._config.device_rules.get(device.device_id, DeviceRule())
        return (
            device.capabilities.supports_audio_playback
            and not rule.is_ignored
            and rule.auto_connect_on_reappear
        )

    def _candidate_sort_key(self, device: DeviceSummary) -> tuple[int, int, str]:
        """收藏设备优先，其次使用显式优先级，最后按名称稳定排序。"""
        rule = self._config.device_rules.get(device.device_id, DeviceRule())
        favorite_rank = 0 if rule.is_favorite else 1
        priority_rank = rule.priority if rule.priority is not None else 10_000
        return (favorite_rank, priority_rank, device.name.casefold())
