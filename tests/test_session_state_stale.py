from audio_blue.app_state import AppStateStore
from audio_blue.models import AppConfig, DeviceRule, DeviceSummary
from audio_blue.notification_service import NotificationService
from audio_blue.session_state import SessionStateCoordinator


class ServiceStub:
    def __init__(self) -> None:
        self.known_devices = {
            "device-1": DeviceSummary(
                device_id="device-1",
                name="Headphones",
                connection_state="connected",
                present_in_last_scan=True,
            )
        }
        self.active_connections = {"device-1": object()}
        self._state_callback = None
        self.connect_calls: list[tuple[str, str]] = []

    def has_completed_initial_enumeration(self):
        return True

    def connect(self, device_id: str, trigger: str = "manual"):
        self.connect_calls.append((device_id, trigger))

    def refresh_devices(self):
        return list(self.known_devices.values())

    def emit_state_event(self, device_id: str, *, state: str, trigger: str = "runtime") -> None:
        existing = self.known_devices[device_id]
        self.known_devices[device_id] = DeviceSummary(
            device_id=existing.device_id,
            name=existing.name,
            connection_state=state,
            present_in_last_scan=existing.present_in_last_scan,
            last_seen_at=existing.last_seen_at,
        )
        if state != "connected":
            self.active_connections.pop(device_id, None)
        if callable(self._state_callback):
            self._state_callback(
                {
                    "event": "device_state_changed",
                    "device_id": device_id,
                    "state": state,
                    "trigger": trigger,
                }
            )


class AutostartManagerStub:
    def set_enabled(self, enabled: bool):
        return None


class StorageStub:
    def __init__(self) -> None:
        self.activity_events: list[dict] = []

    def record_connection_attempt(self, **payload):
        return None

    def upsert_device_cache(self, **payload):
        return None

    def record_activity_event(self, **payload):
        self.activity_events.append(payload)


class RetrySchedulerStub:
    def __init__(self) -> None:
        self.calls: list[tuple[float, object]] = []

    def __call__(self, delay: float, callback):
        self.calls.append((delay, callback))
        return type("Handle", (), {"cancel": lambda self: None})()


def test_session_state_keeps_stale_visible_and_starts_recover_flow():
    service = ServiceStub()
    scheduler = RetrySchedulerStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)}
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="stale", trigger="health_check")
    snapshot = session_state.snapshot()
    device = next(item for item in snapshot["devices"] if item["deviceId"] == "device-1")

    assert device["connectionState"] == "stale"
    assert snapshot["connectionOverview"]["status"] == "stale"
    assert service.connect_calls == [("device-1", "recover")]


def test_session_state_exposes_stale_as_last_failure():
    service = ServiceStub()
    scheduler = RetrySchedulerStub()
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)}
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="silent"),
        storage=StorageStub(),
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="stale", trigger="health_check")
    snapshot = session_state.snapshot()

    assert snapshot["lastFailure"] is not None
    assert snapshot["lastFailure"]["state"] == "stale"


def test_session_state_publishes_failure_notification_for_stale():
    service = ServiceStub()
    scheduler = RetrySchedulerStub()
    published = []
    session_state = SessionStateCoordinator(
        service=service,
        app_state=AppStateStore(
            config=AppConfig(
                device_rules={"device-1": DeviceRule(auto_connect_on_reappear=True)}
            )
        ),
        autostart_manager=AutostartManagerStub(),
        notification_service=NotificationService(policy="all", sink=published.append),
        storage=StorageStub(),
        retry_scheduler=scheduler,
    )

    service.emit_state_event("device-1", state="stale", trigger="health_check")

    assert published
    assert published[-1].level == "error"
