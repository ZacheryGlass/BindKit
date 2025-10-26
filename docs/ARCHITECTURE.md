# BindKit Architecture

## Overview
BindKit is a PyQt6 tray application that loads standalone Python scripts from the local `scripts/` directory (plus any user-added paths), analyzes them with AST parsing, and exposes them through tray actions, global hotkeys, schedules, and a background-service runtime. The application is Windows-first and keeps the main window hidden, using a tray icon as the primary user interface.

## High-level layout
```
+-------------------+         +---------------------+
|   Tray Manager    | <-----> |    Settings/Views    |
|  (gui/tray_*.py)  |         | (views/, gui/...)    |
+---------+---------+         +----------+-----------+
          |                               |
          v                               v
+-------------------+         +---------------------+
|   Core Services   | <-----> |      Script IO      |
| (hotkeys, sched)  |         | (loader, analyzer,  |
|                   |         |  executor, services)|
+-------------------+         +---------------------+
```

## Core modules

### `main.py`
- Enforces single-instance behavior
- Boots the QApplication, tray icon, hotkey hooks, and schedule runtime
- Wires Qt signals between GUI components and the script infrastructure

### `core/script_loader.py`
- Discovers `.py` files (default + user-configured external paths)
- Runs AST analysis in worker threads for speed
- Persists success/failure state for UI display

### `core/script_analyzer.py`
- Parses Python source with `ast` to derive:
  - Execution strategy (`SUBPROCESS`, `FUNCTION_CALL`, `MODULE_EXEC`, `SERVICE`)
  - CLI arguments from argparse calls
  - Whether a `main()` function or `if __name__ == "__main__"` block exists
- Normalizes smart punctuation to prevent parse errors from pasted scripts

### `core/script_executor.py`
- Executes scripts based on the analyzer output
- Manages subprocesses, module caching, and direct `main()` invocation
- Provides shared schedule + service runtimes
- Validates arguments, enforces timeouts, captures stdout/stderr, and formats JSON results

### `core/service_runtime.py`
- Starts/stops long-running scripts as detached Windows processes
- Uses Job Objects to guarantee child cleanup
- Tails stdout/stderr into rotating log files per service

### `core/schedule_runtime.py`
- Schedules per-script timers with overlap prevention
- Emits Qt signals for start/stop/run/error states
- Persists `last_run`/`next_run` timestamps through `SettingsManager`

### `core/hotkey_manager.py` + `core/hotkey_registry.py`
- Wrapper around RegisterHotKey / UnregisterHotKey
- Conflict detection before registration
- Stores assignments in the Windows registry (via QSettings)

### GUI modules
- `gui/tray_manager.py`: builds the tray context menu, reflects script status, and surfaces actions
- `views/schedule_view.py`: schedule tab (enablement, interval, Run Now)
- `gui/settings_dialog.py`: hosts tabs for General, Hotkeys, Scripts, and Schedule
- `gui/hotkey_configurator.py`: modal dialog for capturing key combinations

## Script pipeline
1. **Discovery** – loader scans directories, ignoring `__*.py` and caches errors
2. **Analysis** – analyzer inspects AST, extracts CLI metadata, picks execution strategy
3. **Registration** – results stored as `ScriptInfo` objects and surfaced in the UI
4. **Execution** – tray/hotkey/schedule triggers call `ScriptExecutor.execute_script`
5. **Result handling** – executor normalizes JSON output, stores history, and updates menu text

### Execution strategies
| Strategy | When chosen | Behavior |
| -------- | ----------- | -------- |
| `SUBPROCESS` | Script exposes argparse arguments or only has an `if __name__ == "__main__"` block | Executes via `python script.py [--args]`, capturing stdout/stderr |
| `FUNCTION_CALL` | `main()` function exists without CLI parameters | Imports module once and calls `main()` on demand |
| `MODULE_EXEC` | Simple helper modules w/o `main()`/args | Imports module and runs top-level code |
| `SERVICE` | Script marked as service in settings | Managed through `ServiceRuntime` for start/stop lifecycle |

## Scheduler runtime
- Backed by QTimer instances stored per script
- Enforces intervals between 10 seconds and ~2.4 million seconds (~24.8 days)
- Tracks execution state to prevent overlapping runs
- Emits: `schedule_started`, `schedule_stopped`, `schedule_executed`, `schedule_error`, `schedule_execution_blocked`
- Integrates with `SettingsManager` to persist enablement + interval units between launches

## Service runtime
- Detached processes with `CREATE_NO_WINDOW` so scripts never flash a console
- Optional log streaming into `logs/services/<script>.log`
- Win32 Job Objects ensure that killing the tray app also stops orphaned child processes
- Supports restart attempts and forceful termination when stop events time out

## Hotkey flow
1. User opens Settings ? Hotkeys
2. `HotkeyConfigurator` captures key combo, validates modifiers, and warns about conflicts
3. Settings persist combination under `HKCU\Software\DesktopUtils\DesktopUtilityGUI\hotkeys`
4. `HotkeyManager` registers combo with Windows and maps it to the script
5. WM_HOTKEY events fire on a dedicated thread and dispatch through Qt signals back to the tray

## Error handling
- **Loader errors**: script is skipped, failure reason stored for UI display
- **Execution errors**: executor packages stderr/output into the JSON response and displays it in notifications
- **Schedule overlap**: `schedule_execution_blocked` signal explains that the previous run has not finished
- **Service crashes**: runtime marks state as `CRASHED`, stops log tailing, and notifies the UI

## Logging
- Primary loggers: `MAIN`, `GUI.*`, `Core.ScriptLoader`, `Core.ScriptExecutor`, `Core.ScheduleRuntime`, `Core.ServiceRuntime`
- Log format: `HH:MM:SS | LEVEL | MODULE | Message`
- Logs stored in `logs/app.log` with rotation; service-specific logs live under `logs/services/`

## Future enhancements
- Linux/macOS support for tray + hotkeys (currently Windows-only)
- Script bundles with dependencies packaged alongside scripts
- Remote script catalogs for sharing BindKit-compatible tools
- Metrics view for execution duration and historical success rates
