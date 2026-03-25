from __future__ import annotations

import locale
from typing import Literal

from audio_blue.models import LanguageMode

MessageKey = Literal[
    "tray.refresh_devices",
    "tray.reconnect_on_next_start",
    "tray.open_control_center",
    "tray.language",
    "tray.language.system",
    "tray.language.zh-CN",
    "tray.language.en-US",
    "tray.connect_device",
    "tray.disconnect_device",
    "tray.open_bluetooth_settings",
    "tray.exit",
    "error.timeout",
    "error.denied",
    "error.failed",
    "error.error",
    "notification.connected_title",
    "notification.connected_body",
    "notification.failed_title",
    "notification.failed_body",
]

_MESSAGES: dict[LanguageMode, dict[MessageKey, str]] = {
    "en-US": {
        "tray.refresh_devices": "Refresh Devices",
        "tray.reconnect_on_next_start": "Reconnect On Next Start",
        "tray.open_control_center": "Open Control Center",
        "tray.language": "Language",
        "tray.language.system": "Follow System",
        "tray.language.zh-CN": "Chinese",
        "tray.language.en-US": "English",
        "tray.connect_device": "Connect {device_name}",
        "tray.disconnect_device": "Disconnect {device_name}",
        "tray.open_bluetooth_settings": "Bluetooth Settings",
        "tray.exit": "Exit",
        "error.timeout": "Connection timed out before audio could start.",
        "error.denied": "Windows denied the audio connection request.",
        "error.failed": "The connection opened, but Windows never exposed a stable audio session.",
        "error.error": "AudioBlue could not connect to the device.",
        "notification.connected_title": "Connected",
        "notification.connected_body": "{device_name} connected.",
        "notification.failed_title": "Connection failed",
        "notification.failed_body": "{device_name} failed to connect: {reason}.",
    },
    "zh-CN": {
        "tray.refresh_devices": "刷新设备",
        "tray.reconnect_on_next_start": "下次启动时自动重连",
        "tray.open_control_center": "打开控制中心",
        "tray.language": "语言",
        "tray.language.system": "跟随系统",
        "tray.language.zh-CN": "中文",
        "tray.language.en-US": "英文",
        "tray.connect_device": "连接 {device_name}",
        "tray.disconnect_device": "断开 {device_name}",
        "tray.open_bluetooth_settings": "蓝牙设置",
        "tray.exit": "退出",
        "error.timeout": "连接超时，音频未能启动。",
        "error.denied": "Windows 拒绝了音频连接请求。",
        "error.failed": "连接已建立，但系统未检测到稳定的音频会话。",
        "error.error": "AudioBlue 无法连接到该设备。",
        "notification.connected_title": "已连接",
        "notification.connected_body": "{device_name} 已连接。",
        "notification.failed_title": "连接失败",
        "notification.failed_body": "{device_name} 连接失败：{reason}。",
    },
    "system": {},
}

_FAILURE_KEY_BY_STATE: dict[str, MessageKey] = {
    "timeout": "error.timeout",
    "denied": "error.denied",
    "failed": "error.failed",
    "error": "error.error",
}


def resolve_language(
    language: LanguageMode | str,
    *,
    system_locale: str | None = None,
) -> LanguageMode:
    if language in {"zh-CN", "en-US"}:
        return language

    normalized_locale = (system_locale or locale.getlocale()[0] or "").lower()
    if normalized_locale.startswith("zh"):
        return "zh-CN"
    return "en-US"


def translate(
    key: str,
    *,
    language: LanguageMode | str = "system",
    system_locale: str | None = None,
    **kwargs: object,
) -> str:
    resolved = resolve_language(language, system_locale=system_locale)
    template = _MESSAGES.get(resolved, {}).get(key) or _MESSAGES["en-US"].get(key) or key
    return template.format(**kwargs)


def tray_label(
    action: str,
    *,
    language: LanguageMode | str = "system",
    system_locale: str | None = None,
    device_name: str = "",
) -> str:
    action_to_key: dict[str, MessageKey] = {
        "refresh_devices": "tray.refresh_devices",
        "toggle_reconnect": "tray.reconnect_on_next_start",
        "open_control_center": "tray.open_control_center",
        "language": "tray.language",
        "language_system": "tray.language.system",
        "language_zh-CN": "tray.language.zh-CN",
        "language_en-US": "tray.language.en-US",
        "connect_device": "tray.connect_device",
        "disconnect_device": "tray.disconnect_device",
        "open_bluetooth_settings": "tray.open_bluetooth_settings",
        "exit": "tray.exit",
    }
    key = action_to_key.get(action, "tray.open_control_center")
    return translate(
        key,
        language=language,
        system_locale=system_locale,
        device_name=device_name,
    )


def connection_failure_message(
    state: str,
    *,
    language: LanguageMode | str = "system",
    system_locale: str | None = None,
) -> str:
    key = _FAILURE_KEY_BY_STATE.get(state, "error.error")
    return translate(key, language=language, system_locale=system_locale)


def notification_copy(
    kind: Literal["connect_success", "connect_failed"],
    *,
    language: LanguageMode | str = "system",
    system_locale: str | None = None,
    device_name: str,
    reason: str | None = None,
) -> tuple[str, str]:
    if kind == "connect_success":
        return (
            translate("notification.connected_title", language=language, system_locale=system_locale),
            translate(
                "notification.connected_body",
                language=language,
                system_locale=system_locale,
                device_name=device_name,
            ),
        )
    return (
        translate("notification.failed_title", language=language, system_locale=system_locale),
        translate(
            "notification.failed_body",
            language=language,
            system_locale=system_locale,
            device_name=device_name,
            reason=reason or "unknown reason",
        ),
    )
