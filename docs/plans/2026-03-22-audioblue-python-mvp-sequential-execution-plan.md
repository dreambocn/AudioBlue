# AudioBlue Python MVP Sequential Execution Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the Windows Python MVP described in the migration brief in the same overall 8-task order, while making each step directly executable in the current empty repository.

**Architecture:** The app is a uv-managed Python package with a tray-only Windows host on the main thread and a WinRT-backed connector worker behind a service boundary. Pure state, config, and menu-shaping logic stay unit-testable, while device enumeration and audio playback connection lifecycle stay isolated behind a Windows-specific integration layer.

**Tech Stack:** uv, Python 3.12, PyWinRT (`winrt-Windows.Media.Audio`, `winrt-Windows.Devices.Enumeration`), `pywin32`, `pytest`, `PyInstaller`

---

## Summary

- Keep the project-book task order intact: bootstrap, feasibility, models/config, service contract, WinRT integration, tray host, reconnect/shutdown, packaging.
- Treat the feasibility probe as a hard gate inside Task 2, not as a reordered phase. If it fails, stop implementation and record the blocker instead of forcing later tasks.
- Assume execution happens on Windows with PowerShell, `uv` available on `PATH`, and at least one real Bluetooth audio device available for manual validation.
- Because the current repository only contains planning docs, Task 1 includes creating the real package structure from scratch.

## Important Interfaces

- `src/audio_blue/main.py`
  - Exposes `main() -> int`
  - Owns startup wiring for config load, tray host startup, reconnect flow, and shutdown
- `src/audio_blue/models.py`
  - Defines typed `DeviceSummary` and `AppConfig`
- `src/audio_blue/config.py`
  - Exposes config load/save helpers for `%LocalAppData%\AudioBlue\config.json`
- `src/audio_blue/connector_service.py`
  - Exposes `refresh_devices()`, `connect(device_id)`, `disconnect(device_id)`, `shutdown()`
  - Publishes device and connection state updates through a callback or queue contract chosen during implementation
- `src/audio_blue/tray_host.py`
  - Translates service/config state into Win32 tray menu items and command handlers
- `scripts/feasibility_probe.py`
  - Exposes `run_probe() -> dict`
  - Returns at least `audio_namespace_available`, `enumeration_namespace_available`, `device_selector`, `devices`, and `errors`

## Sequential Tasks

### Task 1: Bootstrap the uv project

**Files:**
- Create: `E:\Development\Project\PythonProjects\AudioBlue\pyproject.toml`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\.python-version`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\README.md`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\__init__.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\main.py`

**Step 1: Initialize the package scaffold**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv init --package`

Expected: `pyproject.toml`, `README.md`, and `src` package scaffold are created.

**Step 2: Pin the interpreter version**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv python pin 3.12`

Expected: `.python-version` contains `3.12`.

**Step 3: Add runtime dependencies**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv add winrt-Windows.Media.Audio winrt-Windows.Devices.Enumeration pywin32`

Expected: runtime dependencies are recorded in `pyproject.toml` and lockfile metadata is created if `uv` chooses to do so.

**Step 4: Add development dependencies**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv add --dev pytest pyinstaller`

Expected: development dependencies are recorded.

**Step 5: Replace the sample entrypoint**

Implement `src/audio_blue/main.py` with a `main() -> int` placeholder that raises `NotImplementedError`, and keep `src/audio_blue/__init__.py` import-safe.

**Step 6: Verify package import**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run python -c "import audio_blue; print('bootstrap-ok')"`

Expected: prints `bootstrap-ok`.

**Step 7: Commit the bootstrap checkpoint**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; git add pyproject.toml .python-version README.md src; git commit -m "chore: bootstrap uv-managed AudioBlue project"`

Expected: bootstrap baseline is committed if the repository has been initialized as Git; if not, initialize Git before this step or defer commits until Git exists.

### Task 2: Add the feasibility gate before production logic

**Files:**
- Create: `E:\Development\Project\PythonProjects\AudioBlue\scripts\feasibility_probe.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_feasibility_probe_contract.py`

**Step 1: Write the failing contract test**

Write a test that requires `run_probe()` to return a dictionary with:
- `audio_namespace_available`
- `enumeration_namespace_available`
- `device_selector`
- `devices`
- `errors`

**Step 2: Verify the contract starts RED**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_feasibility_probe_contract.py -v`

Expected: FAIL because `run_probe()` does not yet exist or does not satisfy the contract.

**Step 3: Implement the minimal probe**

Implement `scripts/feasibility_probe.py` so it:
- imports the WinRT namespaces safely
- attempts to obtain `AudioPlaybackConnection.get_device_selector()`
- attempts device enumeration
- serializes any failures into `errors`
- never crashes the process on namespace or enumeration failure

**Step 4: Verify the test turns GREEN**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_feasibility_probe_contract.py -v`

Expected: PASS.

**Step 5: Run the manual feasibility probe**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run python scripts\feasibility_probe.py`

