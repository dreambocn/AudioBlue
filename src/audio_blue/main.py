"""AudioBlue 桌面程序入口，负责组装运行时依赖并选择宿主模式。"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from logging import Logger
import os
from threading import Lock, Thread
from time import sleep
from typing import Any

from audio_blue.config import get_config_path, load_config
from audio_blue.connector_service import ConnectorService
from audio_blue.desktop_host import DesktopApi, DesktopHost, find_ui_entrypoint
from audio_blue.diagnostics import export_diagnostics_snapshot
from audio_blue.logging_util import configure_logging
from audio_blue.app_state import AppStateStore
from audio_blue.autostart_manager import AutostartManager
from audio_blue.notification_service import NotificationService
from audio_blue.observability import ObservabilityService
from audio_blue.rules_engine import RulesEngine
from audio_blue.session_state import SessionStateCoordinator
from audio_blue.single_instance import SingleInstanceManager
from audio_blue.tray_host import TrayHost


def _resolve_runtime_storage(logger: Logger) -> Any | None:
    """尽力解析运行时存储实现；失败时退回无持久化模式。"""
    try:
        from audio_blue import storage as storage_module
    except Exception:
        return None

    candidates = [
        getattr(storage_module, "get_storage", None),
        getattr(storage_module, "get_default_storage", None),
        getattr(storage_module, "default_storage", None),
        getattr(storage_module, "storage", None),
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            storage = candidate() if callable(candidate) else candidate
            initialize = getattr(storage, "initialize", None)
            if callable(initialize):
                initialize()
            return storage
        except Exception:
            logger.exception("Failed to initialize runtime storage from %r", candidate)
            return None
    return None


def restore_reconnect_devices(
    service: ConnectorService,
    config,
    logger: Logger,
    *,
    observability: ObservabilityService | None = None,
    initial_delay_seconds: float = 0,
    retry_attempts: int = 0,
    retry_backoff_seconds: float = 0.5,
    wait_timeout_seconds: float = 5.0,
) -> None:
    """在启动阶段尝试恢复上次可重连设备。"""
    if not getattr(config, "reconnect", False):
        return
    if observability is not None:
        observability.record_event(
            area="automation",
            event_type="automation.startup_restore.started",
            level="info",
            title="启动自动重连已开始",
            detail="应用启动后开始尝试恢复上次连接设备。",
        )
    if initial_delay_seconds > 0:
        sleep(initial_delay_seconds)

    wait_for_initial_enumeration = getattr(service, "wait_for_initial_enumeration", None)
    if callable(wait_for_initial_enumeration):
        try:
            wait_for_initial_enumeration(wait_timeout_seconds)
        except TypeError:
            wait_for_initial_enumeration()

    total_attempts = max(retry_attempts, 0) + 1
    for attempt_index in range(total_attempts):
        refreshed_devices = service.refresh_devices()
        devices = list(getattr(service, "known_devices", {}).values()) or list(refreshed_devices or [])
        if devices:
            candidates = RulesEngine(config).get_auto_connect_candidates(
                devices=devices,
                trigger="startup",
            )
            for device in candidates:
                try:
                    try:
                        service.connect(device.device_id, trigger="startup")
                    except TypeError:
                        service.connect(device.device_id)
                except Exception as exc:
                    if observability is not None:
                        observability.record_exception(
                            area="automation",
                            event_type="automation.startup_restore.failed",
                            title="启动自动重连失败",
                            exc=exc,
                            device_id=device.device_id,
                            details={"trigger": "startup"},
                        )
                    logger.exception("Failed to auto-connect device %s during startup", device.device_id)
                    continue
                if device.device_id in getattr(service, "active_connections", {}):
                    if observability is not None:
                        observability.record_event(
                            area="connection",
                            event_type="connection.startup_restore.succeeded",
                            level="info",
                            title="启动自动重连成功",
                            detail=f"{device.name} 已在启动阶段恢复连接。",
                            device_id=device.device_id,
                            details={"trigger": "startup"},
                        )
                    return
        if attempt_index < total_attempts - 1 and retry_backoff_seconds > 0:
            sleep(retry_backoff_seconds)
    if observability is not None:
        observability.record_event(
            area="automation",
            event_type="automation.startup_restore.exhausted",
            level="warning",
            title="启动自动重连未命中可用设备",
            detail="启动阶段已完成有限重试，但未恢复任何连接。",
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AudioBlue desktop host")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start hidden and stay in the system tray.",
    )
    return parser.parse_args(argv)


def is_hybrid_ui_unavailable_error(exc: BaseException) -> bool:
    try:
        from webview.errors import WebViewException  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        WebViewException = tuple()  # type: ignore[assignment]

    if isinstance(exc, (FileNotFoundError, ModuleNotFoundError, ImportError)):
        return True
    if WebViewException and isinstance(exc, WebViewException):
        return True

    message = f"{type(exc).__module__}.{type(exc).__name__}: {exc}".lower()
    indicators = (
        "webview2",
        "pywebview",
        "pythonnet",
        "microsoft.web.webview2",
        "edgechromium",
        "run `npm run build`",
        "could not find built audioblue ui entrypoint",
        "clr",
    )
    return any(indicator in message for indicator in indicators)


class HybridAppHost:
    """优先启动混合桌面界面，失败时自动降级到托盘模式。"""

    def __init__(
        self,
        *,
        desktop_host: DesktopHost,
        tray_host_factory,
        fallback_host_factory,
        logger: Logger,
    ) -> None:
        self._desktop_host = desktop_host
        self._tray_host_factory = tray_host_factory
        self._fallback_host_factory = fallback_host_factory
        self._logger = logger
        self._tray_thread: Thread | None = None
        self._tray_lock = Lock()

    def _start_tray_host(self) -> None:
        """确保托盘宿主只被启动一次。"""
        with self._tray_lock:
            if self._tray_thread is not None:
                return

            tray_host = self._tray_host_factory()
            self._tray_thread = Thread(target=tray_host.run, name="audio-blue-tray", daemon=True)
            self._tray_thread.start()

    def run(self) -> None:
        try:
            self._desktop_host.run(on_started=self._start_tray_host)
        except Exception as exc:
            if not is_hybrid_ui_unavailable_error(exc):
                raise
            self._logger.warning("Hybrid desktop UI unavailable (%s). Falling back to tray-only mode.", exc)
            fallback_host = self._fallback_host_factory()
            fallback_host.run()


def create_default_host(
    *,
    service,
    config,
    logger,
    background: bool,
    storage=None,
    observability: ObservabilityService | None = None,
):
    """按当前环境装配默认宿主、状态协调器与诊断能力。"""
    app_state = AppStateStore(config=config, history_provider=storage)
    autostart_manager = AutostartManager()
    notification_service = NotificationService(policy=config.notification.policy)
    runtime_observability = observability or ObservabilityService(storage=storage, logger=logger)
    session_state = SessionStateCoordinator(
        service=service,
        app_state=app_state,
        autostart_manager=autostart_manager,
        notification_service=notification_service,
        storage=storage,
        observability=runtime_observability,
    )

    def build_tray_only_host() -> TrayHost:
        return TrayHost(
            service=service,
            config=config,
            logger=logger,
            background=background,
            session_state=session_state,
            observability=runtime_observability,
        )

    try:
        import webview  # type: ignore[import-not-found]

        ui_entrypoint = find_ui_entrypoint()
        desktop_api = DesktopApi(
            service=service,
            app_state=app_state,
            autostart_manager=autostart_manager,
            notification_service=notification_service,
            diagnostics_exporter=export_diagnostics_snapshot,
            open_bluetooth_settings=lambda: os.startfile("ms-settings:bluetooth"),
            diagnostics_output_dir=get_config_path().parent / "diagnostics",
            session_state=session_state,
            support_bundle_exporter=lambda snapshot, path: runtime_observability.export_support_bundle(snapshot=snapshot, path=path),
            observability=runtime_observability,
        )
        desktop_host = DesktopHost(api=desktop_api, ui_entrypoint=ui_entrypoint, webview_module=webview)
        return HybridAppHost(
            desktop_host=desktop_host,
            tray_host_factory=lambda: TrayHost(
                service=service,
                config=config,
                logger=logger,
                background=background,
                show_main_window=desktop_host.show_main_window,
                shutdown_ui=desktop_host.shutdown,
                session_state=session_state,
                observability=runtime_observability,
            ),
            fallback_host_factory=build_tray_only_host,
            logger=logger,
        )
    except (FileNotFoundError, ModuleNotFoundError, ImportError) as exc:
        logger.warning("Hybrid desktop UI unavailable (%s). Falling back to tray-only mode.", exc)
        return build_tray_only_host()


def run_app(
    *,
    background: bool,
    instance_manager: SingleInstanceManager,
    service_factory=ConnectorService,
    host_factory=create_default_host,
    config=None,
    logger: Logger | None = None,
    storage=None,
) -> int:
    if not instance_manager.acquire():
        return 0

    app_config = config or load_config()
    app_logger = logger or configure_logging(get_config_path().with_name("audioblue.log"))

    try:
        service = service_factory()
        runtime_storage = storage or _resolve_runtime_storage(app_logger)
        observability = ObservabilityService(storage=runtime_storage, logger=app_logger)
        observability.record_event(
            area="runtime",
            event_type="runtime.app.started",
            level="info",
            title="应用已启动",
            detail=f"当前以{'后台' if background else '前台'}模式启动。",
        )
        restore_reconnect_devices(
            service=service,
            config=app_config,
            logger=app_logger,
            observability=observability,
            initial_delay_seconds=(
                app_config.startup.launch_delay_seconds
                if background
                else 0
            ),
            retry_attempts=2 if background else 0,
            retry_backoff_seconds=1.0 if background else 0,
        )

        host = host_factory(
            service=service,
            config=app_config,
            logger=app_logger,
            background=background,
            storage=runtime_storage,
            observability=observability,
        )
        host.run()
        return 0
    finally:
        instance_manager.release()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return run_app(
        background=args.background,
        instance_manager=SingleInstanceManager(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
