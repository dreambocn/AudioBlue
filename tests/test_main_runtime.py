import logging

from audio_blue.main import run_app
from audio_blue.models import AppConfig, DeviceSummary


class InstanceManagerStub:
    def __init__(self, acquired: bool):
        self.acquired = acquired
        self.release_called = False

    def acquire(self) -> bool:
        return self.acquired

    def release(self) -> None:
        self.release_called = True


class ServiceStub:
    def __init__(self):
        self.known_devices = {}
        self.active_connections = {}
        self.shutdown_called = False

    def refresh_devices(self):
        self.known_devices = {
            "device-1": DeviceSummary(device_id="device-1", name="Headphones"),
        }
        return list(self.known_devices.values())

    def connect(self, device_id: str):
        self.active_connections[device_id] = object()

    def shutdown(self):
        self.shutdown_called = True


class HostStub:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.run_called = False

    def run(self):
        self.run_called = True


def test_run_app_returns_when_existing_instance_is_active():
    service_factory_called = False

    def service_factory():
        nonlocal service_factory_called
        service_factory_called = True
        return ServiceStub()

    result = run_app(
        background=False,
        instance_manager=InstanceManagerStub(acquired=False),
        service_factory=service_factory,
        host_factory=lambda **kwargs: HostStub(**kwargs),
        config=AppConfig(),
        logger=logging.getLogger("test"),
    )

    assert result == 0
    assert service_factory_called is False


def test_run_app_passes_background_mode_to_host():
    built_host: HostStub | None = None

    def host_factory(**kwargs):
        nonlocal built_host
        built_host = HostStub(**kwargs)
        return built_host

    instance_manager = InstanceManagerStub(acquired=True)
    result = run_app(
        background=True,
        instance_manager=instance_manager,
        service_factory=ServiceStub,
        host_factory=host_factory,
        config=AppConfig(),
        logger=logging.getLogger("test"),
    )

    assert result == 0
    assert built_host is not None
    assert built_host.kwargs["background"] is True
    assert built_host.run_called is True
    assert instance_manager.release_called is True