Expected: structured output showing whether namespaces load, whether a selector is available, and the currently discoverable devices.

**Step 6: Enforce the hard stop condition**

If the probe cannot import required namespaces or cannot obtain a selector, stop the implementation stream here and record the exact failure in `README.md` or a follow-up note before considering an alternate platform path.

**Step 7: Commit the feasibility checkpoint**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; git add scripts tests; git commit -m "test: add WinRT feasibility gate for AudioBlue"`

Expected: feasibility gate is committed.

### Task 3: Implement pure data models and configuration

**Files:**
- Create: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\models.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\config.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_models.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_config.py`

**Step 1: Write failing model and config tests**

Cover:
- `DeviceSummary` field shape and defaults
- `AppConfig` field shape and defaults
- default config when no file exists
- fallback config when JSON is invalid
- persistence round-trip for reconnect and last device IDs

**Step 2: Verify RED**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_models.py tests\test_config.py -v`

Expected: FAIL because the modules and behavior do not exist yet.

**Step 3: Implement the typed model layer**

Implement typed structures for:
- `DeviceSummary`
- `AppConfig`

Keep them simple and serialization-friendly.

**Step 4: Implement config persistence**

Implement load/save helpers targeting `%LocalAppData%\AudioBlue\config.json` with:
- directory auto-create
- default fallback on missing file
- default fallback on invalid JSON
- persistence for `reconnect` and `last_devices`

Mirror the behavioral intent of `E:\Development\Project\GitHubStar\AudioPlaybackConnector\SettingsUtil.hpp`, not its API shape.

**Step 5: Verify GREEN**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_models.py tests\test_config.py -v`

Expected: PASS.

**Step 6: Commit the state/config checkpoint**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; git add src tests; git commit -m "feat: add AudioBlue models and config persistence"`

Expected: models and config are committed.

### Task 4: Implement a connector service boundary without tray coupling

**Files:**
- Create: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_connector_service_contract.py`

**Step 1: Write failing service contract tests**

Cover:
- `refresh_devices()` updates device inventory
- `connect(device_id)` starts a connection attempt
- `disconnect(device_id)` tears down a tracked connection
- `shutdown()` releases tracked resources and stops worker activity

**Step 2: Verify RED**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_connector_service_contract.py -v`

Expected: FAIL because the service contract does not yet exist.

**Step 3: Implement the minimal service shell**

Implement:
- device registry by ID
- connection registry by device ID
- explicit service methods for refresh/connect/disconnect/shutdown
- outbound state publication through one internal mechanism only, either callback-driven or queue-driven

Do not import tray UI code here.

**Step 4: Verify GREEN**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_connector_service_contract.py -v`

Expected: PASS.

**Step 5: Commit the service-boundary checkpoint**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; git add src tests; git commit -m "feat: add connector service contract for AudioBlue"`

Expected: service shell is committed.

### Task 5: Integrate real WinRT audio connection behavior

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_state_mapping.py`

**Step 1: Write failing state-mapping tests**

Cover pure mapping logic for:
- connect success
- timeout
- access denied or rejected
- unknown failure
- remote close or state-changed closure handling

**Step 2: Verify RED**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_state_mapping.py -v`

Expected: FAIL because the mapping logic is not implemented yet.

**Step 3: Add the WinRT worker integration**

Extend `connector_service.py` so a dedicated worker thread:
- initializes the proper WinRT apartment for its own thread context
- discovers devices using `AudioPlaybackConnection.get_device_selector()`
- creates connections from device IDs
- executes `StartAsync` and `OpenAsync`
- subscribes to state-changed events
- marshals resulting state updates back to the main-thread-facing service surface

Use `E:\Development\Project\GitHubStar\AudioPlaybackConnector\AudioPlaybackConnector.cpp` as the lifecycle reference.

**Step 4: Verify GREEN for pure-state tests**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_state_mapping.py -v`

Expected: PASS.

**Step 5: Run the manual integration check**

Run a manual flow such as:
- refresh devices
- print discovered device IDs and names
- connect one known device
- print resulting status
- disconnect or close cleanly

Use either a dedicated script or a one-off `uv run python -c` command, but keep the flow reproducible.

**Step 6: Commit the WinRT integration checkpoint**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; git add src tests scripts README.md; git commit -m "feat: integrate WinRT audio playback connections"`

Expected: real WinRT behavior is committed.

### Task 6: Add the tray host with menu-state tests first

**Files:**
- Create: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\tray_host.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\logging_util.py`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\main.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_tray_menu_mapping.py`

**Step 1: Write failing menu-mapping tests**

Cover:
- static actions: Refresh Devices, Bluetooth Settings, Exit
- reconnect toggle item
- one device item per discovered device
- labels reflecting connection state
- correct command routing for connect or disconnect actions

**Step 2: Verify RED**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_tray_menu_mapping.py -v`

