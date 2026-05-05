"""验证 WinRT 连接后端对瞬时状态抖动的处理。"""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace

import audio_blue.connector_service as connector_service
import pytest


class _FakeOpenResult:
    """模拟 WinRT 打开结果对象。"""

    def __init__(self, status: str) -> None:
        self.status = status


class _FakeConnection:
    """模拟会在打开阶段出现短暂抖动的 WinRT 连接。"""

    def __init__(self) -> None:
        self.state = "opened"
        self._callback = None
        self.removed_token = None
        self.closed = False

    def add_state_changed(self, callback):
        self._callback = callback
        return "token-1"

    def remove_state_changed(self, token) -> None:
        self.removed_token = token

    def close(self) -> None:
        self.closed = True

    async def start_async(self) -> None:
        return None

    async def open_async(self) -> _FakeOpenResult:
        # 模拟系统在建立会话途中短暂回落到 closed，随后又恢复为 opened。
        self.state = "closed"
        assert self._callback is not None
        self._callback(self, None)
        self.state = "opened"
        self._callback(self, None)
        return _FakeOpenResult("success")


class _FakeAudioPlaybackConnection:
    """模拟 WinRT AudioPlaybackConnection 类型入口。"""

    @staticmethod
    def try_create_from_id(_device_id: str) -> _FakeConnection:
        return _FakeConnection()


class _BackendStub:
    """提供 ConnectorService worker 测试所需的最小后端。"""

    def __init__(self, *, list_devices, stop_watcher=None):
        self._list_devices = list_devices
        self._stop_watcher = stop_watcher

    def list_devices(self):
        return self._list_devices()

    def connect(self, _device_id, _state_callback):
        return None, "connected"

    def disconnect(self, _handle) -> None:
        return None

    def probe_connection(self, _handle) -> str:
        return "connected"

    def start_watcher(self, _callback):
        return object()

    def stop_watcher(self, _handle) -> None:
        if self._stop_watcher is not None:
            self._stop_watcher(_handle)
        return None


def test_winrt_backend_keeps_successful_open_despite_transient_state_flap(monkeypatch):
    """当 OpenAsync 最终成功时，短暂抖动不应被误判为失败。"""

    monkeypatch.setattr(
        connector_service,
        "AudioPlaybackConnectionState",
        SimpleNamespace(OPENED="opened"),
    )
    monkeypatch.setattr(
        connector_service,
        "AudioPlaybackConnectionOpenResultStatus",
        SimpleNamespace(
            SUCCESS="success",
            REQUEST_TIMED_OUT="timeout",
            DENIED_BY_SYSTEM="denied",
            UNKNOWN_FAILURE="error",
        ),
    )
    monkeypatch.setattr(
        connector_service,
        "AudioPlaybackConnection",
        _FakeAudioPlaybackConnection,
    )

    backend = connector_service.WinRTConnectorBackend()

    handle, state = backend.connect("device-1", lambda _state: None)

    assert state == "connected"
    assert handle is not None
    assert handle.connection.closed is False


def test_worker_call_times_out_when_backend_hangs():
    """WinRT worker 卡住时，调用方应收到有界失败而不是无限等待。"""
    hang_event = Event()
    events: list[dict[str, object]] = []
    service = connector_service.ConnectorService(
        backend=_BackendStub(list_devices=lambda: hang_event.wait()),
        state_callback=events.append,
        worker_timeout_seconds=0.01,
        health_check_interval_seconds=0,
    )

    with pytest.raises(connector_service.ConnectorWorkerTimeoutError, match="list_devices"):
        service.refresh_devices()

    assert events[-1] == {
        "event": "worker_call_timeout",
        "action": "list_devices",
        "timeout_seconds": 0.01,
        "error_code": "ConnectorWorkerTimeoutError",
    }

    hang_event.set()
    service.shutdown()


def test_worker_rejects_new_jobs_after_shutdown():
    """关闭开始后不再接受新的 worker job。"""
    service = connector_service.ConnectorService(
        backend=_BackendStub(list_devices=lambda: []),
        health_check_interval_seconds=0,
    )
    service.shutdown()

    with pytest.raises(connector_service.ConnectorWorkerShutdownError):
        service.refresh_devices()


def test_shutdown_completes_when_stop_watcher_times_out():
    """关闭清理遇到 WinRT watcher 卡住时，也必须最终进入关闭态。"""
    blocker = Event()
    events: list[dict[str, object]] = []
    service = connector_service.ConnectorService(
        backend=_BackendStub(
            list_devices=lambda: [],
            stop_watcher=lambda _handle: blocker.wait(),
        ),
        state_callback=events.append,
        worker_timeout_seconds=0.01,
        health_check_interval_seconds=0,
    )

    service.shutdown()
    blocker.set()

    assert service.is_shutdown is True
    assert events[-1] == {"event": "service_shutdown"}
    assert any(
        item.get("event") == "worker_call_timeout"
        and item.get("action") == "stop_watcher"
        for item in events
    )
