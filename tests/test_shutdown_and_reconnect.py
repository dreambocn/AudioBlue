"""覆盖应用关闭与启动重连之间的状态衔接。"""

import logging

from audio_blue.connector_service import ConnectorService
from audio_blue.main import restore_reconnect_devices
from audio_blue.models import AppConfig, DeviceSummary


def test_restore_reconnect_devices_refreshes_before_connecting():
    class ServiceStub:
        def __init__(self):
            self.calls = []

        def refresh_devices(self):
            self.calls.append("refresh")
            return [DeviceSummary(device_id="device-1", name="Headphones")]

        def connect(self, device_id: str):
            self.calls.append(f"connect:{device_id}")

    service = ServiceStub()

    restore_reconnect_devices(
        service=service,
        config=AppConfig(reconnect=True, last_devices=["device-1"]),
        logger=logging.getLogger("test"),
    )

    assert service.calls == ["refresh", "connect:device-1"]


def test_restore_reconnect_devices_retries_when_device_appears_after_initial_scan():
    class ServiceStub:
        def __init__(self):
            self.refresh_count = 0
            self.calls = []
            self.known_devices = {}
            self.active_connections = {}

        def refresh_devices(self):
            self.refresh_count += 1
            self.calls.append(f"refresh:{self.refresh_count}")
            if self.refresh_count == 1:
                return []
            device = DeviceSummary(device_id="device-1", name="Headphones")
            self.known_devices = {"device-1": device}
            return [device]

        def connect(self, device_id: str, trigger: str = "manual"):
            self.calls.append(f"connect:{device_id}:{trigger}")
            self.active_connections[device_id] = object()

    service = ServiceStub()

    restore_reconnect_devices(
        service=service,
        config=AppConfig(reconnect=True, last_devices=["device-1"]),
        logger=logging.getLogger("test"),
        retry_attempts=1,
        retry_backoff_seconds=0,
    )

    assert service.calls == ["refresh:1", "refresh:2", "connect:device-1:startup"]


def test_shutdown_stops_worker_thread_for_backend_mode():
    class BackendStub:
        def list_devices(self):
            return [DeviceSummary(device_id="device-1", name="Headphones")]

        def connect(self, device_id, state_callback):
            state_callback("connected")
            return object(), "connected"

        def disconnect(self, handle):
            return None

    service = ConnectorService(backend=BackendStub())
    service.refresh_devices()
    service.connect("device-1")

    service.shutdown()

    assert service.is_shutdown is True
    assert service.active_connections == {}
    assert service._worker is not None
    assert service._worker.is_alive() is False
