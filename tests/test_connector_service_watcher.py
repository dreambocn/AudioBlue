"""覆盖设备观察器驱动下的连接服务状态变化。"""

import time

from audio_blue.audio_routing import AudioFlowObservation, LocalRenderSnapshot
from audio_blue.connector_service import ConnectorService
from audio_blue.models import DeviceSummary


class WatcherBackendStub:
    """模拟带观察器回调的连接后端，便于主动推送设备变化。"""

    def __init__(self) -> None:
        self.devices: list[DeviceSummary] = []
        self.watcher_callback = None
        self.connect_impl = None
        self.probe_impl = None
        self.disconnect_calls = 0
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
        self.disconnect_calls += 1
        return None

    def start_watcher(self, callback):
        self.watcher_callback = callback
        return object()

    def stop_watcher(self, handle):
        self.stop_calls += 1

    def emit(self, payload):
        assert callable(self.watcher_callback)
        self.watcher_callback(payload)


class AudioRouteProbeStub:
    """按测试场景返回固定的本机输出与峰值结果。"""

    def __init__(
        self,
        *,
        render_snapshot: LocalRenderSnapshot | None = None,
        flow_observation: AudioFlowObservation | None = None,
        render_snapshots: list[LocalRenderSnapshot] | None = None,
        flow_observations: list[AudioFlowObservation] | None = None,
    ) -> None:
        self.render_snapshot = render_snapshot or LocalRenderSnapshot(
            render_id="render-1",
            render_name="扬声器",
            render_state="active",
            is_active=True,
        )
        self.flow_observation = flow_observation or AudioFlowObservation(
            observed=True,
            peak_max=0.25,
            sample_count=4,
            threshold=0.01,
        )
        self.render_snapshots = list(render_snapshots) if render_snapshots is not None else None
        self.flow_observations = list(flow_observations) if flow_observations is not None else None
        self.render_snapshot_calls = 0
        self.endpoint_container_ids: list[str | None] = []
        self.sampled_render_ids: list[str] = []

    def get_default_render_snapshot(self) -> LocalRenderSnapshot:
        self.render_snapshot_calls += 1
        if self.render_snapshots is not None and self.render_snapshots:
            if len(self.render_snapshots) > 1:
                return self.render_snapshots.pop(0)
            return self.render_snapshots[0]
        return self.render_snapshot

    def get_audio_endpoint_snapshot(self, *, container_id: str | None = None) -> LocalRenderSnapshot:
        self.endpoint_container_ids.append(container_id)
        return self.get_default_render_snapshot()

    def sample_audio_flow(
        self,
        *,
        render_id: str,
        sample_count: int,
        sample_interval_seconds: float,
        threshold: float,
    ) -> AudioFlowObservation:
        self.sampled_render_ids.append(render_id)
        if self.flow_observations is not None and self.flow_observations:
            if len(self.flow_observations) > 1:
                return self.flow_observations.pop(0)
            return self.flow_observations[0]
        return self.flow_observation


