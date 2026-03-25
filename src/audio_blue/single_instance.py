from __future__ import annotations

from typing import Protocol

import win32api
import win32event
import winerror


class InstanceCoordinator(Protocol):
    """抽象单实例协调能力，方便在测试中模拟互斥行为。"""

    def try_acquire(self, name: str) -> bool: ...

    def signal_existing(self, name: str) -> None: ...

    def release(self, name: str) -> None: ...


class Win32InstanceCoordinator:
    """使用 Win32 互斥体和事件实现单实例约束。"""

    def __init__(self) -> None:
        self._mutex_handles: dict[str, object] = {}

    def try_acquire(self, name: str) -> bool:
        # 互斥体负责“是否已有实例”，激活事件负责唤醒现有窗口，两者职责分离。
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
    """面向上层的单实例管理器，负责持有与释放当前实例锁。"""

    def __init__(
        self,
        coordinator: InstanceCoordinator | None = None,
        name: str = "AudioBlue",
    ) -> None:
        self._coordinator = coordinator or Win32InstanceCoordinator()
        self._name = name
        self._held = False

    def acquire(self) -> bool:
        """尝试获取实例锁；若失败则通知现有实例激活自身。"""
        acquired = self._coordinator.try_acquire(self._name)
        self._held = acquired
        if not acquired:
            self._coordinator.signal_existing(self._name)
        return acquired

    def release(self) -> None:
        if self._held:
            # 仅在持有句柄时关闭，避免重复释放导致 Win32 报错。
            self._coordinator.release(self._name)
            self._held = False


def try_acquire(name: str = "AudioBlue", coordinator: InstanceCoordinator | None = None) -> bool:
    """提供给启动入口使用的便捷单实例检查函数。"""
    return SingleInstanceManager(coordinator=coordinator, name=name).acquire()


def signal_existing_instance(
    name: str = "AudioBlue",
    coordinator: InstanceCoordinator | None = None,
) -> None:
    """显式向已有实例发送激活信号。"""
    (coordinator or Win32InstanceCoordinator()).signal_existing(name)