Expected: FAIL because tray menu shaping does not yet exist.

**Step 3: Implement the tray host**

Implement:
- hidden Win32 message window on the main thread
- tray icon registration through `pywin32`
- menu rebuilds from current service/config state
- handlers for refresh, connect or disconnect, reconnect toggle, Bluetooth settings, and exit

Do not add a persistent application window.

**Step 4: Wire startup behavior**

Update `main.py` so startup:
- loads config
- starts the connector service
- creates the tray host
- restores `last_devices` when reconnect is enabled

**Step 5: Verify GREEN**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_tray_menu_mapping.py -v`

Expected: PASS.

**Step 6: Commit the tray-host checkpoint**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; git add src tests; git commit -m "feat: add tray-based AudioBlue MVP host"`

Expected: tray host is committed.

### Task 7: Add reconnect and shutdown regression coverage

**Files:**
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_config.py`
- Create: `E:\Development\Project\PythonProjects\AudioBlue\tests\test_shutdown_and_reconnect.py`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\main.py`
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\src\audio_blue\connector_service.py`

**Step 1: Write failing regression tests**

Cover:
- reconnect-on-startup behavior
- persistence of connected device IDs during exit
- clean connector worker shutdown with no leaked active connections

**Step 2: Verify RED**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_config.py tests\test_shutdown_and_reconnect.py -v`

Expected: FAIL because reconnect and shutdown logic is not complete yet.

**Step 3: Implement only the missing reconnect and shutdown behavior**

Keep changes focused on:
- startup reconnect flow
- shutdown persistence ordering
- worker teardown ordering
- connection close behavior during exit

Mirror the intent of:
- `E:\Development\Project\GitHubStar\AudioPlaybackConnector\SettingsUtil.hpp`
- `E:\Development\Project\GitHubStar\AudioPlaybackConnector\AudioPlaybackConnector.cpp`

**Step 4: Verify GREEN**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_config.py tests\test_shutdown_and_reconnect.py -v`

Expected: PASS.

**Step 5: Commit the reconnect/shutdown checkpoint**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; git add src tests; git commit -m "feat: add reconnect and shutdown behavior"`

Expected: reconnect and shutdown logic are committed.

### Task 8: Package and verify the MVP

**Files:**
- Create: `E:\Development\Project\PythonProjects\AudioBlue\AudioBlue.spec` or equivalent packaging config if PyInstaller requires a checked-in spec
- Modify: `E:\Development\Project\PythonProjects\AudioBlue\README.md`

**Step 1: Document operation and support commands**

Update `README.md` with:
- bootstrap instructions using `uv`
- test commands
- manual run command
- packaging command
- config file location
- log file location if logging is added
- supported Windows prerequisites and stop conditions

**Step 2: Build the packaged app**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pyinstaller --onedir -n AudioBlue src\audio_blue\main.py`

Expected: packaged output is created under `dist\AudioBlue\`.

**Step 3: Run the full automated suite**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest -v`

Expected: PASS.

**Step 4: Run the manual MVP checklist**

Validate on a real Windows machine:
- tray startup succeeds and stays resident
- refresh devices updates the device list
- connect succeeds for a known Bluetooth audio device
- disconnect closes the connection cleanly
- remote close or state change updates the tray state
- reconnect persists and restores expected devices on relaunch
- corrupt config falls back safely instead of crashing

**Step 5: Commit the packaging checkpoint**

Run: `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; git add README.md AudioBlue.spec dist; git commit -m "build: add packaging and run instructions"`

Expected: packaging instructions and config are committed. If packaged binaries should stay out of source control, commit only the spec and docs, not `dist`.

## Test Plan

- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_feasibility_probe_contract.py -v`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_models.py tests\test_config.py -v`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_connector_service_contract.py -v`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_state_mapping.py -v`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_tray_menu_mapping.py -v`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest tests\test_config.py tests\test_shutdown_and_reconnect.py -v`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run pytest -v`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run python scripts\feasibility_probe.py`
- `Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'; uv run python -m audio_blue.main`

## Assumptions and Defaults

- The repository may need `git init` before the commit steps become valid.
- Python implementation targets Windows only; no cross-platform abstraction is required for the MVP.
- Tray behavior replaces the original XAML-based picker UI; no XAML Islands or `DevicePicker` UI are ported.
- Unit tests should cover pure logic and state shaping; real WinRT connection success is validated manually with hardware.
- If any of the following occur, stop and reassess instead of pushing through:
  - required WinRT namespaces cannot be imported from Python
  - `AudioPlaybackConnection` cannot be created from a known device ID
  - WinRT callbacks are unreliable on the worker thread
  - packaged output cannot start the tray app or access WinRT behavior that works under `uv run`

Plan complete and saved to `E:\Development\Project\PythonProjects\AudioBlue\docs\plans\2026-03-22-audioblue-python-mvp-sequential-execution-plan.md`.
