"""定义 AudioBlue 后端共享的数据模型。"""

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
    """描述设备是否具备音频播放与麦克风能力。"""

    supports_audio_playback: bool = True
    supports_microphone: bool = False


@dataclass(slots=True)
class ConnectionAttempt:
    """记录一次连接尝试的触发来源、结果与时间。"""

    trigger: str
    succeeded: bool
    state: str
    failure_reason: str | None = None
    failure_code: str | None = None
    happened_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class DeviceRule:
    """保存某个设备的收藏、忽略与自动连接规则。"""

    is_favorite: bool = False
    is_ignored: bool = False
    priority: int | None = None
    auto_connect_on_startup: bool = False
    auto_connect_on_reappear: bool = False

    def matches_trigger(self, trigger: AutoConnectTrigger) -> bool:
        """判断当前规则是否会在指定触发场景下生效。"""
        return (
            self.auto_connect_on_startup
            if trigger == "startup"
            else self.auto_connect_on_reappear
        )


@dataclass(slots=True)
class NotificationPreferences:
    """通知策略配置。"""

    policy: NotificationPolicy = "failures"


@dataclass(slots=True)
class StartupPreferences:
    """启动行为配置。"""

    autostart: bool = False
    run_in_background: bool = False
    launch_delay_seconds: int = 3


@dataclass(slots=True)
class UiPreferences:
    """界面显示相关配置。"""

    theme: ThemeMode = "system"
    high_contrast: bool = False
    language: LanguageMode = "system"


@dataclass(slots=True)
class DeviceSummary:
    """前后端共享的设备摘要模型。"""

    device_id: str
    name: str
    connection_state: str = "disconnected"
    capabilities: DeviceCapabilities = field(default_factory=DeviceCapabilities)
    present_in_last_scan: bool = True
    last_seen_at: datetime | None = None
    last_connection_attempt: ConnectionAttempt | None = None


@dataclass(slots=True)
class AppConfig:
    """应用配置根对象，聚合各类偏好与历史状态。"""

    reconnect: bool = False
    last_devices: list[str] = field(default_factory=list)
    device_rules: dict[str, DeviceRule] = field(default_factory=dict)
    notification: NotificationPreferences = field(default_factory=NotificationPreferences)
    startup: StartupPreferences = field(default_factory=StartupPreferences)
    ui: UiPreferences = field(default_factory=UiPreferences)
