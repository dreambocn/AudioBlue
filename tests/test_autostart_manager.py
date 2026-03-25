"""验证自启动管理器如何读写注册表命令。"""

from pathlib import Path

from audio_blue.autostart_manager import AutostartManager, RegistryValueStore


class FakeRegistry(RegistryValueStore):
    """以内存字典代替注册表，避免测试触碰真实系统设置。"""

    def __init__(self):
        self.values: dict[tuple[str, str], str] = {}

    def get_value(self, key_path: str, value_name: str) -> str | None:
        return self.values.get((key_path, value_name))

    def set_value(self, key_path: str, value_name: str, value: str) -> None:
        self.values[(key_path, value_name)] = value

    def delete_value(self, key_path: str, value_name: str) -> None:
        self.values.pop((key_path, value_name), None)


def test_autostart_manager_builds_background_command_and_toggles_registry():
    registry = FakeRegistry()
    manager = AutostartManager(
        registry=registry,
        executable_path=Path(r"C:\Apps\AudioBlue\audioblue.exe"),
    )

    manager.set_enabled(True)

    assert manager.is_enabled() is True
    assert registry.values[
        (
            manager.RUN_KEY_PATH,
            manager.APP_NAME,
        )
    ] == '"C:\\Apps\\AudioBlue\\audioblue.exe" --background'

    manager.set_enabled(False)

    assert manager.is_enabled() is False
    assert registry.values == {}