def _wait_until(predicate, timeout: float = 1.0) -> None:
    """等待后台线程完成异步事件，避免测试与线程抢跑。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for async state.")


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
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        audio_route_probe=AudioRouteProbeStub(),
        health_check_interval_seconds=0,
        remote_aep_delay_seconds=0,
    )
    service.refresh_devices()
    service.connect("device-1", trigger="manual")
    _wait_until(lambda: any(item.get("event") == "device_connection_diagnostics" for item in published))

    service.poll_connection_health()

    assert "device-1" not in service.active_connections
    assert service.known_devices["device-1"].connection_state == "stale"
    assert published[-1] == {
        "event": "device_state_changed",
        "device_id": "device-1",
        "state": "stale",
        "trigger": "health_check",
    }


def test_service_keeps_connection_and_emits_new_diagnostics_when_audio_flow_is_observed():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=AudioRouteProbeStub(
            flow_observation=AudioFlowObservation(
                observed=True,
                peak_max=0.42,
                sample_count=3,
                threshold=0.01,
            )
        ),
        remote_aep_delay_seconds=0,
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("details", {}).get("phase") == "audio_flow"
            for item in published
        )
    )

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 0
    assert any(
        item == {
            "event": "device_connection_diagnostics",
            "device_id": "device-1",
            "trigger": "manual",
            "details": {
                "phase": "remote_aep",
                "status": "confirmed",
                "containerId": "container-1",
                "aepConnected": True,
                "aepPresent": True,
            },
        }
        for item in published
    )
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("details", {}).get("phase") == "local_render"
        and item.get("details", {}).get("status") == "active"
        for item in published
    )
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("details", {}).get("phase") == "audio_flow"
        and item.get("details", {}).get("status") == "observed"
        for item in published
    )


def test_service_validates_container_matched_audio_endpoint_instead_of_default_render():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="phone-container",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]

    class ContainerAwareRouteProbe(AudioRouteProbeStub):
        """模拟默认播放端点损坏，但目标手机容器端点可用。"""

        def get_default_render_snapshot(self) -> LocalRenderSnapshot:
            self.render_snapshot_calls += 1
            return LocalRenderSnapshot(
                render_id="broken-default-render",
                render_name="耳机 (Senary Audio)",
                render_state="error",
                is_active=False,
                error="render_state:OSError",
            )

        def get_audio_endpoint_snapshot(self, *, container_id: str | None = None) -> LocalRenderSnapshot:
            self.endpoint_container_ids.append(container_id)
            return LocalRenderSnapshot(
                render_id="phone-capture-endpoint",
                render_name="麦克风 (Phone A2DP SNK)",
                render_state="active",
                is_active=True,
                container_id=container_id,
                endpoint_flow="capture",
            )

    route_probe = ContainerAwareRouteProbe(
        flow_observation=AudioFlowObservation(
            observed=True,
            peak_max=0.36,
            sample_count=4,
            threshold=0.01,
        )
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_probe_delay_seconds=0,
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "observed"
            for item in published
        )
    )

    assert route_probe.endpoint_container_ids == ["phone-container"]
    assert route_probe.render_snapshot_calls == 0
    assert route_probe.sampled_render_ids == ["phone-capture-endpoint"]
    assert backend.disconnect_calls == 0
    assert "device-1" in service.active_connections
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("details", {}).get("phase") == "local_render"
        and item.get("details", {}).get("containerId") == "phone-container"
        and item.get("details", {}).get("endpointFlow") == "capture"
        for item in published
    )


def test_service_keeps_connection_when_matched_endpoint_is_active_but_audio_is_silent():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    route_probe = AudioRouteProbeStub(
        render_snapshot=LocalRenderSnapshot(
            render_id="capture-1",
            render_name="麦克风 (Phone A2DP SNK)",
            render_state="active",
            is_active=True,
            container_id="container-1",
            endpoint_flow="capture",
        ),
        flow_observation=AudioFlowObservation(
            observed=False,
            peak_max=0.0,
            sample_count=8,
            threshold=0.01,
        ),
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_probe_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "unconfirmed"
            for item in published
        )
    )
    time.sleep(0.05)

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 1
    assert route_probe.sampled_render_ids == ["capture-1", "capture-1", "capture-1", "capture-1"]
    assert not any(item.get("event") == "device_connection_failed" for item in published)
    assert any(
        item.get("trigger") == "manual"
        and item.get("details", {}).get("nextAction") == "recover"
        for item in published
        if item.get("event") == "device_connection_diagnostics"
    )


def test_service_recovers_first_manual_connection_when_endpoint_active_but_audio_is_silent():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    route_probe = AudioRouteProbeStub(
        render_snapshots=[
            LocalRenderSnapshot(
                render_id="capture-1",
                render_name="麦克风 (Phone A2DP SNK)",
                render_state="active",
                is_active=True,
                container_id="container-1",
                endpoint_flow="capture",
            ),
            LocalRenderSnapshot(
                render_id="capture-1",
                render_name="麦克风 (Phone A2DP SNK)",
                render_state="active",
                is_active=True,
                container_id="container-1",
                endpoint_flow="capture",
            ),
            LocalRenderSnapshot(
                render_id="capture-1",
                render_name="麦克风 (Phone A2DP SNK)",
                render_state="active",
                is_active=True,
                container_id="container-1",
                endpoint_flow="capture",
            ),
        ],
        flow_observations=[
            AudioFlowObservation(
                observed=False,
                peak_max=0.0,
                sample_count=8,
                threshold=0.01,
            ),
            AudioFlowObservation(
                observed=False,
                peak_max=0.0,
                sample_count=8,
                threshold=0.01,
            ),
            AudioFlowObservation(
                observed=True,
                peak_max=0.31,
                sample_count=2,
                threshold=0.01,
            ),
        ],
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_probe_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("trigger") == "recover"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "observed"
            for item in published
        )
    )

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 1
    assert route_probe.sampled_render_ids == ["capture-1", "capture-1", "capture-1"]
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("trigger") == "manual"
        and item.get("details", {}).get("phase") == "audio_flow"
        and item.get("details", {}).get("nextAction") == "recover"
        for item in published
    )
    assert not any(item.get("event") == "device_connection_failed" for item in published)


def test_service_keeps_connection_when_matched_capture_endpoint_is_unplugged_until_playback():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    route_probe = AudioRouteProbeStub(
        render_snapshot=LocalRenderSnapshot(
            render_id="capture-1",
            render_name="麦克风 (Phone A2DP SNK)",
            render_state="unplugged",
            is_active=False,
            container_id="container-1",
            endpoint_flow="capture",
        ),
        flow_observation=AudioFlowObservation(
            observed=False,
            peak_max=0.0,
            sample_count=0,
            threshold=0.01,
            error="render_inactive",
        ),
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_probe_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("details", {}).get("phase") == "audio_flow"
            for item in published
        )
    )
    time.sleep(0.05)

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 1
    assert not any(item.get("event") == "device_connection_failed" for item in published)
    assert any(
        item.get("trigger") == "manual"
        and item.get("details", {}).get("nextAction") == "recover"
        for item in published
        if item.get("event") == "device_connection_diagnostics"
    )


def test_service_waits_for_render_endpoint_to_become_active_before_manual_connection_is_judged():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    route_probe = AudioRouteProbeStub(
        render_snapshots=[
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="inactive",
                is_active=False,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
        ],
        flow_observations=[
            AudioFlowObservation(
                observed=True,
                peak_max=0.38,
                sample_count=4,
                threshold=0.01,
            )
        ],
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "observed"
            for item in published
        )
        or any(
            item.get("event") in {"device_disconnected", "device_connection_failed"}
            for item in published
        )
    )

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 0
    assert route_probe.render_snapshot_calls >= 2
    assert route_probe.sampled_render_ids == ["render-1"]
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("details", {}).get("phase") == "local_render"
        and item.get("details", {}).get("status") == "inactive"
        for item in published
    )


def test_service_recovers_manual_connection_when_render_endpoint_never_becomes_ready_within_grace_window():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    route_probe = AudioRouteProbeStub(
        render_snapshots=[
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="inactive",
                is_active=False,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="inactive",
                is_active=False,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="inactive",
                is_active=False,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
        ],
        flow_observations=[
            AudioFlowObservation(
                observed=True,
                peak_max=0.31,
                sample_count=4,
                threshold=0.01,
            )
        ],
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_probe_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0, 0.0),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("trigger") == "recover"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "observed"
            for item in published
        )
    )

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 1
    assert route_probe.render_snapshot_calls >= 4
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("trigger") == "manual"
        and item.get("details", {}).get("phase") == "audio_flow"
        and item.get("details", {}).get("nextAction") == "recover"
        for item in published
    )
    assert not any(item.get("event") == "device_connection_failed" for item in published)


def test_service_keeps_manual_connection_when_audio_flow_stays_unconfirmed_on_active_endpoint():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    route_probe = AudioRouteProbeStub(
        render_snapshots=[
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
            LocalRenderSnapshot(
                render_id="render-1",
                render_name="扬声器",
                render_state="active",
                is_active=True,
            ),
        ],
        flow_observations=[
            AudioFlowObservation(
                observed=False,
                peak_max=0.0,
                sample_count=4,
                threshold=0.01,
            ),
            AudioFlowObservation(
                observed=False,
                peak_max=0.0,
                sample_count=4,
                threshold=0.01,
            ),
            AudioFlowObservation(
                observed=True,
                peak_max=0.27,
                sample_count=4,
                threshold=0.01,
            ),
        ],
    )
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=route_probe,
        remote_aep_delay_seconds=0,
        endpoint_probe_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("trigger") == "recover"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "observed"
            for item in published
        )
    )

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 1
    assert route_probe.sampled_render_ids == ["render-1", "render-1", "render-1"]
    assert any(
        item.get("event") == "device_connection_diagnostics"
        and item.get("trigger") == "manual"
        and item.get("details", {}).get("phase") == "audio_flow"
        and item.get("details", {}).get("status") == "unconfirmed"
        for item in published
    )
    assert not any(item.get("event") == "device_connection_failed" for item in published)
    assert any(
        item.get("trigger") == "manual"
        and item.get("details", {}).get("nextAction") == "recover"
        for item in published
        if item.get("event") == "device_connection_diagnostics"
    )


def test_service_manual_no_audio_recover_fails_terminally_after_one_retry():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=AudioRouteProbeStub(
            render_snapshots=[
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="inactive",
                    is_active=False,
                ),
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="inactive",
                    is_active=False,
                ),
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="inactive",
                    is_active=False,
                ),
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="inactive",
                    is_active=False,
                ),
            ],
            flow_observations=[
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
            ],
        ),
        remote_aep_delay_seconds=0,
        endpoint_probe_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="manual")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_failed"
            and item.get("failure_code") == "connection.no_audio"
            for item in published
        )
    )

    assert "device-1" not in service.active_connections
    assert service.known_devices["device-1"].connection_state == "failed"
    assert backend.disconnect_calls == 2
    assert sum(1 for item in published if item.get("event") == "device_connection_failed") == 1
    assert published[-1] == {
        "event": "device_connection_failed",
        "device_id": "device-1",
        "state": "failed",
        "trigger": "recover",
        "failure_code": "connection.no_audio",
        "suppress_recover": True,
    }


def test_service_recover_connection_with_active_endpoint_but_silent_audio_stays_connected():
    published = []
    backend = WatcherBackendStub()
    backend.devices = [
        DeviceSummary(
            device_id="device-1",
            name="Phone",
            container_id="container-1",
            aep_is_connected=True,
            aep_is_present=True,
        )
    ]
    service = ConnectorService(
        backend=backend,
        state_callback=published.append,
        health_check_interval_seconds=0,
        audio_route_probe=AudioRouteProbeStub(
            render_snapshots=[
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="active",
                    is_active=True,
                ),
                LocalRenderSnapshot(
                    render_id="render-1",
                    render_name="扬声器",
                    render_state="active",
                    is_active=True,
                ),
            ],
            flow_observations=[
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
                AudioFlowObservation(
                    observed=False,
                    peak_max=0.0,
                    sample_count=4,
                    threshold=0.01,
                ),
            ],
        ),
        remote_aep_delay_seconds=0,
        endpoint_ready_retry_delays_seconds=(0.0,),
    )
    service.refresh_devices()

    service.connect("device-1", trigger="recover")
    _wait_until(
        lambda: any(
            item.get("event") == "device_connection_diagnostics"
            and item.get("details", {}).get("phase") == "audio_flow"
            and item.get("details", {}).get("status") == "unconfirmed"
            for item in published
        )
    )

    assert "device-1" in service.active_connections
    assert service.known_devices["device-1"].connection_state == "connected"
    assert backend.disconnect_calls == 0
    assert not any(item.get("event") == "device_disconnected" for item in published)
    assert not any(item.get("event") == "device_connection_failed" for item in published)
