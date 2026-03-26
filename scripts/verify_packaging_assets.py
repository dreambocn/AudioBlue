from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


def collect_packaging_report(
    dist_root: Path,
    installer_scripts: Sequence[Path],
    installer_core_script: Path,
    webview2_runtime_installer: Path | None = None,
) -> dict[str, object]:
    """收集打包目录、安装器脚本与 WebView2 附加资源的校验结果。"""
    issues: list[str] = []
    app_root = dist_root / "AudioBlue"
    executable_path = app_root / "audioblue.exe"
    ui_index_candidates = [
        app_root / "ui" / "index.html",
        app_root / "_internal" / "ui" / "index.html",
    ]

    if not executable_path.exists():
        issues.append(f"Missing packaged executable: {executable_path}")
    if not any(path.exists() for path in ui_index_candidates):
        issues.append(f"Missing packaged UI entrypoint: {ui_index_candidates[0]}")

    for installer_script in installer_scripts:
        if not installer_script.exists():
            issues.append(f"Missing installer scaffold: {installer_script}")

    if not installer_core_script.exists():
        issues.append(f"Missing installer core scaffold: {installer_core_script}")
    else:
        content = installer_core_script.read_text(encoding="utf-8")
        if r"Software\Microsoft\Windows\CurrentVersion\Run" not in content:
            issues.append(
                "Installer core scaffold is missing the Windows Run registry autostart entry."
            )
        if "--background" not in content:
            issues.append(
                'Installer core scaffold is missing the "--background" launch argument.'
            )
        if "IsWebView2RuntimeInstalled" not in content:
            issues.append(
                "Installer core scaffold is missing WebView2 runtime detection."
            )
        if webview2_runtime_installer is not None:
            if not webview2_runtime_installer.exists():
                issues.append(
                    f"Missing bundled WebView2 runtime installer: {webview2_runtime_installer}"
                )
            if "MicrosoftEdgeWebView2RuntimeInstallerX64.exe" not in content:
                issues.append(
                    "Installer core scaffold is missing the bundled WebView2 runtime installer reference."
                )

    return {
        "ok": not issues,
        "distRoot": str(dist_root),
        "installerScripts": [str(path) for path in installer_scripts],
        "installerCoreScript": str(installer_core_script),
        "webview2RuntimeInstaller": (
            str(webview2_runtime_installer) if webview2_runtime_installer is not None else None
        ),
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify packaged AudioBlue assets.")
    parser.add_argument("--dist-root", type=Path, required=True)
    parser.add_argument(
        "--installer-script",
        type=Path,
        required=True,
        action="append",
        dest="installer_scripts",
    )
    parser.add_argument("--installer-core-script", type=Path, required=True)
    parser.add_argument("--webview2-runtime-installer", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = collect_packaging_report(
        dist_root=args.dist_root,
        installer_scripts=args.installer_scripts,
        installer_core_script=args.installer_core_script,
        webview2_runtime_installer=args.webview2_runtime_installer,
    )

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Packaging ok: {report['ok']}")
        for issue in report["issues"]:
            print(f"- {issue}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
