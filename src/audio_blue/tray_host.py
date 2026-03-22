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
from audio_blue.models import AppConfig, DeviceSummary

WMAPP_NOTIFYCALLBACK = win32con.WM_APP + 1


@dataclass(slots=True)
class MenuEntry:
    action: str
    label: str
    checked: bool = False
    enabled: bool = True
    device_id: str | None = None


def build_menu_entries(devices: list[DeviceSummary], reconnect_enabled: bool) -> list[MenuEntry]:
    entries = [
        MenuEntry(action="refresh_devices", label="Refresh Devices"),
        MenuEntry(action="toggle_reconnect", label="Reconnect On Next Start", checked=reconnect_enabled),
        MenuEntry(action="open_control_center", label="Open Control Center"),
    ]

    for device in devices:
        if device.connection_state == "connected":
            entries.append(
                MenuEntry(
                    action="disconnect_device",
                    label=f"Disconnect {device.name}",
                    device_id=device.device_id,
                )
            )
        else:
            entries.append(
                MenuEntry(
                    action="connect_device",
                    label=f"Connect {device.name}",
                    device_id=device.device_id,
                )
            )

    entries.extend(
        [
            MenuEntry(action="open_bluetooth_settings", label="Bluetooth Settings"),
            MenuEntry(action="exit", label="Exit"),
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
    ) -> None:
        self._service = service
        self._config = config
        self._logger = logger
        self._background = background
        self._show_quick_panel = show_quick_panel or self._show_menu
        self._show_main_window = show_main_window or (lambda: None)
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
            self._service.refresh_devices()
        except Exception:
            self._logger.exception("Failed to refresh devices.")

    def _show_menu(self) -> None:
        menu = win32gui.CreatePopupMenu()
        self._command_map.clear()
        self._next_command_id = 1000

        for entry in build_menu_entries(list(self._service.known_devices.values()), self._config.reconnect):
            menu_flags = win32con.MF_STRING
            if not entry.enabled:
                menu_flags |= win32con.MF_GRAYED
            if entry.checked:
                menu_flags |= win32con.MF_CHECKED

            command_id = self._next_command_id
            self._next_command_id += 1
            self._command_map[command_id] = entry
            win32gui.AppendMenu(menu, menu_flags, command_id, entry.label)

        cursor_x, cursor_y = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self._hwnd)
        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, cursor_x, cursor_y, 0, self._hwnd, None)

    def _on_notify(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if lparam == win32con.WM_LBUTTONUP:
            self._show_quick_panel()
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
            self._config.reconnect = not self._config.reconnect
        elif entry.action == "open_control_center":
            self._show_main_window()
        elif entry.action == "connect_device" and entry.device_id:
            self._service.connect(entry.device_id)
        elif entry.action == "disconnect_device" and entry.device_id:
            self._service.disconnect(entry.device_id)
        elif entry.action == "open_bluetooth_settings":
            os.startfile("ms-settings:bluetooth")
        elif entry.action == "exit":
            win32gui.DestroyWindow(hwnd)

        return 0

    def _on_destroy(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if self._notify_id is not None:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, self._notify_id)
        save_config(build_exit_config(self._config, self._service))
        self._service.shutdown()
        win32gui.PostQuitMessage(0)
        return 0
