"""协调连接服务、持久化存储与前端会话快照。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from inspect import Parameter, signature
from threading import Lock, Timer
from typing import Any, Protocol

from audio_blue.config import save_config
from audio_blue.localization import connection_failure_message, notification_copy
from audio_blue.rules_engine import RulesEngine

_RECOVER_RETRY_DELAYS_SECONDS = (1.0, 2.0)


@dataclass(slots=True)
class _RecoverJob:
    """记录单个设备当前异常断联恢复任务的代次与重试进度。"""

    token: int
    next_retry_index: int = 0
    handle: object | None = None


class RuntimeStorage(Protocol):
    """定义会话层依赖的最小运行时存储能力。"""

    def record_connection_attempt(self, **payload: Any) -> None: ...

    def upsert_device_cache(self, **payload: Any) -> None: ...

    def record_activity_event(self, **payload: Any) -> None: ...


class SessionStateCoordinator:
    """统一处理设备刷新、自动连接、事件发布和诊断记录。"""

    def __init__(
        self,
        *,
        service,
        app_state,
        autostart_manager,
        notification_service,
        storage: RuntimeStorage | None = None,
        observability=None,
        retry_scheduler: Callable[[float, Callable[[], None]], object] | None = None,
    ) -> None:
        self.service = service
        self.app_state = app_state
        self.autostart_manager = autostart_manager
        self.notification_service = notification_service
        self.storage = storage
        self.observability = observability
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._startup_auto_connect_completed = self._detect_startup_phase_completed()
        self._retry_scheduler = retry_scheduler or self._schedule_retry
        self._recover_lock = Lock()
        self._recover_sequence = 0
        self._manual_disconnect_suppressed_devices: set[str] = set()
        self._pending_recover_jobs: dict[str, _RecoverJob] = {}
        self._recover_shutdown = False
        self._bind_service_callback()
        self._sync_from_service()

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """注册快照监听器，并返回对应的取消订阅函数。"""
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    def snapshot(self) -> dict[str, Any]:
        """返回经过会话层补充后的标准化快照。"""
        self._sync_from_service()
        return self._normalize_snapshot(self.app_state.snapshot())

    def list_devices(self):
        self._sync_from_service()
        return list(getattr(self.service, "known_devices", {}).values())

    def refresh_devices(self) -> dict[str, Any]:
        """刷新设备列表，并在合适时机触发启动/再出现自动连接。"""
        previous_presence = {
            device_id: bool(getattr(device, "present_in_last_scan", True))
            for device_id, device in getattr(self.service, "known_devices", {}).items()
        }

        try:
            self.service.refresh_devices()
            self._sync_from_service()
            self._sync_device_cache()

            devices = list(getattr(self.service, "known_devices", {}).values())
            if not self._startup_auto_connect_completed:
                # 首轮刷新优先走启动自动连接，避免应用刚启动时误判为“设备再次出现”。
                self._attempt_auto_connect(trigger="startup", devices=devices)
                self._startup_auto_connect_completed = True
            else:
                reappeared = [
                    device
                    for device in devices
                    if getattr(device, "present_in_last_scan", True)
                    and not previous_presence.get(device.device_id, False)
                ]
                if reappeared:
                    self._attempt_auto_connect(trigger="reappear", devices=reappeared)

            self._record_activity_event(
                area="device",
                event_type="device.refresh.completed",
                level="info",
                title="设备列表已刷新",
                detail=f"本轮共同步 {len(devices)} 个设备。",
                details={"deviceCount": len(devices)},
            )
            self._sync_from_service()
            return self._publish_snapshot()
        except Exception as exc:
            self._record_exception(
                area="device",
                event_type="device.refresh.failed",
                title="刷新设备失败",
                exc=exc,
            )
            raise

    def connect_device(self, device_id: str) -> dict[str, Any]:
        self._cancel_recover_job(device_id)
        try:
            self._connect_service_device(device_id, trigger="manual")
        except Exception as exc:
            self._record_exception(
                area="connection",
                event_type="connection.manual_connect.failed",
                title="手动连接失败",
                exc=exc,
                device_id=device_id,
            )
            raise
        self._sync_from_service()
        return self._publish_snapshot()

    def disconnect_device(self, device_id: str) -> dict[str, Any]:
        self._suppress_manual_auto_connect(device_id)
        self._cancel_recover_job(device_id)
        try:
            self._disconnect_service_device(device_id, trigger="manual")
        except Exception as exc:
            self._record_exception(
                area="connection",
                event_type="connection.manual_disconnect.failed",
                title="手动断开失败",
                exc=exc,
                device_id=device_id,
            )
            raise
        self._sync_from_service()
        return self._publish_snapshot()

    def update_device_rule(self, device_id: str, rule_patch: dict[str, Any]) -> dict[str, Any]:
        """更新单个设备规则，并立即落盘配置。"""
        self.app_state.update_device_rule(device_id, rule_patch)
        self._persist_config()
        self._record_activity_event(
            area="automation",
            event_type="automation.rule.updated",
            level="info",
            title="自动连接规则已更新",
            detail=f"{device_id} 的自动连接规则已更新。",
            device_id=device_id,
            details=rule_patch,
        )
        return self._publish_snapshot()

    def reorder_device_priority(self, device_ids: list[str]) -> dict[str, Any]:
        """更新自动连接优先级，并广播新的快照。"""
        self.app_state.reorder_device_priority(device_ids)
        self._persist_config()
        self._record_activity_event(
            area="automation",
            event_type="automation.priority.reordered",
            level="info",
            title="自动连接顺序已更新",
            detail="自动连接设备优先级已重新排序。",
            details={"deviceIds": list(device_ids)},
        )
        return self._publish_snapshot()

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        self.autostart_manager.set_enabled(enabled)
        self.app_state.config.startup.autostart = enabled
        self._persist_config()
        self._record_activity_event(
            area="settings",
            event_type="settings.autostart.updated",
            level="info",
            title="随 Windows 启动设置已更新",
            detail=f"随 Windows 启动已{'开启' if enabled else '关闭'}。",
        )
        return self._publish_snapshot()

    def set_reconnect(self, enabled: bool) -> dict[str, Any]:
        self.app_state.config.reconnect = enabled
        self._persist_config()
        self._record_activity_event(
            area="settings",
            event_type="settings.reconnect.updated",
            level="info",
            title="启动自动重连设置已更新",
            detail=f"下次启动自动重连已{'开启' if enabled else '关闭'}。",
        )
        return self._publish_snapshot()

    def set_theme(self, mode: str) -> dict[str, Any]:
        self.app_state.config.ui.theme = mode
        self._persist_config()
        self._record_activity_event(
            area="settings",
            event_type="settings.theme.updated",
            level="info",
            title="主题模式已更新",
            detail=f"主题模式已切换为 {mode}。",
        )
        return self._publish_snapshot()

    def set_language(self, language: str) -> dict[str, Any]:
        setattr(self.app_state.config.ui, "language", language)
        self._persist_config()
        self._record_activity_event(
            area="settings",
            event_type="settings.language.updated",
            level="info",
            title="界面语言已更新",
            detail=f"界面语言已切换为 {language}。",
        )
        return self._publish_snapshot()

    def set_notification_policy(self, policy: str) -> dict[str, Any]:
        self.notification_service.update_policy(policy)
        self.app_state.config.notification.policy = policy
        self._persist_config()
        self._record_activity_event(
            area="settings",
            event_type="settings.notification.updated",
            level="info",
            title="通知策略已更新",
            detail=f"通知策略已切换为 {policy}。",
        )
        return self._publish_snapshot()

    def handle_service_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.app_state.handle_connector_event(payload)
        self._sync_from_service()
        self._sync_device_cache()
        self._record_connection_attempt(payload)
        self._record_service_activity(payload)
        self._handle_auto_connect_event(payload)
        self._publish_notification(payload)
        return self._publish_snapshot()

    def shutdown(self) -> None:
        """释放挂起的 recovery 定时任务，避免应用退出后残留回调。"""
        with self._recover_lock:
            self._recover_shutdown = True
            device_ids = list(self._pending_recover_jobs)
        for device_id in device_ids:
            self._cancel_recover_job(device_id)

    def record_client_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record_activity_event(
            area=str(payload.get("area", "ui")),
            event_type=str(payload.get("eventType", payload.get("event_type", "ui.event"))),
            level=str(payload.get("level", "error")),
            title=str(payload.get("title", "界面事件")),
            detail=(
                str(payload.get("detail"))
                if payload.get("detail") is not None
                else None
            ),
            device_id=(
                str(payload.get("deviceId"))
                if payload.get("deviceId") is not None
                else None
            ),
            error_code=(
                str(payload.get("errorCode"))
                if payload.get("errorCode") is not None
                else None
            ),
            details=payload.get("details") if isinstance(payload.get("details"), dict) else None,
        )
        return self._publish_snapshot()

    def _sync_from_service(self) -> None:
        self.app_state.sync_devices(list(getattr(self.service, "known_devices", {}).values()))

    def _publish_snapshot(self) -> dict[str, Any]:
        snapshot = self._normalize_snapshot(self.app_state.snapshot())
        for callback in list(self._listeners):
            callback(snapshot)
        return snapshot

    def _bind_service_callback(self) -> None:
        existing_callback = getattr(self.service, "_state_callback", None)

        def composed_callback(payload: dict[str, Any]) -> None:
            if callable(existing_callback):
                existing_callback(payload)
            if isinstance(payload, dict):
                self.handle_service_event(payload)

        setattr(self.service, "_state_callback", composed_callback)

    def _normalize_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        settings = snapshot.setdefault("settings", {})
        startup_settings = settings.setdefault("startup", {})
        startup_settings.setdefault("reconnectOnNextStart", bool(self.app_state.config.reconnect))
        ui_settings = settings.setdefault("ui", {})
        ui_settings.setdefault("language", getattr(self.app_state.config.ui, "language", "system"))
        diagnostics = snapshot.setdefault("diagnostics", {})
        if isinstance(diagnostics, dict):
            diagnostics.setdefault("runtimeMode", "native")
            diagnostics["watcher"] = {
                "initialEnumerationCompleted": bool(self._detect_startup_phase_completed()),
                "startupReconnectCompleted": bool(self._startup_auto_connect_completed),
                "knownDeviceCount": len(getattr(self.service, "known_devices", {})),
                "activeConnectionCount": len(getattr(self.service, "active_connections", {})),
                "serviceShutdown": bool(getattr(self.service, "is_shutdown", False)),
            }
        return snapshot

    def _detect_startup_phase_completed(self) -> bool:
        checker = getattr(self.service, "has_completed_initial_enumeration", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception:
                return False
        return False

    def _attempt_auto_connect(self, *, trigger: str, devices: list[Any]) -> None:
        if trigger not in {"startup", "reappear"}:
            return

        candidates = RulesEngine(
            self.app_state.config,
            suppressed_device_ids=self._manual_disconnect_suppressed_devices,
        ).get_auto_connect_candidates(
            devices=devices,
            trigger=trigger,
        )
        if candidates:
            self._record_activity_event(
                area="automation",
                event_type=f"automation.{trigger}.scheduled",
                level="info",
                title="自动连接任务已排队",
                detail=f"{trigger} 阶段共有 {len(candidates)} 个候选设备待尝试。",
                details={"trigger": trigger, "deviceIds": [device.device_id for device in candidates]},
            )
        for device in candidates:
            if getattr(device, "connection_state", "disconnected") == "connected":
                return

            try:
                self._connect_service_device(device.device_id, trigger=trigger)
            except Exception as exc:
                self._record_exception(
                    area="automation",
                    event_type=f"automation.{trigger}.failed",
                    title="自动连接执行失败",
                    exc=exc,
                    device_id=device.device_id,
                    details={"trigger": trigger},
                )
                self.handle_service_event(
                    {
                        "event": "device_connection_failed",
                        "device_id": device.device_id,
                        "state": "error",
                        "trigger": trigger,
                    }
                )
                continue

            known_device = getattr(self.service, "known_devices", {}).get(device.device_id)
            if device.device_id in getattr(self.service, "active_connections", {}):
                return
            if known_device is not None and getattr(known_device, "connection_state", None) == "connected":
                return

    def _connect_service_device(self, device_id: str, *, trigger: str) -> None:
        connect = getattr(self.service, "connect")
        try:
            connect(device_id, trigger=trigger)
        except TypeError:
            connect(device_id)

    def _disconnect_service_device(self, device_id: str, *, trigger: str) -> None:
        disconnect = getattr(self.service, "disconnect")
        try:
            disconnect(device_id, trigger=trigger)
        except TypeError:
            disconnect(device_id)

    def _persist_config(self) -> None:
        save_config(self.app_state.config)

    def _record_connection_attempt(self, payload: dict[str, Any]) -> None:
        event_name = payload.get("event")
        if event_name not in {"device_connected", "device_connection_failed"}:
            return
        device_id = payload.get("device_id")
        if not isinstance(device_id, str):
            return

        trigger = payload.get("trigger")
        trigger_name = trigger if isinstance(trigger, str) else "manual"
        succeeded = event_name == "device_connected"
        state = "connected" if succeeded else payload.get("state", "error")
        if not isinstance(state, str):
            state = "error"

        known_device = getattr(self.service, "known_devices", {}).get(device_id)
        device_name = getattr(known_device, "name", device_id)
        language = getattr(self.app_state.config.ui, "language", "system")
        failure_reason = None if succeeded else connection_failure_message(state, language=language)
        failure_code = None if succeeded else f"connection.{state}"

        self._invoke_storage_method(
            "record_connection_attempt",
            device_id=device_id,
            device_name=device_name,
            trigger=trigger_name,
            succeeded=succeeded,
            state=state,
            failure_reason=failure_reason,
            failure_code=failure_code,
            happened_at=datetime.now(UTC),
        )

        if succeeded:
            if trigger_name == "manual":
                self._clear_manual_auto_connect_suppression(device_id)
            existing = [item for item in self.app_state.config.last_devices if item != device_id]
            self.app_state.config.last_devices = [device_id, *existing]
            self._persist_config()

    def _sync_device_cache(self) -> None:
        for device in getattr(self.service, "known_devices", {}).values():
            capabilities = getattr(device, "capabilities", None)
            self._invoke_storage_method(
                "upsert_device_cache",
                device_id=device.device_id,
                name=device.name,
                connection_state=device.connection_state,
                supports_audio_playback=bool(
                    getattr(capabilities, "supports_audio_playback", False)
                ),
                supports_microphone=bool(
                    getattr(capabilities, "supports_microphone", False)
                ),
                last_seen_at=device.last_seen_at,
            )

    def _publish_notification(self, payload: dict[str, Any]) -> None:
        event_name = payload.get("event")
        if event_name not in {"device_connected", "device_connection_failed"}:
            return
        device_id = payload.get("device_id")
        if not isinstance(device_id, str):
            return

        known_device = getattr(self.service, "known_devices", {}).get(device_id)
        device_name = getattr(known_device, "name", device_id)
        language = getattr(self.app_state.config.ui, "language", "system")
        trigger = payload.get("trigger")
        trigger_name = trigger if isinstance(trigger, str) else "manual"
        if event_name == "device_connection_failed" and trigger_name == "recover":
            if self._has_pending_recover_job(device_id):
                return
        if event_name == "device_connected":
            title, body = notification_copy(
                "connect_success",
                language=language,
                device_name=device_name,
            )
            self.notification_service.publish_success(title, body)
            return

        state = payload.get("state", "error")
        if not isinstance(state, str):
            state = "error"
        reason = connection_failure_message(state, language=language)
        title, body = notification_copy(
            "connect_failed",
            language=language,
            device_name=device_name,
            reason=reason,
        )
        self.notification_service.publish_failure(title, body)

    def _record_service_activity(self, payload: dict[str, Any]) -> None:
        event_name = payload.get("event")
        device_id = payload.get("device_id")
        device_name = getattr(
            getattr(self.service, "known_devices", {}).get(device_id),
            "name",
            device_id,
        )
        trigger = payload.get("trigger")
        trigger_name = trigger if isinstance(trigger, str) else "manual"
        state = payload.get("state")
        if event_name == "device_connected":
            self._record_activity_event(
                area="connection",
                event_type="connection.connected",
                level="info",
                title="连接成功",
                detail=f"{device_name} 已通过 {trigger_name} 建立连接。",
                device_id=device_id if isinstance(device_id, str) else None,
                details={"trigger": trigger_name},
            )
        elif event_name == "device_connection_failed":
            self._record_activity_event(
                area="connection",
                event_type="connection.failed",
                level="error",
                title="连接失败",
                detail=(
                    f"{device_name} 连接失败：{connection_failure_message(str(state), language=getattr(self.app_state.config.ui, 'language', 'system'))}"
                    if isinstance(device_name, str)
                    else "设备连接失败。"
                ),
                device_id=device_id if isinstance(device_id, str) else None,
                error_code=f"connection.{state}" if isinstance(state, str) else None,
                details={"trigger": trigger_name, "state": state},
            )
        elif event_name == "device_disconnected":
            self._record_activity_event(
                area="connection",
                event_type="connection.disconnected",
                level="info",
                title="连接已断开",
                detail=f"{device_name} 已断开连接。",
                device_id=device_id if isinstance(device_id, str) else None,
                details={"trigger": trigger_name},
            )
        elif event_name == "device_presence_changed":
            present = payload.get("present")
            self._record_activity_event(
                area="device",
                event_type="device.present" if present else "device.absent",
                level="info",
                title="设备已出现" if present else "设备已离线",
                detail=f"{device_name} {'重新出现在扫描结果中' if present else '已从扫描结果中消失'}。",
                device_id=device_id if isinstance(device_id, str) else None,
                details={
                    "change": payload.get("change"),
                    "previousPresent": payload.get("previous_present"),
                },
            )
        elif event_name == "device_watcher_enumeration_completed":
            self._record_activity_event(
                area="watcher",
                event_type="watcher.enumeration.completed",
                level="info",
                title="设备首轮发现已完成",
                detail="蓝牙音频设备首轮发现完成，后续将持续监听设备出现与离线事件。",
            )
        elif event_name == "devices_refreshed":
            self._record_activity_event(
                area="device",
                event_type="device.refresh.cache_updated",
                level="info",
                title="设备缓存已刷新",
                detail="连接服务已完成一次设备刷新。",
                details={"deviceIds": payload.get("device_ids")},
            )

    def _record_activity_event(
        self,
        *,
        area: str,
        event_type: str,
        level: str,
        title: str,
        detail: str | None = None,
        device_id: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self.observability is not None and hasattr(self.observability, "record_event"):
            self.observability.record_event(
                area=area,
                event_type=event_type,
                level=level,
                title=title,
                detail=detail,
                device_id=device_id,
                error_code=error_code,
                details=details,
            )
            return

        self._invoke_storage_method(
            "record_activity_event",
            area=area,
            event_type=event_type,
            level=level,
            title=title,
            detail=detail,
            device_id=device_id,
            error_code=error_code,
            details=details,
        )

    def _record_exception(
        self,
        *,
        area: str,
        event_type: str,
        title: str,
        exc: BaseException,
        device_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self.observability is not None and hasattr(self.observability, "record_exception"):
            self.observability.record_exception(
                area=area,
                event_type=event_type,
                title=title,
                exc=exc,
                device_id=device_id,
                details=details,
            )
            return
        self._record_activity_event(
            area=area,
            event_type=event_type,
            level="error",
            title=title,
            detail=f"{type(exc).__name__}: {exc}",
            device_id=device_id,
            error_code=type(exc).__name__,
            details=details,
        )

    def _handle_auto_connect_event(self, payload: dict[str, Any]) -> None:
        event_name = payload.get("event")
        device_id = payload.get("device_id")
        trigger = payload.get("trigger")
        trigger_name = trigger if isinstance(trigger, str) else "manual"

        if event_name == "device_connected":
            if isinstance(device_id, str):
                self._cancel_recover_job(device_id)
                if trigger_name == "recover":
                    self._record_recover_result(device_id, succeeded=True)
            return

        if event_name == "device_connection_failed":
            if isinstance(device_id, str) and trigger_name == "recover":
                self._handle_recover_failure(device_id, state=payload.get("state"))
            return

        if event_name == "device_disconnected":
            if not isinstance(device_id, str) or trigger_name == "manual":
                return
            self._start_recover_flow(device_id)
            return

        if event_name == "device_state_changed":
            state = payload.get("state")
            if isinstance(device_id, str) and state == "disconnected":
                self._start_recover_flow(device_id)
            return

        if event_name == "device_watcher_enumeration_completed":
            if self._startup_auto_connect_completed:
                return
            devices = list(getattr(self.service, "known_devices", {}).values())
            self._attempt_auto_connect(trigger="startup", devices=devices)
            self._startup_auto_connect_completed = True
            return

        if event_name != "device_presence_changed":
            return
        present = payload.get("present")
        previous_present = payload.get("previous_present")
        if not isinstance(device_id, str) or not isinstance(present, bool) or not isinstance(previous_present, bool):
            return
        if not present:
            self._cancel_recover_job(device_id)
            return
        if not self._startup_auto_connect_completed:
            return
        if not present or previous_present:
            return

        device = getattr(self.service, "known_devices", {}).get(device_id)
        if device is None:
            return
        self._attempt_auto_connect(trigger="reappear", devices=[device])

    def _schedule_retry(self, delay: float, callback: Callable[[], None]) -> object:
        """默认用 daemon Timer 安排后续 recovery 重试。"""
        timer = Timer(delay, callback)
        timer.daemon = True
        timer.start()
        return timer

    def _start_recover_flow(self, device_id: str) -> None:
        device = getattr(self.service, "known_devices", {}).get(device_id)
        if device is None:
            self._cancel_recover_job(device_id)
            return
        if not getattr(device, "present_in_last_scan", True):
            self._cancel_recover_job(device_id)
            return
        if device_id in self._manual_disconnect_suppressed_devices:
            self._cancel_recover_job(device_id)
            self._record_activity_event(
                area="automation",
                event_type="automation.recover.skipped.manual_override",
                level="info",
                title="已跳过异常断联自动回连",
                detail=f"{device.name} 刚被手动断开，本次运行内不再自动恢复连接。",
                device_id=device_id,
            )
            return
        candidates = RulesEngine(
            self.app_state.config,
            suppressed_device_ids=self._manual_disconnect_suppressed_devices,
        ).get_auto_connect_candidates(
            devices=[device],
            trigger="recover",
        )
        if not candidates:
            self._cancel_recover_job(device_id)
            return
        token = self._create_recover_job(device_id)
        self._record_activity_event(
            area="automation",
            event_type="automation.recover.scheduled",
            level="info",
            title="异常断联自动回连已开始",
            detail=f"{device.name} 已进入异常断联恢复队列，将立即发起第一次回连。",
            device_id=device_id,
        )
        self._run_recover_attempt(device_id, token)

    def _handle_recover_failure(self, device_id: str, *, state: object) -> None:
        with self._recover_lock:
            job = self._pending_recover_jobs.get(device_id)
            if job is None:
                return
            if job.next_retry_index >= len(_RECOVER_RETRY_DELAYS_SECONDS):
                self._pending_recover_jobs.pop(device_id, None)
                should_schedule = False
                next_delay = None
            else:
                next_delay = _RECOVER_RETRY_DELAYS_SECONDS[job.next_retry_index]
                job.next_retry_index += 1
                should_schedule = True
        if not should_schedule:
            self._record_recover_result(device_id, succeeded=False, state=state)
            return
        self._record_activity_event(
            area="automation",
            event_type="automation.recover.retrying",
            level="warning",
            title="异常断联自动回连重试中",
            detail=f"{device_id} 将在 {int(next_delay)} 秒后继续自动回连。",
            device_id=device_id,
            details={"nextDelaySeconds": next_delay},
        )
        handle = self._retry_scheduler(
            next_delay,
            lambda device_id=device_id, token=job.token: self._run_recover_attempt(device_id, token),
        )
        with self._recover_lock:
            current_job = self._pending_recover_jobs.get(device_id)
            if current_job is None or current_job.token != job.token:
                cancel = getattr(handle, "cancel", None)
                if callable(cancel):
                    cancel()
                return
            current_job.handle = handle

    def _run_recover_attempt(self, device_id: str, token: int) -> None:
        if not self._is_recover_job_current(device_id, token):
            return
        try:
            self._connect_service_device(device_id, trigger="recover")
        except Exception as exc:
            self._record_exception(
                area="automation",
                event_type="automation.recover.failed",
                title="异常断联自动回连执行失败",
                exc=exc,
                device_id=device_id,
                details={"trigger": "recover"},
            )
            self.handle_service_event(
                {
                    "event": "device_connection_failed",
                    "device_id": device_id,
                    "state": "error",
                    "trigger": "recover",
                }
            )

    def _record_recover_result(self, device_id: str, *, succeeded: bool, state: object | None = None) -> None:
        device = getattr(self.service, "known_devices", {}).get(device_id)
        device_name = getattr(device, "name", device_id)
        if succeeded:
            self._record_activity_event(
                area="connection",
                event_type="connection.recover.succeeded",
                level="info",
                title="异常断联自动回连成功",
                detail=f"{device_name} 已在异常断联后自动恢复连接。",
                device_id=device_id,
            )
            return
        self._record_activity_event(
            area="connection",
            event_type="connection.recover.exhausted",
            level="error",
            title="异常断联自动回连已停止",
            detail=f"{device_name} 在 3 次自动回连后仍未恢复连接，已停止本轮重试。",
            device_id=device_id,
            error_code=f"connection.{state}" if isinstance(state, str) else None,
        )

    def _create_recover_job(self, device_id: str) -> int:
        with self._recover_lock:
            self._recover_sequence += 1
            token = self._recover_sequence
            self._cancel_recover_job_locked(device_id)
            self._pending_recover_jobs[device_id] = _RecoverJob(token=token)
            return token

    def _cancel_recover_job(self, device_id: str) -> None:
        with self._recover_lock:
            self._cancel_recover_job_locked(device_id)

    def _cancel_recover_job_locked(self, device_id: str) -> None:
        job = self._pending_recover_jobs.pop(device_id, None)
        if job is None:
            return
        cancel = getattr(job.handle, "cancel", None)
        if callable(cancel):
            cancel()

    def _has_pending_recover_job(self, device_id: str) -> bool:
        with self._recover_lock:
            return device_id in self._pending_recover_jobs

    def _is_recover_job_current(self, device_id: str, token: int) -> bool:
        with self._recover_lock:
            if self._recover_shutdown:
                return False
            job = self._pending_recover_jobs.get(device_id)
            return job is not None and job.token == token

    def _suppress_manual_auto_connect(self, device_id: str) -> None:
        with self._recover_lock:
            self._manual_disconnect_suppressed_devices.add(device_id)

    def _clear_manual_auto_connect_suppression(self, device_id: str) -> None:
        with self._recover_lock:
            self._manual_disconnect_suppressed_devices.discard(device_id)

    def _invoke_storage_method(self, method_name: str, **payload: Any) -> None:
        if self.storage is None:
            return

        method = getattr(self.storage, method_name, None)
        if not callable(method):
            return

        method_signature = signature(method)
        if any(parameter.kind == Parameter.VAR_KEYWORD for parameter in method_signature.parameters.values()):
            method(**payload)
            return

        allowed = {
            key: value
            for key, value in payload.items()
            if key in method_signature.parameters
        }
        method(**allowed)
