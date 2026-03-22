# AudioBlue Python MVP Migration Plan

> For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python MVP for Windows Bluetooth audio playback connection management in E:\Development\Project\PythonProjects\AudioBlue, using uv for Python and dependency management, while preserving the core behavior of the local C++ reference application without attempting a 1:1 XAML UI port.

**Architecture:** The MVP is a packaged Python application managed by uv, with a strict split between a Win32 tray/UI host on the main thread and a WinRT connector worker on a background thread. The app exposes a tray-only interaction model: refresh devices, connect or disconnect a device, toggle reconnect-on-next-start, open Bluetooth settings, and exit. The implementation keeps pure-Python state and config logic testable, while isolating WinRT calls behind a service boundary.

**Tech Stack:** uv, Python 3.12, PyWinRT (winrt-Windows.Media.Audio, winrt-Windows.Devices.Enumeration), pywin32, pytest, PyInstaller

---

## Local Reference Project

Use the following local files as the behavior reference during implementation. These are absolute paths and must be preserved in any follow-up implementation notes.

- E:\Development\Project\GitHubStar\AudioPlaybackConnector\README.md
- E:\Development\Project\GitHubStar\AudioPlaybackConnector\AudioPlaybackConnector.cpp
- E:\Development\Project\GitHubStar\AudioPlaybackConnector\AudioPlaybackConnector.h
- E:\Development\Project\GitHubStar\AudioPlaybackConnector\SettingsUtil.hpp
- E:\Development\Project\GitHubStar\AudioPlaybackConnector\pch.h
- E:\Development\Project\GitHubStar\AudioPlaybackConnector\AudioPlaybackConnector.vcxproj

## Required Behavior Mapping

- WinRT feature gating based on AudioPlaybackConnection availability.
- Device filtering based on AudioPlaybackConnection::GetDeviceSelector().
- Connection lifecycle based on TryCreateFromId, StartAsync, OpenAsync, and StateChanged.
- Persistent config with reconnect and lastDevices.
- Reconnect on next launch.
- Tray-driven workflow instead of a normal main window.

Do not port these reference-specific UI technologies into the MVP:

- DevicePicker
- DesktopWindowXamlSource
- XAML Islands
- Direct2D SVG icon rendering

The Python MVP uses a simpler Win32 tray menu instead.

## Task 1: Bootstrap the uv project

**Files:**
- Create: E:\Development\Project\PythonProjects\AudioBlue\pyproject.toml
- Create: E:\Development\Project\PythonProjects\AudioBlue\.python-version
- Create: E:\Development\Project\PythonProjects\AudioBlue\README.md
- Create: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\__init__.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\main.py

**Steps:**
1. Run `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv init --package`.
2. Run `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv python pin 3.12`.
3. Run `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv add winrt-Windows.Media.Audio winrt-Windows.Devices.Enumeration pywin32`.
4. Run `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv add --dev pytest pyinstaller`.
5. Replace the generated sample entrypoint with `src\audio_blue\main.py` containing `main() -> int` that raises `NotImplementedError`.
6. Verify with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run python -c "import audio_blue; print('bootstrap-ok')"`.
7. Commit with `git commit -m "chore: bootstrap uv-managed AudioBlue project"`.

## Task 2: Add the feasibility gate before any production implementation

**Files:**
- Create: E:\Development\Project\PythonProjects\AudioBlue\scripts\feasibility_probe.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\tests\test_feasibility_probe_contract.py

**Steps:**
1. Write a failing test that requires `run_probe()` to return a dictionary with `audio_namespace_available`, `enumeration_namespace_available`, `device_selector`, `devices`, and `errors`.
2. Verify RED with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_feasibility_probe_contract.py -v`.
3. Implement the minimal probe to import the WinRT namespaces, obtain the audio playback device selector, attempt device enumeration, and return structured output without crashing.
4. Verify GREEN with the same pytest command.
5. Manually execute `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run python scripts\feasibility_probe.py`.
6. Stop the whole Python path if the probe cannot import the namespaces or cannot obtain the selector.
7. Commit with `git commit -m "test: add WinRT feasibility gate for AudioBlue"`.

## Task 3: Implement pure data models and configuration with tests first

**Files:**
- Create: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\models.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\config.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\tests\test_models.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\tests\test_config.py

**Steps:**
1. Write failing tests covering `DeviceSummary`, `AppConfig`, and default config values.
2. Verify RED with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_models.py tests\test_config.py -v`.
3. Implement dataclasses or equivalent typed structures for `DeviceSummary` and `AppConfig`.
4. Implement config persistence at `%LocalAppData%\AudioBlue\config.json` with default fallback on missing or invalid JSON.
5. Mirror the semantics of E:\Development\Project\GitHubStar\AudioPlaybackConnector\SettingsUtil.hpp.
6. Verify GREEN with the same pytest command.
7. Commit with `git commit -m "feat: add AudioBlue models and config persistence"`.

## Task 4: Implement a connector service boundary without UI coupling

**Files:**
- Create: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\tests\test_connector_service_contract.py

**Steps:**
1. Write failing service contract tests for `refresh_devices()`, `connect(device_id)`, `disconnect(device_id)`, and `shutdown()`.
2. Verify RED with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_connector_service_contract.py -v`.
3. Implement a service shell that stores known devices, tracks connection handles by device ID, and emits state updates through a callback or queue.
4. Keep tray logic out of this module.
5. Verify GREEN with the same pytest command.
6. Commit with `git commit -m "feat: add connector service contract for AudioBlue"`.

