from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, Literal

from audio_blue.models import NotificationPolicy

NotificationLevel = Literal["info", "error"]
NotificationSink = Callable[["NotificationMessage"], None]


@dataclass(slots=True)
class NotificationMessage:
    title: str
    body: str
    level: NotificationLevel
    happened_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class NotificationService:
    def __init__(
        self,
        policy: NotificationPolicy = "failures",
        sink: NotificationSink | None = None,
    ) -> None:
        self._policy: NotificationPolicy = self._validate_policy(policy)
        self._sink = sink or (lambda _message: None)

    @property
    def policy(self) -> NotificationPolicy:
        return self._policy

    def update_policy(self, policy: NotificationPolicy) -> None:
        self._policy = self._validate_policy(policy)

    def publish_success(self, title: str, body: str) -> None:
        self._publish(title=title, body=body, level="info")

    def publish_failure(self, title: str, body: str) -> None:
        self._publish(title=title, body=body, level="error")

    def _publish(self, title: str, body: str, level: NotificationLevel) -> None:
        if not self._should_publish(level):
            return

        self._sink(NotificationMessage(title=title, body=body, level=level))

    def _should_publish(self, level: NotificationLevel) -> bool:
        if self._policy == "silent":
            return False
        if self._policy == "all":
            return True
        return level == "error"

    @staticmethod
    def _validate_policy(policy: str) -> NotificationPolicy:
        if policy not in {"silent", "failures", "all"}:
            raise ValueError(f"Unsupported notification policy: {policy}")
        return policy
