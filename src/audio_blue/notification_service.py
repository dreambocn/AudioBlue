from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, Literal

from audio_blue.models import NotificationPolicy

NotificationLevel = Literal["info", "error"]
NotificationSink = Callable[["NotificationMessage"], None]


@dataclass(slots=True)
class NotificationMessage:
    """统一描述一次可投递的通知消息。"""

    title: str
    body: str
    level: NotificationLevel
    happened_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class NotificationService:
    """按用户通知策略过滤并分发通知。"""

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
        """更新通知策略时保持和初始化阶段一致的校验规则。"""
        self._policy = self._validate_policy(policy)

    def publish_success(self, title: str, body: str) -> None:
        self._publish(title=title, body=body, level="info")

    def publish_failure(self, title: str, body: str) -> None:
        self._publish(title=title, body=body, level="error")

    def _publish(self, title: str, body: str, level: NotificationLevel) -> None:
        if not self._should_publish(level):
            return

        # 统一通过 sink 交给外部实现，保持通知入口的可替换性。
        self._sink(NotificationMessage(title=title, body=body, level=level))

    def _should_publish(self, level: NotificationLevel) -> bool:
        """把策略判断收敛在一处，避免调用方自行分支。"""
        if self._policy == "silent":
            return False
        if self._policy == "all":
            return True
        return level == "error"

    @staticmethod
    def _validate_policy(policy: str) -> NotificationPolicy:
        """只接受前后端约定过的通知策略枚举值。"""
        if policy not in {"silent", "failures", "all"}:
            raise ValueError(f"Unsupported notification policy: {policy}")
        return policy
