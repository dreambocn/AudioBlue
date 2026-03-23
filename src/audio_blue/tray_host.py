from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Callable

import win32api
import win32con
import win32gui

from audio_blue.config import save_config
from audio_blue.connector_service import ConnectorService
from audio_blue.localization import tray_label
from audio_blue.models import AppConfig, DeviceSummary

WMAPP_NOTIFYCALLBACK = win32con.WM_APP + 1


@dataclass(slots=True)
class MenuEntry:
    action: str
    label: str
    checked: bool = False
    enabled: bool = True
    device_id: str | None = None
    language: str | None = None
    children: list["MenuEntry"] | None = None


def build_menu_entries(
    devices: list[DeviceSummary],
    reconnect_enabled: bool,
    *,
    language: str = "system",
    selected_language: str | None = None,
) -> list[MenuEntry]:
    selected = selected_language or language
    entries = [
        MenuEntry(action="refresh_devices", label=tray_label("refresh_devices", language=language)),
        MenuEntry(
            action="toggle_reconnect",
            label=tray_label("toggle_reconnect", language=language),
            checked=reconnect_enabled,
        ),
        MenuEntry(action="open_control_center", label=tray_label("open_control_center", language=language)),
        MenuEntry(
            action="set_language",
            label=tray_label("language", language=language),
            children=[
                MenuEntry(
                    action="set_language",
                    label=tray_label("language_system", language=language),
                    checked=selected == "system",
                    language="system",
                ),
                MenuEntry(
                    action="set_language",
                    label=tray_label("language_zh-CN", language=language),
                    checked=selected == "zh-CN",
                    language="zh-CN",
                ),
                MenuEntry(
                    action="set_language",
                    label=tray_label("language_en-US", language=language),
                    checked=selected == "en-US",
                    language="en-US",
                ),
            ],
        ),
    ]

    for device in devices:
        if device.connection_state == "connected":
            entries.append(
                MenuEntry(
                    action="disconnect_device",
                    label=tray_label("disconnect_device", language=language, device_name=device.name),
                    device_id=device.device_id,
                )
            )
        else:
            entries.append(
                MenuEntry(
                    action="connect_device",
                    label=tray_label("connect_device", language=language, device_name=device.name),
                    device_id=device.device_id,
                )
            )

    entries.extend(
        [
            MenuEntry(action="open_bluetooth_settings", label=tray_label("open_bluetooth_settings", language=language)),
            MenuEntry(action="exit", label=tray_label("exit", language=language)),
        ]
    )
    return entries


def build_exit_config(config: AppConfig, service: ConnectorService) -> AppConfig:
    return replace(
        config,
        last_devices=list(service.active_connections),
    )


