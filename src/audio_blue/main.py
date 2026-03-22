"""Application entry point for AudioBlue."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from logging import Logger
import os

from audio_blue.config import get_config_path, load_config
from audio_blue.connector_service import ConnectorService
from audio_blue.desktop_host import DesktopApi, DesktopHost, find_ui_entrypoint
from audio_blue.diagnostics import export_diagnostics_snapshot
from audio_blue.logging_util import configure_logging
from audio_blue.app_state import AppStateStore
from audio_blue.autostart_manager import AutostartManager
from audio_blue.notification_service import NotificationService
from audio_blue.single_instance import SingleInstanceManager
from audio_blue.tray_host import TrayHost


def restore_reconnect_devices(
    service: ConnectorService,
    config,
    logger: Logger,
) -> None:
    if not config.reconnect or not config.last_devices:
        return

    service.refresh_devices()
    for device_id in config.last_devices:
        try:
            service.connect(device_id)
        except Exception:
            logger.exception("Failed to reconnect device %s", device_id)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AudioBlue desktop host")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start hidden and stay in the system tray.",
    )
    return parser.parse_args(argv)


def create_default_host(
    *,
    service,
    config,
    logger,
    background: bool,
):
    try:
        import webview  # type: ignore[import-not-found]

        ui_entrypoint = find_ui_entrypoint()
        desktop_api = DesktopApi(
            service=service,
            app_state=AppStateStore(config=config),
            autostart_manager=AutostartManager(),
            notification_service=NotificationService(policy=config.notification.policy),
            diagnostics_exporter=export_diagnostics_snapshot,
            open_bluetooth_settings=lambda: os.startfile("ms-settings:bluetooth"),
            diagnostics_output_dir=get_config_path().parent / "diagnostics",
        )
        desktop_host = DesktopHost(api=desktop_api, ui_entrypoint=ui_entrypoint, webview_module=webview)
        return TrayHost(
            service=service,
            config=config,
            logger=logger,
            background=background,
            show_quick_panel=desktop_host.show_quick_panel,
            show_main_window=desktop_host.show_main_window,
        )
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        logger.warning("Hybrid desktop UI unavailable (%s). Falling back to tray-only mode.", exc)
        return TrayHost(
            service=service,
            config=config,
            logger=logger,
            background=background,
        )


def run_app(
    *,
    background: bool,
    instance_manager: SingleInstanceManager,
    service_factory=ConnectorService,
    host_factory=create_default_host,
    config=None,
    logger: Logger | None = None,
) -> int:
    if not instance_manager.acquire():
        return 0

    app_config = config or load_config()
    app_logger = logger or configure_logging(get_config_path().with_name("audioblue.log"))

    try:
        service = service_factory()
        restore_reconnect_devices(service=service, config=app_config, logger=app_logger)

        host = host_factory(
            service=service,
            config=app_config,
            logger=app_logger,
            background=background,
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
