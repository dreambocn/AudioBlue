"""集中维护托盘与连接结果的后端文案。"""

from __future__ import annotations

import ctypes
import locale
from ctypes import wintypes
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
    "error.no_audio",
    "error.endpoint_not_ready",
    "error.stale",
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
        "error.no_audio": "The device connected, but AudioBlue still could not observe usable audio output after auto-recovery.",
        "error.endpoint_not_ready": "The connection opened, but Windows never exposed the playback endpoint in time.",
        "error.stale": "Windows still reports the device as connected, but AudioBlue has detected that the session is stale.",
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
        "error.no_audio": "设备已连接，但未检测到有效音频输出，自动恢复后仍未成功。",
        "error.endpoint_not_ready": "连接已建立，但系统未在预期时间内创建设备播放端点。",
        "error.stale": "Windows 仍显示设备已连接，但 AudioBlue 已判定当前连接失活。",
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
    "no_audio": "error.no_audio",
    "endpoint_not_ready": "error.endpoint_not_ready",
    "stale": "error.stale",
    "error": "error.error",
}


def _normalize_system_language(raw_language: str | int | None) -> LanguageMode:
    """把系统语言原始值收敛到中文或英文两种展示语言。"""
    if isinstance(raw_language, int):
        # LANGID 的低 10 位是主语言 ID，0x04 代表中文。
        if raw_language & 0x3FF == 0x04:
            return "zh-CN"
        return "en-US"

    normalized = str(raw_language or "").lower()
    if normalized.startswith("zh"):
        return "zh-CN"
    return "en-US"


def _get_windows_system_locale_name() -> str | None:
    """优先读取 Windows 系统 locale name，失败时返回 None。"""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_locale_name = kernel32.GetUserDefaultLocaleName
        get_locale_name.argtypes = [wintypes.LPWSTR, ctypes.c_int]
        get_locale_name.restype = ctypes.c_int
        buffer = ctypes.create_unicode_buffer(85)
        if get_locale_name(buffer, len(buffer)) > 0 and buffer.value:
            return buffer.value
    except Exception:
        return None
    return None


def _get_windows_ui_language_id() -> int | None:
    """当 locale name 不可用时，继续读取 Windows UI 语言 ID。"""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_ui_language = kernel32.GetUserDefaultUILanguage
        get_ui_language.restype = wintypes.LANGID
        language_id = int(get_ui_language())
        if language_id > 0:
            return language_id
    except Exception:
        return None
    return None


def _get_python_system_locale_name() -> str | None:
    """Windows API 不可用时，回退到 Python locale。"""
    try:
        resolved = locale.getlocale()
    except Exception:
        return None
    if not resolved:
        return None
    return resolved[0]


def resolve_language(
    language: LanguageMode | str,
    *,
    system_locale: str | None = None,
) -> LanguageMode:
    """把“跟随系统”之类的偏好解析成实际可用语言。"""
    if language in {"zh-CN", "en-US"}:
        return language

    if system_locale is not None:
        return _normalize_system_language(system_locale)

    windows_locale_name = _get_windows_system_locale_name()
    if windows_locale_name is not None:
        return _normalize_system_language(windows_locale_name)

    windows_ui_language_id = _get_windows_ui_language_id()
    if windows_ui_language_id is not None:
        return _normalize_system_language(windows_ui_language_id)

    return _normalize_system_language(_get_python_system_locale_name())


def translate(
    key: str,
    *,
    language: LanguageMode | str = "system",
    system_locale: str | None = None,
    **kwargs: object,
) -> str:
    """从语言词典中取文案，并执行简单变量替换。"""
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
    """把托盘动作名映射成当前语言下的菜单文案。"""
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
    """把连接失败状态统一转换为可直接展示的说明文案。"""
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
    """生成通知标题与正文，确保成功和失败场景走统一词典。"""
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
