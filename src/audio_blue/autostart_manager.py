from __future__ import annotations

from pathlib import Path
from typing import Protocol
import winreg


class RegistryValueStore(Protocol):
    """抽象注册表读写能力，便于测试时替换真实注册表访问。"""

    def get_value(self, key_path: str, value_name: str) -> str | None: ...

    def set_value(self, key_path: str, value_name: str, value: str) -> None: ...

    def delete_value(self, key_path: str, value_name: str) -> None: ...


class WinRegistryValueStore:
    """直接对接 Windows 注册表的默认实现。"""

    def get_value(self, key_path: str, value_name: str) -> str | None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
        except FileNotFoundError:
            return None
        return value if isinstance(value, str) else None

    def set_value(self, key_path: str, value_name: str, value: str) -> None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value)

    def delete_value(self, key_path: str, value_name: str) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, value_name)
        except FileNotFoundError:
            return


class AutostartManager:
    """管理 AudioBlue 在当前用户下的开机自启动注册表项。"""

    RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "AudioBlue"

    def __init__(
        self,
        registry: RegistryValueStore | None = None,
        executable_path: Path | None = None,
    ) -> None:
        self._registry = registry or WinRegistryValueStore()
        self._executable_path = executable_path

    def is_enabled(self) -> bool:
        """通过 Run 键是否存在来判断自启动开关。"""
        return self._registry.get_value(self.RUN_KEY_PATH, self.APP_NAME) is not None

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._registry.set_value(
                self.RUN_KEY_PATH,
                self.APP_NAME,
                self.build_command(),
            )
            return

        self._registry.delete_value(self.RUN_KEY_PATH, self.APP_NAME)

    def build_command(self) -> str:
        """根据可执行文件路径拼接带后台启动参数的命令字符串。"""
        executable = self._executable_path or Path(__file__).resolve().parents[2] / "audioblue.exe"
        return build_autostart_command(executable)


def build_autostart_command(executable_path: Path | str) -> str:
    """生成写入注册表的自启动命令行。"""
    return f'"{executable_path}" --background'
