"""验证通知服务在不同策略下的发布过滤行为。"""

from audio_blue.notification_service import NotificationMessage, NotificationService


def test_policy_silent_blocks_all_notifications():
    published: list[NotificationMessage] = []
    service = NotificationService(policy="silent", sink=published.append)

    service.publish_success("Connected", "Headphones connected")
    service.publish_failure("Connection failed", "Timeout")

    assert published == []


def test_policy_failures_only_publishes_failures():
    published: list[NotificationMessage] = []
    service = NotificationService(policy="failures", sink=published.append)

    service.publish_success("Connected", "Headphones connected")
    service.publish_failure("Connection failed", "Timeout")

    assert [message.level for message in published] == ["error"]
    assert published[0].title == "Connection failed"


def test_policy_all_publishes_success_and_failures():
    published: list[NotificationMessage] = []
    service = NotificationService(policy="all", sink=published.append)

    service.publish_success("Connected", "Headphones connected")
    service.publish_failure("Connection failed", "Timeout")

    assert [message.level for message in published] == ["info", "error"]


def test_update_policy_takes_effect_for_next_publish():
    published: list[NotificationMessage] = []
    service = NotificationService(policy="silent", sink=published.append)

    service.publish_failure("Connection failed", "Timeout")
    service.update_policy("all")
    service.publish_success("Connected", "Headphones connected")

    assert [message.level for message in published] == ["info"]
