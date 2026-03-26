"""覆盖图标资源在仓库中的存在性契约。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    assert path.exists(), f"Expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def test_icon_assets_exist_for_web_and_windows_runtime():
    expected_paths = [
        REPO_ROOT / "assets" / "branding" / "audioblue-icon.svg",
        REPO_ROOT / "assets" / "branding" / "audioblue-icon.ico",
        REPO_ROOT / "assets" / "branding" / "audioblue-icon-512.png",
        REPO_ROOT / "ui" / "public" / "favicon.svg",
    ]

    for path in expected_paths:
        assert path.exists(), f"Expected branding asset: {path}"


def test_pyinstaller_spec_includes_custom_icon_and_branding_assets():
    content = read_text(REPO_ROOT / "AudioBlue.spec")

    assert "('assets\\\\branding', 'assets\\\\branding')" in content
    assert "icon='assets\\\\branding\\\\audioblue-icon.ico'" in content


def test_inno_setup_uses_custom_setup_icon():
    content = read_text(REPO_ROOT / "installer" / "AudioBlue.InstallerCore.iss")

    assert r"SetupIconFile=..\assets\branding\audioblue-icon.ico" in content


def test_tray_host_loads_packaged_custom_icon_with_fallback():
    content = read_text(REPO_ROOT / "src" / "audio_blue" / "tray_host.py")

    assert "find_app_icon_path" in content
    assert "LoadImage" in content
    assert "LR_LOADFROMFILE" in content
    assert "audioblue-icon.ico" in content
