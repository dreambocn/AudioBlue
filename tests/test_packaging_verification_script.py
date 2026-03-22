from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_packaging_assets.py"
    spec = spec_from_file_location("verify_packaging_assets", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_packaging_report_flags_missing_assets(tmp_path):
    module = load_module()
    dist_root = tmp_path / "dist"
    installer_script = tmp_path / "installer" / "AudioBlue.iss"

    report = module.collect_packaging_report(dist_root=dist_root, installer_script=installer_script)

    assert report["ok"] is False
    assert any("audioblue.exe" in issue for issue in report["issues"])
    assert any("AudioBlue.iss" in issue for issue in report["issues"])


def test_collect_packaging_report_passes_for_minimum_valid_layout(tmp_path):
    module = load_module()

    dist_root = tmp_path / "dist"
    app_dir = dist_root / "AudioBlue"
    app_dir.mkdir(parents=True)
    (app_dir / "audioblue.exe").write_text("stub", encoding="utf-8")
    (app_dir / "ui").mkdir()
    (app_dir / "ui" / "index.html").write_text("<html></html>", encoding="utf-8")

    installer_script = tmp_path / "installer" / "AudioBlue.iss"
    installer_script.parent.mkdir(parents=True)
    installer_script.write_text(
        """
[Setup]
AppName=AudioBlue

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueData: """ + '"""{app}\\audioblue.exe --background"""',
        encoding="utf-8",
    )

    report = module.collect_packaging_report(dist_root=dist_root, installer_script=installer_script)

    assert report["ok"] is True
    assert report["issues"] == []


def test_main_returns_nonzero_when_assets_invalid(tmp_path):
    module = load_module()

    code = module.main(
        [
            "--dist-root",
            str(tmp_path / "dist"),
            "--installer-script",
            str(tmp_path / "installer" / "AudioBlue.iss"),
            "--format",
            "text",
        ]
    )

    assert code == 1
