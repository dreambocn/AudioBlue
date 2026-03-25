"""验证 WinRT 状态枚举如何映射为稳定的内部状态码。"""

from winrt.windows.media.audio import (
    AudioPlaybackConnectionOpenResultStatus,
    AudioPlaybackConnectionState,
)

from audio_blue.connector_service import (
    map_connection_state,
    map_open_result_status,
)


def test_map_open_result_status_success():
    assert map_open_result_status(AudioPlaybackConnectionOpenResultStatus.SUCCESS) == "connected"


def test_map_open_result_status_timeout():
    assert map_open_result_status(AudioPlaybackConnectionOpenResultStatus.REQUEST_TIMED_OUT) == "timeout"


def test_map_open_result_status_denied():
    assert map_open_result_status(AudioPlaybackConnectionOpenResultStatus.DENIED_BY_SYSTEM) == "denied"


def test_map_open_result_status_unknown_failure():
    assert map_open_result_status(AudioPlaybackConnectionOpenResultStatus.UNKNOWN_FAILURE) == "error"


def test_map_connection_state_closed_event_maps_to_disconnected():
    assert map_connection_state(AudioPlaybackConnectionState.CLOSED) == "disconnected"


def test_map_connection_state_opened_maps_to_connected():
    assert map_connection_state(AudioPlaybackConnectionState.OPENED) == "connected"
