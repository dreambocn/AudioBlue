from importlib.util import module_from_spec, spec_from_file_location
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
        "devices",
        "errors",
    }
    assert isinstance(result["audio_namespace_available"], bool)
    assert isinstance(result["enumeration_namespace_available"], bool)
    assert result["device_selector"] is None or isinstance(result["device_selector"], str)
    assert isinstance(result["devices"], list)
    assert isinstance(result["errors"], list)
