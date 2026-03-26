# AudioBlue Installer Verification Checklist

## Build Inputs
- `dist/AudioBlue/audioblue.exe` exists.
- `dist/AudioBlue/_internal/ui/index.html` exists.
- `installer/AudioBlue.iss` references `--background` for autostart.
- `installer/AudioBlue.WithWebView2.iss` exists.
- `dist/webview2/` 下存在目标架构对应的 WebView2 离线安装器。

## Installer Build
- Inno Setup compiler runs successfully for `installer/AudioBlue.iss`.
- Inno Setup compiler runs successfully for `installer/AudioBlue.WithWebView2.iss`.
- 当前目标架构的输出安装包会生成在 `dist/installer/` 下。

## Install Flow
- Fresh install creates Start Menu shortcuts.
- Desktop shortcut remains disabled by default unless selected.
- "Launch after install" starts `AudioBlue.exe`.

## Runtime Behavior
- Autostart task writes Windows Run key for current user.
- Re-login starts app with `--background` and tray-only behavior.
- Uninstall removes app files and cleans autostart Run key.

## Troubleshooting
- If WebView2 runtime is missing, `AudioBlue-Setup-<arch>.exe` shows actionable guidance.
- If WebView2 runtime is missing, `AudioBlue-Setup-With-WebView2-<arch>.exe` attempts local installation and shows actionable failure guidance when needed.
- Packaging verification helper reports no issues:
  - `uv run python scripts/verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --installer-script installer\AudioBlue.WithWebView2.iss --installer-core-script installer\AudioBlue.InstallerCore.iss --webview2-runtime-installer dist\webview2\<当前架构对应的离线安装器>.exe --format text`
