"""覆盖设备观察器驱动下的连接服务状态变化。"""

import time

from audio_blue.connector_service import ConnectorService
from audio_blue.models import DeviceSummary


class WatcherBackendStub:
    """模拟带观察器回调的连接后端，便于主动推送设备变化。"""

    def __init__(self) -> None:
        self.devices: list[DeviceSummary] = []
        self.watcher_callback = None
        self.connect_impl = None
        self.probe_impl = None
        self.stop_calls = 0

    def list_devices(self):
        return list(self.devices)

    def connect(self, device_id: str, state_callback):
        if self.connect_impl is not None:
            return self.connect_impl(device_id, state_callback)
        return object(), "connected"

    def probe_connection(self, handle):
        if self.probe_impl is not None:
            return self.probe_impl(handle)
        return "connected"

    def disconnect(self, handle):
        return None

    def start_watcher(self, callback):
        self.watcher_callback = callback
        return object()

    def stop_watcher(self, handle):
        self.stop_calls += 1

    def emit(self, payload):
        assert callable(self.watcher_callback)
        self.watcher_callback(payload)


def _wait_until(predicate, timeout: float = 1.0) -> None:
    """等待后台线程完成观察器注册，避免测试与异步初始化抢跑。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for watcher callback to be ready.")


def test_service_watcher_tracks_added_and_removed_devices_without_manual_refresh():
    published = []
    backend = WatcherBackendStub()
    service = ConnectorService(backend=backend, state_callback=published.append)

    _wait_until(lambda: callable(backend.watcher_callback))

    backend.emit(
        {
            "change": "added",
            "device": DeviceSummary(device_id="device-1", name="Phone"),
        }
    )

    assert service.known_devices["device-1"].present_in_last_scan is True
    assert published[-1] == {
        "event": "device_presence_changed",
        "device_id": "device-1",
        "present": True,
        "previous_present": False,
        "change": "added",
    }

    backend.emit(
        {
            "change": "removed",
            "device_id": "device-1",
        }
    )

    assert service.known_devices["device-1"].present_in_last_scan is False
    assert published[-1] == {
        "event": "device_presence_changed",
        "device_id": "device-1",
        "present": False,
        "previous_present": True,
        "change": "removed",
    }

    service.shutdown()
    assert backend.stop_calls == 1


def test_service_treats_quick_disconnect_during_connect_as_failed():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [DeviceSummary(device_id="device-1", name="Phone")]

    def unstable_connect(device_id: str, state_callback):
        state_callback("disconnected")
        return object(), "connected"

    backend.connect_impl = unstable_connect
    service = ConnectorService(backend=backend, state_callback=published.append)
    service.refresh_devices()

    service.connect("device-1", trigger="startup")

    assert "device-1" not in service.active_connections
    assert service.known_devices["device-1"].connection_state == "failed"
    assert published[-1] == {
        "event": "device_connection_failed",
        "device_id": "device-1",
        "state": "failed",
        "trigger": "startup",
    }


def test_service_marks_connection_stale_when_health_check_fails_without_disconnect_event():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [DeviceSummary(device_id="device-1", name="Phone")]
    backend.probe_impl = lambda _handle: "stale"
    service = ConnectorService(backend=backend, state_callback=published.append)
    service.refresh_devices()
    service.connect("device-1", trigger="manual")

    service.poll_connection_health()

    assert "device-1" not in service.active_connections
    assert service.known_devices["device-1"].connection_state == "stale"
    assert published[-1] == {
        "event": "device_state_changed",
        "device_id": "device-1",
        "state": "stale",
        "trigger": "health_check",
    }
