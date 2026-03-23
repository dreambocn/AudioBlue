from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from audio_blue.storage import SQLiteStorage


class SQLiteLogHandler(logging.Handler):
    def __init__(self, storage: SQLiteStorage) -> None:
        super().__init__()
        self._storage = storage

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._storage.record_log(
                level=record.levelname,
                message=record.getMessage(),
                logger_name=record.name,
                created_at=datetime.fromtimestamp(record.created, tz=UTC),
            )
        except Exception:
            self.handleError(record)


def configure_logging(log_path: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("audio_blue")
    if any(isinstance(handler, SQLiteLogHandler) for handler in logger.handlers):
        return logger

    logger.setLevel(logging.INFO)
    storage = _build_storage_for_logging(log_path)
    storage.initialize()
    storage.migrate_legacy_files()
    storage.purge_expired_records()

    handler: logging.Handler = SQLiteLogHandler(storage)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def _build_storage_for_logging(log_path: Path | None) -> SQLiteStorage:
    if log_path is None:
        return SQLiteStorage()
    return SQLiteStorage(
        db_path=log_path.with_name("audioblue.db"),
        legacy_log_path=log_path,
        legacy_config_path=log_path.with_name("config.json"),
        legacy_diagnostics_dir=log_path.with_name("diagnostics"),
    )
