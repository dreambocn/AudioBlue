"""验证单实例协调器在重复启动时的信号与释放行为。"""

from audio_blue.single_instance import InstanceCoordinator, SingleInstanceManager


class MemoryCoordinator(InstanceCoordinator):
    """以内存集合模拟互斥体与激活信号。"""

    def __init__(self):
        self.acquired: set[str] = set()
        self.signaled: list[str] = []

    def try_acquire(self, name: str) -> bool:
        if name in self.acquired:
            return False
        self.acquired.add(name)
        return True

    def signal_existing(self, name: str) -> None:
        self.signaled.append(name)

    def release(self, name: str) -> None:
        self.acquired.discard(name)


def test_second_instance_signals_existing_process():
    coordinator = MemoryCoordinator()
    first = SingleInstanceManager(coordinator=coordinator, name="AudioBlue")
    second = SingleInstanceManager(coordinator=coordinator, name="AudioBlue")

    assert first.acquire() is True
    assert second.acquire() is False
    assert coordinator.signaled == ["AudioBlue"]


def test_release_frees_the_instance_name():
    coordinator = MemoryCoordinator()
    instance = SingleInstanceManager(coordinator=coordinator, name="AudioBlue")

    assert instance.acquire() is True

    instance.release()

    assert "AudioBlue" not in coordinator.acquired
