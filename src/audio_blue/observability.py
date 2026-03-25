from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from audio_blue.diagnostics import export_support_bundle


class ObservabilityService:
    def __init__(self, *, storage=None, logger: logging.Logger | None = None) -> None:
        self._storage = storage
        self._logger = logger

    def record_event(
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
        storage_method = getattr(self._storage, "record_activity_event", None)
        if callable(storage_method):
            storage_method(
                area=area,
                event_type=event_type,
                level=level,
                title=title,
                detail=detail,
                device_id=device_id,
                error_code=error_code,
                details=details,
            )

        if self._logger is None:
            return

        message = title if not detail else f"{title} | {detail}"
        if level == "error":
            self._logger.error(message)
        elif level == "warning":
            self._logger.warning(message)
        else:
            self._logger.info(message)

    def record_exception(
        self,
        *,
        area: str,
        event_type: str,
        title: str,
        exc: BaseException,
        device_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.record_event(
            area=area,
            event_type=event_type,
            level="error",
            title=title,
            detail=f"{type(exc).__name__}: {exc}",
            device_id=device_id,
            error_code=type(exc).__name__,
            details=details,
        )

    def export_support_bundle(self, *, snapshot: dict[str, Any], path: Path) -> Path:
        return export_support_bundle(snapshot=snapshot, path=path, storage=self._storage)
