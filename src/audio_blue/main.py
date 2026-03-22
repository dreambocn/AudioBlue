"""Application entry point for AudioBlue."""

from __future__ import annotations

from pathlib import Path

from audio_blue.config import get_config_path, load_config
from audio_blue.connector_service import ConnectorService
from audio_blue.logging_util import configure_logging
from audio_blue.tray_host import TrayHost


def main() -> int:
    config = load_config()
    logger = configure_logging(get_config_path().with_name("audioblue.log"))
    service = ConnectorService()
    host = TrayHost(service=service, config=config, logger=logger)

    for device_id in config.last_devices if config.reconnect else []:
        try:
            service.connect(device_id)
        except Exception:
            logger.exception("Failed to reconnect device %s", device_id)

    host.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