## Task 5: Integrate real WinRT audio connection behavior behind the service

**Files:**
- Modify: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\tests\test_state_mapping.py

**Steps:**
1. Write failing tests for pure state mapping logic: success, timeout, denied, unknown failure, and closed event handling.
2. Verify RED with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_state_mapping.py -v`.
3. Implement a background worker that initializes the WinRT apartment on its own thread, discovers devices with `AudioPlaybackConnection.get_device_selector()`, creates connections from device IDs, performs `StartAsync` and `OpenAsync`, subscribes to `StateChanged`, and posts state updates back to the main thread.
4. Use E:\Development\Project\GitHubStar\AudioPlaybackConnector\AudioPlaybackConnector.cpp as the lifecycle reference.
5. Verify GREEN for the pure state tests with the same pytest command.
6. Add a manual check script or `uv run python -c` flow that refreshes devices, prints discovered devices, attempts a connect on one known device ID, prints result status, and closes cleanly.
7. Commit with `git commit -m "feat: integrate WinRT audio playback connections"`.

## Task 6: Add tray host behavior with tests for menu-state mapping first

**Files:**
- Create: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\tray_host.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\logging_util.py
- Modify: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\main.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\tests\test_tray_menu_mapping.py

**Steps:**
1. Write failing tests covering menu composition: Refresh Devices, Reconnect On Next Start, one menu item per device, stateful device labels, Bluetooth Settings, and Exit.
2. Verify RED with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_tray_menu_mapping.py -v`.
3. Implement a hidden Win32 message host on the main thread and tray icon registration via pywin32.
4. Implement menu rebuilds from service state and handlers for refresh, connect or disconnect, reconnect toggle, Bluetooth settings, and exit.
5. Load config at startup, start the connector worker, and restore `last_devices` when reconnect is enabled.
6. Do not add a persistent GUI window.
7. Verify GREEN with the same pytest command.
8. Commit with `git commit -m "feat: add tray-based AudioBlue MVP host"`.

## Task 7: Add reconnect and shutdown regression coverage

**Files:**
- Modify: E:\Development\Project\PythonProjects\AudioBlue\tests\test_config.py
- Create: E:\Development\Project\PythonProjects\AudioBlue\tests\test_shutdown_and_reconnect.py
- Modify: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\main.py
- Modify: E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py

**Steps:**
1. Write failing regression tests for startup reconnect behavior, shutdown persistence of connected device IDs, and clean worker shutdown.
2. Verify RED with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_config.py tests\test_shutdown_and_reconnect.py -v`.
3. Implement only the reconnect and shutdown logic required by the tests.
4. Mirror the intent of E:\Development\Project\GitHubStar\AudioPlaybackConnector\SettingsUtil.hpp and E:\Development\Project\GitHubStar\AudioPlaybackConnector\AudioPlaybackConnector.cpp.
5. Verify GREEN with the same pytest command.
6. Commit with `git commit -m "feat: add reconnect and shutdown behavior"`.

## Task 8: Package and verify the MVP without changing scope

**Files:**
- Create: E:\Development\Project\PythonProjects\AudioBlue\AudioBlue.spec or equivalent packaging config if needed
- Modify: E:\Development\Project\PythonProjects\AudioBlue\README.md

**Steps:**
1. Document project bootstrap with uv, test commands, manual run commands, build command, and the locations of config and logs.
2. Build with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pyinstaller --onedir -n AudioBlue src\audio_blue\main.py`.
3. Run the full suite with `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest -v`.
4. Manually verify tray startup, device refresh, connect, disconnect, remote close handling, reconnect persistence, and corrupt-config fallback.
5. Commit with `git commit -m "build: add packaging and run instructions"`.

## Failure Conditions That Stop Implementation

- `uv run python scripts\feasibility_probe.py` cannot import the required WinRT namespaces.
- `AudioPlaybackConnection` cannot be created from Python for a known device.
- WinRT callbacks cannot be made reliable on a dedicated worker thread.
- Packaged output works differently from `uv run` in a way that blocks tray startup or WinRT access.

If any stop condition is reached, do not keep forcing the Python path. Reassess with a C# desktop implementation instead.

## Verification Commands

- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest -v`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run python scripts\feasibility_probe.py`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run python -m audio_blue.main`

Expected:
- tests pass
- feasibility probe reports usable WinRT access
- app starts and stays resident in the tray without crashing

## External References

- AudioPlaybackConnection API: https://learn.microsoft.com/en-us/uwp/api/windows.media.audio.audioplaybackconnection?view=winrt-26100
- DevicePicker API: https://learn.microsoft.com/en-us/uwp/api/windows.devices.enumeration.devicepicker?view=winrt-26100
- DesktopWindowXamlSource API: https://learn.microsoft.com/en-us/uwp/api/windows.ui.xaml.hosting.desktopwindowxamlsource?view=winrt-26100
- uv project creation: https://docs.astral.sh/uv/concepts/projects/init/
- uv dependency management: https://docs.astral.sh/uv/concepts/projects/dependencies/
- uv Python version management: https://docs.astral.sh/uv/concepts/python-versions/
