"""覆盖打包校验脚本对发布目录布局的判断逻辑。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def load_module():
    """按脚本路径直接加载模块，避免测试依赖安装态入口。"""
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_packaging_assets.py"
    spec = spec_from_file_location("verify_packaging_assets", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_packaging_fixture(
    tmp_path: Path,
    *,
    runtime_name: str = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
    core_runtime_name: str | None = None,
) -> tuple[Path, Path, Path, Path]:
    """构建最小打包目录，便于校验不同架构的 WebView2 文件名。"""
    dist_root = tmp_path / "dist"
    app_dir = dist_root / "AudioBlue"
    app_dir.mkdir(parents=True)
    (app_dir / "audioblue.exe").write_text("exe", encoding="utf-8")
    (app_dir / "ui").mkdir()
    (app_dir / "ui" / "index.html").write_text("<html></html>", encoding="utf-8")

    webview2_dir = dist_root / "webview2"
    webview2_dir.mkdir()
    runtime_path = webview2_dir / runtime_name
    runtime_path.write_text("runtime", encoding="utf-8")

    installer_dir = tmp_path / "installer"
    installer_dir.mkdir(parents=True)
    installer = installer_dir / "AudioBlue.iss"
    core = installer_dir / "AudioBlue.InstallerCore.iss"
    installer.write_text('#include "AudioBlue.InstallerCore.iss"', encoding="utf-8")
    referenced_runtime_name = core_runtime_name or runtime_name
    core.write_text(
        f"""
[Setup]
AppName=AudioBlue

[Files]
Source: "..\\dist\\AudioBlue\\*"; DestDir: "{{app}}"
Source: "..\\dist\\webview2\\{referenced_runtime_name}"; DestDir: "{{tmp}}"

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueData: """ + '"""{app}\\audioblue.exe --background"""' + f"""

[Code]
function IsWebView2RuntimeInstalled(): Boolean;
begin
  Result := True;
end;
""",
        encoding="utf-8",
    )

    return dist_root, installer, core, runtime_path


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


@pytest.mark.parametrize(
    "runtime_name",
    [
        "MicrosoftEdgeWebView2RuntimeInstallerX86.exe",
        "MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
        "MicrosoftEdgeWebView2RuntimeInstallerARM64.exe",
    ],
)
def test_collect_packaging_report_requires_matching_webview2_runtime_name(
    tmp_path, runtime_name
):
    """校验脚本必须按传入的 WebView2 安装器文件名检查脚本引用。"""
    module = load_module()
    dist_root, installer, core, runtime_path = build_packaging_fixture(
        tmp_path, runtime_name=runtime_name
    )

    report = module.collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[installer],
        installer_core_script=core,
        webview2_runtime_installer=runtime_path,
    )

    assert report["ok"] is True


def test_collect_packaging_report_rejects_mismatched_webview2_runtime_name(tmp_path):
    """传入 arm64 runtime 时，core 脚本不能只引用 x64 文件名。"""
    module = load_module()
    dist_root, installer, core, runtime_path = build_packaging_fixture(
        tmp_path,
        runtime_name="MicrosoftEdgeWebView2RuntimeInstallerARM64.exe",
        core_runtime_name="MicrosoftEdgeWebView2RuntimeInstallerX64.exe",
    )

    report = module.collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[installer],
        installer_core_script=core,
        webview2_runtime_installer=runtime_path,
    )

    assert report["ok"] is False
    assert any(
        "MicrosoftEdgeWebView2RuntimeInstallerARM64.exe" in issue
        for issue in report["issues"]
    )


def test_collect_packaging_report_accepts_injected_webview2_runtime_name(tmp_path):
    """真实 release 脚本会通过 Inno 预处理变量注入当前架构 runtime。"""
    module = load_module()
    runtime_name = "MicrosoftEdgeWebView2RuntimeInstallerARM64.exe"
    dist_root, installer, core, runtime_path = build_packaging_fixture(
        tmp_path,
        runtime_name=runtime_name,
    )
    core.write_text(
        """
#ifndef WebView2RuntimeRelativePath
#define WebView2RuntimeRelativePath "..\\dist\\webview2\\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
#endif

#ifndef WebView2BundledInstallerName
  #define WebView2BundledInstallerName "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
#endif

[Setup]
AppName=AudioBlue

[Files]
Source: "..\\dist\\AudioBlue\\*"; DestDir: "{app}"
Source: "{#WebView2RuntimeRelativePath}"; DestDir: "{tmp}"

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueData: """ + '"""{app}\\audioblue.exe --background"""' + """

[Code]
const
  WebView2BundledInstallerName = '{#WebView2BundledInstallerName}';

function IsWebView2RuntimeInstalled(): Boolean;
begin
  Result := True;
end;
""",
        encoding="utf-8",
    )

    report = module.collect_packaging_report(
        dist_root=dist_root,
        installer_scripts=[installer],
        installer_core_script=core,
        webview2_runtime_installer=runtime_path,
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
