"""验证 WinRT 连接后端对瞬时状态抖动的处理。"""

from __future__ import annotations

from types import SimpleNamespace

import audio_blue.connector_service as connector_service


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
