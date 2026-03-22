# AudioBlue

AudioBlue is a Windows-only Python MVP for managing Bluetooth audio playback connections from the system tray.

## Requirements

- Windows 10 2004 or later
- `uv 0.10+`
- Python `3.12`
- A Bluetooth audio playback device that exposes `AudioPlaybackConnection`

## Bootstrap

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv python install 3.12
uv sync
```

## Run

Feasibility probe:

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python scripts\feasibility_probe.py
```

Tray app:

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python -m audio_blue.main
```

## Test

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run pytest -v
```

## Build

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run pyinstaller AudioBlue.spec
```

Packaged output is created under `dist\AudioBlue\`.

## Runtime Files

- Config: `%LocalAppData%\AudioBlue\config.json`
- Log: `%LocalAppData%\AudioBlue\audioblue.log`

## Known Manual Checks

- Tray icon appears and stays resident.
- Refresh Devices updates the current target list.
- Connect or Disconnect updates device state.
- Bluetooth Settings opens the Windows Bluetooth settings page.
- Reconnect On Next Start persists and restores active device IDs.

## Stop Conditions

Stop the Python implementation path and reassess if any of these happen:

- WinRT namespaces cannot be imported from Python.
- `AudioPlaybackConnection.get_device_selector()` fails.
- `AudioPlaybackConnection.try_create_from_id(...)` cannot create a connection for a known device.
- Worker-thread WinRT callbacks prove unreliable.
- Packaged output cannot start the tray app or loses WinRT access that works under `uv run`.
