# BindKit

BindKit is a PyQt6 system tray application for Windows that discovers standalone Python scripts, exposes them through a tray menu, and lets you run them manually, on a schedule, or through global hotkeys. All scripts run in isolation so a single failure never crashes the tray app.

## Features

### Core experience
- **Tray-first UI** with a single icon, dynamic menus, and a lightweight hidden window
- **Auto-discovery** of `.py` files in the `scripts/` directory plus optional external script paths stored in settings
- **One script model**: plain Python files with either a `main()` function or an argparse CLI, no base classes or special decorators
- **Live status + logs** surfaced in the tray menu and `logs/` directory
- **External configuration** via `core/settings.py`, Windows Registry persistence, and JSON exportable preferences

### Script execution
- **AST-powered analyzer** determines arguments, detects `main()` functions, and chooses the safest strategy
- **Execution strategies**: subprocess (argparse/CLI), direct `main()` call, module execution, or Windows service mode
- **Argument validation** driven by detected argparse metadata so the UI can prompt before execution
- **JSON contract** between scripts and the GUI (`{"success": true/false, "message": "..."}`), with optional `data`, `output`, and `error` fields for richer feedback
- **Module cache** with aggressive cleanup so frequently used scripts stay warm without leaking memory

### Scheduler and services
- **Interval scheduling** with per-script enablement, 10 second to ~24.8 day limits, overlap prevention, and persisted timestamps
- **Service runtime** for long-running/background scripts using detached Win32 processes, job objects, and rotating logs
- **Graceful shutdown** that stops services, cancels timers, and flushes logs on exit

### Hotkeys
- **RegisterHotKey integration** with conflict detection, duplicate prevention, and restart-safe re-registration
- **Configurable modifiers** (Ctrl, Alt, Shift, Win) plus any standard key
- **Instant feedback** when a hotkey fails (e.g., reserved combination)

## Installation

1. Install Python 3.10 or newer on Windows
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Activate a virtual environment before running the app

## Usage

### Running the tray app
```bash
# Normal startup
python main.py

# Start minimized to the tray
python main.py --minimized
```
A notification appears on first launch; afterwards the tray icon hosts every script entry plus Settings, Logs, and Exit controls.

### Working with scripts
- **Tray menu**: Right-click the icon to run a script instantly or inspect its last result
- **Hotkeys**: Open `Settings -> Hotkeys`, pick a script, press your desired combination, then click OK
- **Schedules**: `Settings -> Schedule` lets you toggle the schedule, set interval + units, and monitor next/last run timestamps
- **Arguments**: Scripts that declare argparse parameters show configurable fields inside the settings dialog so you can persist defaults

### Logs and diagnostics
- Runtime logs live in `logs/app.log` (rolling)
- Each service-managed script also writes to `logs/services/<script>.log`
- Test hotkeys with the included `example.py` script or create a quick script that prints JSON to confirm bindings

## Creating custom scripts

BindKit treats every `.py` file in `scripts/` as a standalone program. Follow these rules:

1. **Stick to standard Python** (no framework-specific inheritance required)
2. **Provide a `main()` function** or an argparse entry point guarded by `if __name__ == "__main__":`
3. **Accept arguments with argparse** so BindKit can auto-detect available options
4. **Return JSON** describing the outcome

### Minimal template
```python
#!/usr/bin/env python3
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Toggle Focus Assist")
    parser.add_argument("--mode", choices=["off", "priority", "alarms"], default="priority")
    args = parser.parse_args()

    # TODO: implement OS interaction here
    result = {
        "success": True,
        "message": f"Focus Assist set to {args.mode}",
        "data": {"mode": args.mode}
    }

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Best practices
- **Keep scripts idempotent** so repeated runs via scheduler or hotkeys are safe
- **Handle Windows-only behavior** defensively (check `sys.platform`) and emit clear error messages
- **Validate prerequisites** (admin rights, executables, devices) before doing destructive work
- **Use `PYTHONIOENCODING` aware printing** (already enforced by the executor) and avoid writing to stdout outside the final JSON payload

## Included scripts

| Script | Description |
| ------ | ----------- |
| `example.py` | Shows a PyQt6 message box to verify the pipeline |
| `recycle_bin_empty.py` | Uses PowerShell/Win32 APIs to empty the recycle bin with status reporting |

Drop additional scripts into `scripts/` or add external paths from the Settings dialog; BindKit rescans automatically.

## Further reading

- `docs/ARCHITECTURE.md` � system overview and component responsibilities
- `docs/API_REFERENCE.md` � public Python APIs for settings, hotkeys, and runtimes
- `docs/SCRIPT_TUTORIAL.md` � step-by-step guide for building high-quality scripts
- `docs/SCHEDULER_GUIDE.md` � scheduler UX, signals, and troubleshooting
- `docs/HOTKEY_FEATURE.md` � hotkey UX deep dive

## Troubleshooting

- **PyQt DLL errors**: Clear `%LOCALAPPDATA%\pyinstaller`, reinstall dependencies, and ensure antivirus excludes the BindKit directory
- **Hotkey conflicts**: Try adding the Win modifier or pick a less common combination
- **Script fails to load**: Check `logs/app.log`; the loader reports syntax errors, missing files, and invalid argparse setups
- **Scheduler stuck**: Verify the interval (>= 10s), ensure the script is not already running, and review `logs/schedules.log` for overlap warnings

If issues persist, open an issue with your Windows version, script output, and the relevant log excerpts.
