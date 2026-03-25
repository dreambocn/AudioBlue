import logging
import threading
from threading import Event

import pytest

from audio_blue.main import HybridAppHost, run_app
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
        self.calls: list[str] = []

    def refresh_devices(self):
        self.calls.append("refresh")
        self.known_devices = {
            "device-1": DeviceSummary(device_id="device-1", name="Headphones"),
        }
        return list(self.known_devices.values())

    def connect(self, device_id: str, trigger: str = "manual"):
        self.calls.append(f"connect:{device_id}:{trigger}")
        self.active_connections[device_id] = object()

    def shutdown(self):
        self.shutdown_called = True


class HostStub:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.run_called = False

    def run(self):
        self.run_called = True


class DesktopHostStub:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.run_called = False
        self.run_thread_name: str | None = None

    def run(self, on_started=None):
        self.run_called = True
        self.run_thread_name = threading.current_thread().name
        if self.error is not None:
            raise self.error
        if on_started is not None:
            on_started()


class TrayThreadHostStub:
    def __init__(self, started: Event):
        self.started = started
        self.run_called = False
        self.run_thread_name: str | None = None

    def run(self):
        self.run_called = True
        self.run_thread_name = threading.current_thread().name
        self.started.set()


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


def test_run_app_restores_reconnect_devices_before_host_run():
    built_host: HostStub | None = None
    service = ServiceStub()

    def host_factory(**kwargs):
        nonlocal built_host
        built_host = HostStub(**kwargs)
        return built_host

    result = run_app(
        background=False,
        instance_manager=InstanceManagerStub(acquired=True),
        service_factory=lambda: service,
        host_factory=host_factory,
        config=AppConfig(reconnect=True, last_devices=["device-1"]),
        logger=logging.getLogger("test"),
        storage=object(),
    )

    assert result == 0
    assert service.calls[:2] == ["refresh", "connect:device-1:startup"]
    assert built_host is not None
    assert built_host.run_called is True


def test_hybrid_app_host_runs_desktop_on_main_thread_and_tray_on_worker():
    tray_started = Event()
    tray_host = TrayThreadHostStub(started=tray_started)
    desktop_host = DesktopHostStub()
    host = HybridAppHost(
        desktop_host=desktop_host,
        tray_host_factory=lambda: tray_host,
        fallback_host_factory=lambda: HostStub(),
        logger=logging.getLogger("test"),
    )

    host.run()

    assert desktop_host.run_called is True
    assert desktop_host.run_thread_name == threading.current_thread().name
    assert tray_started.wait(1) is True
    assert tray_host.run_called is True
    assert tray_host.run_thread_name == "audio-blue-tray"


def test_hybrid_app_host_falls_back_when_hybrid_ui_is_unavailable(caplog):
    desktop_host = DesktopHostStub(error=FileNotFoundError("Run npm run build"))
    fallback_host = HostStub()
    host = HybridAppHost(
        desktop_host=desktop_host,
        tray_host_factory=lambda: TrayThreadHostStub(started=Event()),
        fallback_host_factory=lambda: fallback_host,
        logger=logging.getLogger("test"),
    )

    with caplog.at_level(logging.WARNING):
        host.run()

    assert fallback_host.run_called is True
    assert "Falling back to tray-only mode" in caplog.text


def test_hybrid_app_host_reraises_non_hybrid_errors():
    host = HybridAppHost(
        desktop_host=DesktopHostStub(error=RuntimeError("boom")),
        tray_host_factory=lambda: TrayThreadHostStub(started=Event()),
        fallback_host_factory=lambda: HostStub(),
        logger=logging.getLogger("test"),
    )

    with pytest.raises(RuntimeError, match="boom"):
        host.run()
