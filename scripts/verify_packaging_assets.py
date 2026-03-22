from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


def collect_packaging_report(
    dist_root: Path,
    installer_script: Path,
) -> dict[str, object]:
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
    if not installer_script.exists():
        issues.append(f"Missing installer scaffold: {installer_script}")
    else:
        content = installer_script.read_text(encoding="utf-8")
        if r"Software\Microsoft\Windows\CurrentVersion\Run" not in content:
            issues.append(
                "Installer scaffold is missing the Windows Run registry autostart entry."
            )
        if "--background" not in content:
            issues.append('Installer scaffold is missing the "--background" launch argument.')

    return {
        "ok": not issues,
        "distRoot": str(dist_root),
        "installerScript": str(installer_script),
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify packaged AudioBlue assets.")
    parser.add_argument("--dist-root", type=Path, required=True)
    parser.add_argument("--installer-script", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = collect_packaging_report(
        dist_root=args.dist_root,
        installer_script=args.installer_script,
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
