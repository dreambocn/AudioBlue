from __future__ import annotations

from typing import Protocol

import win32api
import win32event
import winerror


class InstanceCoordinator(Protocol):
    def try_acquire(self, name: str) -> bool: ...

    def signal_existing(self, name: str) -> None: ...

    def release(self, name: str) -> None: ...


class Win32InstanceCoordinator:
    def __init__(self) -> None:
        self._mutex_handles: dict[str, object] = {}

    def try_acquire(self, name: str) -> bool:
        handle = win32event.CreateMutex(None, False, f"Local\\{name}")
        already_exists = win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS
        self._mutex_handles[name] = handle
        return not already_exists

    def signal_existing(self, name: str) -> None:
        event_handle = win32event.CreateEvent(None, False, False, f"Local\\{name}.activate")
        win32event.SetEvent(event_handle)

    def release(self, name: str) -> None:
        handle = self._mutex_handles.pop(name, None)
        if handle is not None:
            win32api.CloseHandle(handle)


class SingleInstanceManager:
    def __init__(
        self,
        coordinator: InstanceCoordinator | None = None,
        name: str = "AudioBlue",
    ) -> None:
        self._coordinator = coordinator or Win32InstanceCoordinator()
        self._name = name
        self._held = False

    def acquire(self) -> bool:
        acquired = self._coordinator.try_acquire(self._name)
        self._held = acquired
        if not acquired:
            self._coordinator.signal_existing(self._name)
        return acquired

    def release(self) -> None:
        if self._held:
            self._coordinator.release(self._name)
            self._held = False


def try_acquire(name: str = "AudioBlue", coordinator: InstanceCoordinator | None = None) -> bool:
    return SingleInstanceManager(coordinator=coordinator, name=name).acquire()


def signal_existing_instance(
    name: str = "AudioBlue",
    coordinator: InstanceCoordinator | None = None,
) -> None:
    (coordinator or Win32InstanceCoordinator()).signal_existing(name)
