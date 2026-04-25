"""验证后端本地化词典对托盘与失败文案的映射。"""

import audio_blue.localization as localization
from audio_blue.localization import (
    connection_failure_message,
    notification_copy,
    resolve_language,
    tray_label,
    translate,
)


def test_resolve_language_prefers_explicit_supported_language():
    assert resolve_language("zh-CN", system_locale="en-US") == "zh-CN"
    assert resolve_language("en-US", system_locale="zh-CN") == "en-US"


def test_resolve_language_uses_system_locale_for_system_mode():
    assert resolve_language("system", system_locale="zh-HK") == "zh-CN"
    assert resolve_language("system", system_locale="en-GB") == "en-US"


def test_resolve_language_prefers_windows_locale_name_when_system_locale_missing(monkeypatch):
    # 未显式传入 system_locale 时，应优先读取 Windows locale name。
    monkeypatch.setattr(localization, "_get_windows_system_locale_name", lambda: "zh-CN")
    monkeypatch.setattr(localization, "_get_windows_ui_language_id", lambda: None)
    monkeypatch.setattr(localization.locale, "getlocale", lambda: ("en_US", "UTF-8"))

    assert resolve_language("system") == "zh-CN"


def test_resolve_language_uses_windows_ui_language_when_locale_name_missing(monkeypatch):
    # locale name 缺失后，应继续尝试 Windows UI 语言 ID。
    monkeypatch.setattr(localization, "_get_windows_system_locale_name", lambda: None)
    monkeypatch.setattr(localization, "_get_windows_ui_language_id", lambda: 2052)
    monkeypatch.setattr(localization.locale, "getlocale", lambda: ("en_US", "UTF-8"))

    assert resolve_language("system") == "zh-CN"


def test_resolve_language_falls_back_to_python_locale_when_windows_api_unavailable(monkeypatch):
    # Windows API 不可用时，仍要回退到 Python locale 保持稳定行为。
    monkeypatch.setattr(localization, "_get_windows_system_locale_name", lambda: None)
    monkeypatch.setattr(localization, "_get_windows_ui_language_id", lambda: None)
    monkeypatch.setattr(localization.locale, "getlocale", lambda: ("zh_TW", "UTF-8"))

    assert resolve_language("system") == "zh-CN"


def test_tray_labels_are_localized_for_both_languages():
    assert tray_label("refresh_devices", language="zh-CN") == "刷新设备"
    assert tray_label("open_control_center", language="en-US") == "Open Control Center"
    assert tray_label("connect_device", language="zh-CN", device_name="耳机") == "连接 耳机"


def test_connection_failure_messages_are_localized_by_state():
    assert connection_failure_message("timeout", language="zh-CN") == "连接超时，音频未能启动。"
    assert connection_failure_message("denied", language="en-US") == "Windows denied the audio connection request."
    assert connection_failure_message("failed", language="zh-CN") == "连接已建立，但系统未检测到稳定的音频会话。"
    assert connection_failure_message("no_audio", language="zh-CN") == "设备已连接，但未检测到有效音频输出，自动恢复后仍未成功。"
    assert connection_failure_message("stale", language="zh-CN") == "Windows 仍显示设备已连接，但 AudioBlue 已判定当前连接失活。"
    assert connection_failure_message("unknown", language="zh-CN") == "AudioBlue 无法连接到该设备。"


def test_notification_copy_supports_success_and_failure_messages():
    zh_success = notification_copy("connect_success", language="zh-CN", device_name="耳机")
    en_failure = notification_copy(
        "connect_failed",
        language="en-US",
        device_name="Headphones",
        reason="Timed out",
    )

    assert zh_success == ("已连接", "耳机 已连接。")
    assert en_failure == ("Connection failed", "Headphones failed to connect: Timed out.")


def test_translate_falls_back_to_english_for_unknown_key():
    assert translate("unknown.key", language="zh-CN") == "unknown.key"