class TrayHost:
    def __init__(
        self,
        service: ConnectorService,
        config: AppConfig,
        logger: logging.Logger,
        background: bool = False,
        show_quick_panel: Callable[[], None] | None = None,
        show_main_window: Callable[[], None] | None = None,
        shutdown_ui: Callable[[], None] | None = None,
        session_state=None,
    ) -> None:
        self._service = service
        self._config = config
        self._logger = logger
        self._background = background
        self._session_state = session_state
        self._show_quick_panel = show_quick_panel or self._show_menu
        self._show_main_window = show_main_window or (lambda: None)
        self._shutdown_ui = shutdown_ui or (lambda: None)
        self._command_map: dict[int, MenuEntry] = {}
        self._next_command_id = 1000
        self._hwnd: int | None = None
        self._class_name = "AudioBlueTrayHost"
        self._notify_id = None

    def run(self) -> None:
        window_class = win32gui.WNDCLASS()
        window_class.hInstance = win32api.GetModuleHandle(None)
        window_class.lpszClassName = self._class_name
        window_class.lpfnWndProc = {
            win32con.WM_COMMAND: self._on_command,
            win32con.WM_DESTROY: self._on_destroy,
            WMAPP_NOTIFYCALLBACK: self._on_notify,
        }

        atom = win32gui.RegisterClass(window_class)
        self._hwnd = win32gui.CreateWindow(
            atom,
            self._class_name,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            window_class.hInstance,
            None,
        )

        icon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        self._notify_id = (
            self._hwnd,
            0,
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            WMAPP_NOTIFYCALLBACK,
            icon,
            "AudioBlue",
        )
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, self._notify_id)

        self._refresh_devices()
        if not self._background:
            self._show_main_window()
        win32gui.PumpMessages()

    def _refresh_devices(self) -> None:
        try:
            if self._session_state is not None:
                self._session_state.refresh_devices()
            else:
                self._service.refresh_devices()
        except Exception:
            self._logger.exception("Failed to refresh devices.")

    def _show_menu(self) -> None:
        if self._hwnd is None:
            return

        menu = win32gui.CreatePopupMenu()
        self._command_map.clear()
        self._next_command_id = 1000

        devices = (
            self._session_state.list_devices()
            if self._session_state is not None
            else list(self._service.known_devices.values())
        )
        reconnect_enabled, selected_language = self._resolve_menu_preferences()
        for entry in build_menu_entries(
            devices,
            reconnect_enabled,
            language=selected_language,
            selected_language=selected_language,
        ):
            self._append_menu_entry(menu, entry)

        cursor_x, cursor_y = win32gui.GetCursorPos()
        try:
            win32gui.SetForegroundWindow(self._hwnd)
        except Exception:
            self._logger.debug("Failed to foreground tray host before opening menu.", exc_info=True)
        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, cursor_x, cursor_y, 0, self._hwnd, None)

    def _on_notify(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if lparam == win32con.WM_LBUTTONUP:
            self._show_main_window()
        elif lparam in (win32con.WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
            self._show_menu()
        return 0

    def _on_command(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        command_id = win32api.LOWORD(wparam)
        entry = self._command_map.get(command_id)
        if entry is None:
            return 0

        if entry.action == "refresh_devices":
            self._refresh_devices()
        elif entry.action == "toggle_reconnect":
            reconnect_enabled, _ = self._resolve_menu_preferences()
            next_enabled = not reconnect_enabled
            if self._session_state is not None and hasattr(self._session_state, "set_reconnect"):
                self._session_state.set_reconnect(next_enabled)
            else:
                self._config.reconnect = next_enabled
        elif entry.action == "open_control_center":
            self._show_main_window()
        elif entry.action == "connect_device" and entry.device_id:
            if self._session_state is not None:
                self._session_state.connect_device(entry.device_id)
            else:
                self._service.connect(entry.device_id)
        elif entry.action == "disconnect_device" and entry.device_id:
            if self._session_state is not None:
                self._session_state.disconnect_device(entry.device_id)
            else:
                self._service.disconnect(entry.device_id)
        elif entry.action == "set_language" and isinstance(entry.language, str):
            if self._session_state is not None and hasattr(self._session_state, "set_language"):
                self._session_state.set_language(entry.language)
            else:
                self._config.ui.language = entry.language
        elif entry.action == "open_bluetooth_settings":
            os.startfile("ms-settings:bluetooth")
        elif entry.action == "exit":
            win32gui.DestroyWindow(hwnd)

        return 0

    def _append_menu_entry(self, menu, entry: MenuEntry) -> None:
        menu_flags = win32con.MF_STRING
        if not entry.enabled:
            menu_flags |= win32con.MF_GRAYED
        if entry.checked:
            menu_flags |= win32con.MF_CHECKED

        if entry.children:
            submenu = win32gui.CreatePopupMenu()
            for child in entry.children:
                self._append_menu_entry(submenu, child)
            win32gui.AppendMenu(menu, menu_flags | win32con.MF_POPUP, submenu, entry.label)
            return

        command_id = self._next_command_id
        self._next_command_id += 1
        self._command_map[command_id] = entry
        win32gui.AppendMenu(menu, menu_flags, command_id, entry.label)

    def _resolve_menu_preferences(self) -> tuple[bool, str]:
        reconnect_enabled = bool(getattr(self._config, "reconnect", False))
        language = str(getattr(self._config.ui, "language", "system"))
        if self._session_state is None or not hasattr(self._session_state, "snapshot"):
            return reconnect_enabled, language

        try:
            snapshot = self._session_state.snapshot()
        except Exception:
            self._logger.debug("Failed to read session state snapshot for tray menu.", exc_info=True)
            return reconnect_enabled, language

        settings = snapshot.get("settings", {}) if isinstance(snapshot, dict) else {}
        startup = settings.get("startup", {}) if isinstance(settings, dict) else {}
        ui = settings.get("ui", {}) if isinstance(settings, dict) else {}
        reconnect_from_snapshot = startup.get("reconnectOnNextStart")
        language_from_snapshot = ui.get("language")

        if isinstance(reconnect_from_snapshot, bool):
            reconnect_enabled = reconnect_from_snapshot
        if isinstance(language_from_snapshot, str):
            language = language_from_snapshot
        return reconnect_enabled, language

    def _on_destroy(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if self._notify_id is not None:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, self._notify_id)
        self._shutdown_ui()
        save_config(build_exit_config(self._config, self._service))
        self._service.shutdown()
        win32gui.PostQuitMessage(0)
        return 0
