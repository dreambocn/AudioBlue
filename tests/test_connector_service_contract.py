from audio_blue.connector_service import ConnectorService
from audio_blue.models import DeviceSummary


def test_refresh_devices_updates_inventory_and_emits_state():
    published = []
    service = ConnectorService(
        device_provider=lambda: [DeviceSummary(device_id="device-1", name="Headphones")],
        state_callback=published.append,
    )

    devices = service.refresh_devices()

    assert [device.device_id for device in devices] == ["device-1"]
    assert service.known_devices["device-1"].name == "Headphones"
    assert published[-1]["event"] == "devices_refreshed"


def test_connect_tracks_connection_and_emits_state():
    published = []
    service = ConnectorService(
        device_provider=lambda: [DeviceSummary(device_id="device-1", name="Headphones")],
        state_callback=published.append,
    )
    service.refresh_devices()

    service.connect("device-1")

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert published[-1] == {"event": "device_connected", "device_id": "device-1"}


def test_disconnect_releases_connection_and_emits_state():
    published = []
    service = ConnectorService(
        device_provider=lambda: [DeviceSummary(device_id="device-1", name="Headphones")],
        state_callback=published.append,
    )
    service.refresh_devices()
    service.connect("device-1")

    service.disconnect("device-1")

    assert "device-1" not in service.active_connections
    assert service.known_devices["device-1"].connection_state == "disconnected"
    assert published[-1] == {"event": "device_disconnected", "device_id": "device-1"}


def test_shutdown_clears_connections_and_marks_service_stopped():
    service = ConnectorService(
        device_provider=lambda: [DeviceSummary(device_id="device-1", name="Headphones")],
    )
    service.refresh_devices()
    service.connect("device-1")

    service.shutdown()

    assert service.active_connections == {}
    assert service.is_shutdown is True
