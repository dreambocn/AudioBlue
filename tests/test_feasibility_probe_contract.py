from importlib.util import module_from_spec, spec_from_file_location
"""覆盖可行性探测脚本的输出契约。"""

from pathlib import Path


def load_probe_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "feasibility_probe.py"
    spec = spec_from_file_location("feasibility_probe", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_probe_returns_expected_contract():
    module = load_probe_module()

    result = module.run_probe()

    assert set(result) == {
        "audio_namespace_available",
        "enumeration_namespace_available",
        "device_selector",
        "matched_device_count",
        "devices",
        "errors",
    }
    assert isinstance(result["audio_namespace_available"], bool)
    assert isinstance(result["enumeration_namespace_available"], bool)
    assert result["device_selector"] is None or isinstance(result["device_selector"], str)
    assert isinstance(result["matched_device_count"], int)
    assert isinstance(result["devices"], list)
    assert isinstance(result["errors"], list)


def test_run_probe_uses_runtime_selector_with_aqs_filter(monkeypatch):
    module = load_probe_module()
    observed: dict[str, str] = {}

    class ImmediateAwaitable:
        def __init__(self, value):
            self._value = value

        def __await__(self):
            async def _inner():
                return self._value

            return _inner().__await__()

    class DeviceStub:
        def __init__(self, device_id: str, name: str):
            self.id = device_id
            self.name = name

    class DeviceInformationStub:
        @staticmethod
        def find_all_async_aqs_filter(selector: str):
            observed["selector"] = selector
            return ImmediateAwaitable(
                [
                    DeviceStub("id-1", "Headphones"),
                    DeviceStub("id-2", "Phone"),
                ]
            )

    class AudioPlaybackConnectionStub:
        @staticmethod
        def get_device_selector() -> str:
            return "A2DP-SOURCE-SELECTOR"

    monkeypatch.setattr(
        module,
        "_load_audio_namespace",
        lambda: type("AudioNs", (), {"AudioPlaybackConnection": AudioPlaybackConnectionStub})(),
    )
    monkeypatch.setattr(
        module,
        "_load_enumeration_namespace",
        lambda: type("EnumNs", (), {"DeviceInformation": DeviceInformationStub})(),
    )

    result = module.run_probe()

    assert observed["selector"] == "A2DP-SOURCE-SELECTOR"
    assert result["device_selector"] == "A2DP-SOURCE-SELECTOR"
    assert result["matched_device_count"] == 2
    assert [device["id"] for device in result["devices"]] == ["id-1", "id-2"]
