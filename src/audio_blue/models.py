from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

AutoConnectTrigger = Literal["startup", "reappear"]
NotificationPolicy = Literal["silent", "failures", "all"]
ThemeMode = Literal["system", "light", "dark"]
LanguageMode = Literal["system", "zh-CN", "en-US"]


@dataclass(slots=True)
class DeviceCapabilities:
    supports_audio_playback: bool = True
    supports_microphone: bool = False


@dataclass(slots=True)
class ConnectionAttempt:
    trigger: str
    succeeded: bool
    state: str
    failure_reason: str | None = None
    failure_code: str | None = None
    happened_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class DeviceRule:
    is_favorite: bool = False
    is_ignored: bool = False
    priority: int | None = None
    auto_connect_on_startup: bool = False
    auto_connect_on_reappear: bool = False

    def matches_trigger(self, trigger: AutoConnectTrigger) -> bool:
        return (
            self.auto_connect_on_startup
            if trigger == "startup"
            else self.auto_connect_on_reappear
        )


@dataclass(slots=True)
class NotificationPreferences:
    policy: NotificationPolicy = "failures"


@dataclass(slots=True)
class StartupPreferences:
    autostart: bool = False
    run_in_background: bool = False
    launch_delay_seconds: int = 3


@dataclass(slots=True)
class UiPreferences:
    theme: ThemeMode = "system"
    high_contrast: bool = False
    language: LanguageMode = "system"


@dataclass(slots=True)
class DeviceSummary:
    device_id: str
    name: str
    connection_state: str = "disconnected"
    capabilities: DeviceCapabilities = field(default_factory=DeviceCapabilities)
    last_seen_at: datetime | None = None
    last_connection_attempt: ConnectionAttempt | None = None


@dataclass(slots=True)
class AppConfig:
    reconnect: bool = False
    last_devices: list[str] = field(default_factory=list)
    device_rules: dict[str, DeviceRule] = field(default_factory=dict)
    notification: NotificationPreferences = field(default_factory=NotificationPreferences)
    startup: StartupPreferences = field(default_factory=StartupPreferences)
    ui: UiPreferences = field(default_factory=UiPreferences)
