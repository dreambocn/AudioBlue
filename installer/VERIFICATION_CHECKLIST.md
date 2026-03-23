# AudioBlue Installer Verification Checklist

## Build Inputs
- `dist/AudioBlue/AudioBlue.exe` exists.
- `dist/AudioBlue/_internal/ui/index.html` exists.
- `installer/AudioBlue.iss` references `--background` for autostart.

## Installer Build
- Inno Setup compiler runs successfully for `installer/AudioBlue.iss`.
- Output setup binary is generated under `dist/installer/`.

## Install Flow
- Fresh install creates Start Menu shortcuts.
- Desktop shortcut remains disabled by default unless selected.
- "Launch after install" starts `AudioBlue.exe`.

## Runtime Behavior
- Autostart task writes Windows Run key for current user.
- Re-login starts app with `--background` and tray-only behavior.
- Uninstall removes app files and cleans autostart Run key.

## Troubleshooting
- If WebView2 runtime is missing, installer/app shows actionable guidance.
- Packaging verification helper reports no issues:
  - `uv run python scripts/verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --format text`
