"""Application entry point for AudioBlue."""

from __future__ import annotations

from pathlib import Path

from audio_blue.config import get_config_path, load_config
from audio_blue.connector_service import ConnectorService
from audio_blue.logging_util import configure_logging
from audio_blue.tray_host import TrayHost


def restore_reconnect_devices(
    service: ConnectorService,
    config,
    logger,
) -> None:
    if not config.reconnect or not config.last_devices:
        return

    service.refresh_devices()
    for device_id in config.last_devices:
        try:
            service.connect(device_id)
        except Exception:
            logger.exception("Failed to reconnect device %s", device_id)


def main() -> int:
    config = load_config()
    logger = configure_logging(get_config_path().with_name("audioblue.log"))
    service = ConnectorService()
    restore_reconnect_devices(service=service, config=config, logger=logger)

    host = TrayHost(service=service, config=config, logger=logger)
    host.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
