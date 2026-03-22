from audio_blue.connector_service import run_awaitable_blocking


class ImmediateAwaitable:
    def __await__(self):
        async def _inner():
            return "done"

        return _inner().__await__()


def test_run_awaitable_blocking_handles_winrt_style_awaitables():
    assert run_awaitable_blocking(ImmediateAwaitable()) == "done"
