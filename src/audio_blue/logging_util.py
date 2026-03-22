from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_path: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("audio_blue")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler: logging.Handler
    if log_path is None:
        handler = logging.StreamHandler()
    else:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
