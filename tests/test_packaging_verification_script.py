"""覆盖打包校验脚本对发布目录布局的判断逻辑。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_module():
    """按脚本路径直接加载模块，避免测试依赖安装态入口。"""
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
    installer_core_script = tmp_path / "installer" / "AudioBlue.InstallerCore.iss"

    report = module.collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[installer_script],
        installer_core_script=installer_core_script,
    )

    assert report["ok"] is False
    assert any("audioblue.exe" in issue for issue in report["issues"])
    assert any("AudioBlue.iss" in issue for issue in report["issues"])
    assert any("AudioBlue.InstallerCore.iss" in issue for issue in report["issues"])


def test_collect_packaging_report_flags_missing_bundled_webview2_installer(tmp_path):
    module = load_module()

    dist_root = tmp_path / "dist"
    app_dir = dist_root / "AudioBlue"
    app_dir.mkdir(parents=True)
    (app_dir / "audioblue.exe").write_text("stub", encoding="utf-8")
    (app_dir / "ui").mkdir()
    (app_dir / "ui" / "index.html").write_text("<html></html>", encoding="utf-8")

    installer_dir = tmp_path / "installer"
    installer_dir.mkdir(parents=True)
    thin_script = installer_dir / "AudioBlue.iss"
    bundled_script = installer_dir / "AudioBlue.WithWebView2.iss"
    core_script = installer_dir / "AudioBlue.InstallerCore.iss"
    thin_script.write_text('#define BundleWebView2Runtime "0"', encoding="utf-8")
    bundled_script.write_text('#define BundleWebView2Runtime "1"', encoding="utf-8")
    core_script.write_text(
        """
[Setup]
AppName=AudioBlue

[Files]
Source: "..\\dist\\AudioBlue\\*"; DestDir: "{app}"
Source: "..\\dist\\webview2\\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; DestDir: "{tmp}"

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueData: """ + '"""{app}\\audioblue.exe --background"""' + """

[Code]
function IsWebView2RuntimeInstalled(): Boolean;
begin
  Result := True;
end;
""",
        encoding="utf-8",
    )

    report = module.collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[thin_script, bundled_script],
        installer_core_script=core_script,
        webview2_runtime_installer=dist_root / "webview2" / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
    )

    assert report["ok"] is False
    assert any("WebView2 runtime installer" in issue for issue in report["issues"])


def test_collect_packaging_report_passes_for_dual_installer_layout(tmp_path):
    module = load_module()

    dist_root = tmp_path / "dist"
    app_dir = dist_root / "AudioBlue"
    app_dir.mkdir(parents=True)
    (app_dir / "audioblue.exe").write_text("stub", encoding="utf-8")
    (app_dir / "ui").mkdir()
    (app_dir / "ui" / "index.html").write_text("<html></html>", encoding="utf-8")
    webview2_dir = dist_root / "webview2"
    webview2_dir.mkdir()
    (webview2_dir / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe").write_text("stub", encoding="utf-8")

    installer_dir = tmp_path / "installer"
    installer_dir.mkdir(parents=True)
    thin_script = installer_dir / "AudioBlue.iss"
    bundled_script = installer_dir / "AudioBlue.WithWebView2.iss"
    core_script = installer_dir / "AudioBlue.InstallerCore.iss"
    thin_script.write_text('#define BundleWebView2Runtime "0"', encoding="utf-8")
    bundled_script.write_text('#define BundleWebView2Runtime "1"', encoding="utf-8")
    core_script.write_text(
        """
[Setup]
AppName=AudioBlue

[Files]
Source: "..\\dist\\AudioBlue\\*"; DestDir: "{app}"
Source: "..\\dist\\webview2\\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; DestDir: "{tmp}"

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueData: """ + '"""{app}\\audioblue.exe --background"""' + """

[Code]
function IsWebView2RuntimeInstalled(): Boolean;
begin
  Result := True;
end;
""",
        encoding="utf-8",
    )

    report = module.collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[thin_script, bundled_script],
        installer_core_script=core_script,
        webview2_runtime_installer=webview2_dir / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
    )

    assert report["ok"] is True
    assert report["issues"] == []


def test_collect_packaging_report_accepts_pyinstaller_internal_ui_layout(tmp_path):
    module = load_module()

    dist_root = tmp_path / "dist"
    app_dir = dist_root / "AudioBlue"
    internal_ui_dir = app_dir / "_internal" / "ui"
    internal_ui_dir.mkdir(parents=True)
    (app_dir / "audioblue.exe").write_text("stub", encoding="utf-8")
    (internal_ui_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    webview2_dir = dist_root / "webview2"
    webview2_dir.mkdir()
    (webview2_dir / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe").write_text("stub", encoding="utf-8")

    installer_dir = tmp_path / "installer"
    installer_dir.mkdir(parents=True)
    thin_script = installer_dir / "AudioBlue.iss"
    bundled_script = installer_dir / "AudioBlue.WithWebView2.iss"
    core_script = installer_dir / "AudioBlue.InstallerCore.iss"
    thin_script.write_text('#define BundleWebView2Runtime "0"', encoding="utf-8")
    bundled_script.write_text('#define BundleWebView2Runtime "1"', encoding="utf-8")
    core_script.write_text(
        """
[Setup]
AppName=AudioBlue

[Files]
Source: "..\\dist\\AudioBlue\\*"; DestDir: "{app}"
Source: "..\\dist\\webview2\\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; DestDir: "{tmp}"

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueData: """ + '"""{app}\\audioblue.exe --background"""' + """

[Code]
function IsWebView2RuntimeInstalled(): Boolean;
begin
  Result := True;
end;
""",
        encoding="utf-8",
    )

    report = module.collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[thin_script, bundled_script],
        installer_core_script=core_script,
        webview2_runtime_installer=webview2_dir / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
    )

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
            "--installer-core-script",
            str(tmp_path / "installer" / "AudioBlue.InstallerCore.iss"),
            "--format",
            "text",
        ]
    )

    assert code == 1
