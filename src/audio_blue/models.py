from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DeviceSummary:
    device_id: str
    name: str
    connection_state: str = "disconnected"


@dataclass(slots=True)
class AppConfig:
    reconnect: bool = False
    last_devices: list[str] = field(default_factory=list)
