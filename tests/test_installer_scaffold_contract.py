"""覆盖安装器脚手架文件的基础存在性契约。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INNO_SCRIPT_PATH = REPO_ROOT / "installer" / "AudioBlue.iss"
INNO_WITH_WEBVIEW2_SCRIPT_PATH = REPO_ROOT / "installer" / "AudioBlue.WithWebView2.iss"
INNO_CORE_SCRIPT_PATH = REPO_ROOT / "installer" / "AudioBlue.InstallerCore.iss"


def read_text(path: Path) -> str:
    assert path.exists(), f"Expected installer scaffold at {path}."
    return path.read_text(encoding="utf-8")


def test_inno_scaffolds_and_core_template_exist():
    assert INNO_SCRIPT_PATH.exists()
    assert INNO_WITH_WEBVIEW2_SCRIPT_PATH.exists()
    assert INNO_CORE_SCRIPT_PATH.exists()


def test_inno_core_contains_required_sections():
    content = read_text(INNO_CORE_SCRIPT_PATH)

    for section in ("[Setup]", "[Tasks]", "[Files]", "[Registry]", "[Icons]", "[Run]", "[Code]"):
        assert section in content


def test_inno_scaffold_declares_expected_tasks_and_defaults():
    content = read_text(INNO_CORE_SCRIPT_PATH)

    assert 'Name: "startmenu"' in content
    assert 'Name: "autostart"' in content
    assert 'Name: "desktopicon"' in content
    assert 'Name: "desktopicon";' in content and "Flags: unchecked" in content


def test_inno_scaffold_wires_background_autostart_command():
    content = read_text(INNO_CORE_SCRIPT_PATH)

    assert r"Software\Microsoft\Windows\CurrentVersion\Run" in content
    assert "--background" in content
    assert 'Filename: "{app}\\audioblue.exe"' in content


def test_thin_inno_wrapper_uses_expected_output_name_and_core_include():
    content = read_text(INNO_SCRIPT_PATH)

    assert '#define InstallerOutputBaseFilename "AudioBlue-Setup-x64"' in content
    assert '#define BundleWebView2Runtime "0"' in content
    assert '#include "AudioBlue.InstallerCore.iss"' in content


def test_bundled_inno_wrapper_uses_expected_output_name_and_core_include():
    content = read_text(INNO_WITH_WEBVIEW2_SCRIPT_PATH)

    assert '#define InstallerOutputBaseFilename "AudioBlue-Setup-With-WebView2-x64"' in content
    assert '#define BundleWebView2Runtime "1"' in content
    assert '#include "AudioBlue.InstallerCore.iss"' in content


def test_inno_core_uses_repo_root_relative_dist_paths():
    content = read_text(INNO_CORE_SCRIPT_PATH)

    assert 'OutputDir=..\\dist\\installer' in content
    assert 'Source: "..\\dist\\AudioBlue\\*"' in content


def test_inno_core_warns_when_webview2_runtime_is_missing():
    content = read_text(INNO_CORE_SCRIPT_PATH)

    assert "function IsWebView2RuntimeInstalled()" in content
    assert '#define ReleaseArchitectureLabel "x64"' in content
    assert '#define BundledReleaseFileName "AudioBlue-Setup-With-WebView2-x64.exe"' in content
    assert "https://developer.microsoft.com/en-us/microsoft-edge/webview2/" in content


def test_inno_core_installs_local_webview2_runtime_in_bundled_variant():
    content = read_text(INNO_CORE_SCRIPT_PATH)

    assert '#define WebView2RuntimeRelativePath "..\\dist\\webview2\\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"' in content
    assert '#define WebView2BundledInstallerName "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"' in content
    assert "'/silent /install'" in content
