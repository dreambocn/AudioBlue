"""覆盖连接服务的最小运行时辅助行为。"""

from audio_blue.connector_service import run_awaitable_blocking


class ImmediateAwaitable:
    """模拟 WinRT 风格的 awaitable，验证同步包装器兼容性。"""

    def __await__(self):
        async def _inner():
            return "done"

        return _inner().__await__()


def test_run_awaitable_blocking_handles_winrt_style_awaitables():
    assert run_awaitable_blocking(ImmediateAwaitable()) == "done"
